import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prompt_folder"))
import prompts as p  # noqa: E402


def write(root, rel, text="x"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def root(tmp_path):
    write(tmp_path, "a.txt", "root prompt")
    write(tmp_path, "moody/10.txt", "ten")
    write(tmp_path, "moody/2.txt", "two")
    write(tmp_path, "moody/1.txt", "one")
    write(tmp_path, "moody/notes.md", "ignored")
    write(tmp_path, "moody/.hidden.txt", "ignored")
    write(tmp_path, "moody/rain/3.txt", "rain")
    write(tmp_path, "empty/readme.md", "no prompts")
    return tmp_path


def test_folders_include_parents_and_skip_empty(root):
    write(root, "deep/only/x.txt")
    assert p.list_folders(root) == [p.ROOT_FOLDER, "deep", "deep/only", "moody", "moody/rain"]


def test_files_natural_order_and_txt_only(root):
    assert p.prompt_files(root, "moody", False) == ["moody/1.txt", "moody/2.txt", "moody/10.txt"]


def test_subfolders(root):
    assert p.prompt_files(root, "moody", True) == ["moody/1.txt", "moody/2.txt", "moody/10.txt", "moody/rain/3.txt"]
    assert "a.txt" in p.prompt_files(root, p.ROOT_FOLDER, True)
    assert p.prompt_files(root, p.ROOT_FOLDER, False) == ["a.txt"]


@pytest.mark.parametrize("bad", ["../", "..", "/etc", "moody/../..", "nope", "moody/../../etc"])
def test_folder_must_come_from_the_list(root, bad):
    with pytest.raises(ValueError):
        p.prompt_files(root, bad, True)


def test_sequence_walks_in_order_and_wraps():
    files = ["1", "2", "3"]
    assert [p.pick(files, "sequence", s) for s in range(5)] == [0, 1, 2, 0, 1]


def test_random_is_seeded():
    files = [str(i) for i in range(50)]
    assert p.pick(files, "random", 7) == p.pick(files, "random", 7)
    assert len({p.pick(files, "random", s) for s in range(40)}) > 10


def test_pick_errors():
    with pytest.raises(ValueError):
        p.pick([], "random", 0)
    with pytest.raises(ValueError):
        p.pick(["a"], "shuffle", 0)


def test_read_prompt_strips_and_decodes(root):
    write(root, "moody/u.txt", "  café \n\n")
    assert p.read_prompt(root, "moody/u.txt") == "café"
    (root / "moody/bad.txt").write_bytes(b"ok \xff")
    assert p.read_prompt(root, "moody/bad.txt") == "ok �"


def test_read_refuses_symlink_fifo_and_oversize(root, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "secret.txt"
    outside.write_text("secret")
    os.symlink(outside, root / "moody/link.txt")
    with pytest.raises(ValueError):
        p.read_prompt(root, "moody/link.txt")
    os.mkfifo(root / "moody/fifo.txt")
    with pytest.raises(ValueError):
        p.read_prompt(root, "moody/fifo.txt")  # must not hang
    write(root, "moody/big.txt", "x" * (p.MAX_PROMPT_BYTES + 1))
    with pytest.raises(ValueError):
        p.read_prompt(root, "moody/big.txt")


def test_symlinked_folder_followed_and_loop_safe(root, tmp_path_factory):
    elsewhere = tmp_path_factory.mktemp("collection")
    (elsewhere / "p.txt").write_text("linked in")
    os.symlink(elsewhere, root / "linked")
    os.symlink(root, root / "moody/loop")  # a loop back to the root
    assert "linked" in p.list_folders(root)
    assert p.read_prompt(root, p.prompt_files(root, "linked", False)[0]) == "linked in"


def test_fingerprint_changes_on_edit(root):
    files = p.prompt_files(root, "moody", False)
    before = p.fingerprint(root, files)
    write(root, "moody/2.txt", "two, edited and longer")
    assert p.fingerprint(root, files) != before
