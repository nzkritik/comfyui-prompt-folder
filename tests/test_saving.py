import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "prompt_folder"))
import saving as s  # noqa: E402


def read(root, rel):
    return (root / rel).read_text()


def test_numbers_like_save_image(tmp_path):
    assert s.save_prompt(tmp_path, "saved", "rain", "a") == "saved/rain_00001.txt"
    assert s.save_prompt(tmp_path, "saved", "rain", "b") == "saved/rain_00002.txt"
    assert read(tmp_path, "saved/rain_00002.txt") == "b\n"


def test_default_name_and_root_folder(tmp_path):
    assert s.save_prompt(tmp_path, "", None, "x") == "prompt_00001.txt"
    assert s.save_prompt(tmp_path, "saved", "", "y") == "saved/prompt_00001.txt"


def test_continues_after_highest_and_never_overwrites(tmp_path):
    (tmp_path / "saved").mkdir()
    (tmp_path / "saved/rain_00007.txt").write_text("keep")
    assert s.save_prompt(tmp_path, "saved", "rain", "new") == "saved/rain_00008.txt"
    assert read(tmp_path, "saved/rain_00007.txt") == "keep"


def test_name_with_slashes_makes_subfolders_and_cleans_colons(tmp_path):
    rel = s.save_prompt(tmp_path, "saved", "ZI-Natalia:1+Noir:0.8/2026-09-30_1715", "p")
    assert rel == "saved/ZI-Natalia_1+Noir_0.8/2026-09-30_1715_00001.txt"


@pytest.mark.parametrize("folder", ["../", "..", "a/../../b", "..\\..\\etc"])
def test_dotdot_refused(tmp_path, folder):
    with pytest.raises(ValueError):
        s.save_prompt(tmp_path, folder, None, "x")


@pytest.mark.parametrize("folder, expect", [("/etc", "etc"), ("///tmp//x", "tmp/x"), ("C:\\Windows", "C_/Windows")])
def test_absolute_paths_are_confined_under_root(tmp_path, folder, expect):
    rel = s.save_prompt(tmp_path, folder, "n", "x")
    assert rel == f"{expect}/n_00001.txt"
    assert (tmp_path / rel).is_file()


def test_name_cannot_escape(tmp_path):
    with pytest.raises(ValueError):
        s.save_prompt(tmp_path, "saved", "../../evil", "x")
    assert s.save_prompt(tmp_path, "saved", "/abs/evil", "x") == "saved/abs/evil_00001.txt"


def test_planted_symlink_at_target_is_not_written_through(tmp_path, tmp_path_factory):
    victim = tmp_path_factory.mktemp("victim") / "important.txt"
    victim.write_text("original")
    (tmp_path / "saved").mkdir()
    os.symlink(victim, tmp_path / "saved/rain_00001.txt")
    assert s.save_prompt(tmp_path, "saved", "rain", "x") == "saved/rain_00002.txt"
    assert victim.read_text() == "original"


def test_file_where_a_folder_should_be(tmp_path):
    (tmp_path / "saved").write_text("not a folder")
    with pytest.raises(ValueError):
        s.save_prompt(tmp_path, "saved", "n", "x")


def test_empty_and_oversized_prompts(tmp_path):
    with pytest.raises(ValueError):
        s.save_prompt(tmp_path, "saved", "n", "   ")
    with pytest.raises(ValueError):
        s.save_prompt(tmp_path, "saved", "n", "x" * (s.MAX_PROMPT_BYTES + 1))


def test_too_deep(tmp_path):
    with pytest.raises(ValueError):
        s.save_prompt(tmp_path, "/".join("abcdefghij"), "n", "x")


def test_list_dirs_only_under_root_and_loop_safe(tmp_path):
    (tmp_path / "saved/portraits").mkdir(parents=True)
    (tmp_path / "anime").mkdir()
    (tmp_path / ".hidden").mkdir()
    os.symlink(tmp_path, tmp_path / "anime/loop")
    dirs = s.list_dirs(tmp_path)
    assert dirs == ["anime", "saved", "saved/portraits"]  # the loop back to root is not listed again
    assert not any(d.startswith(".hidden") for d in dirs)
    assert all(not d.startswith("/") and ".." not in d for d in dirs)


def test_saved_prompt_is_readable_by_the_loader(tmp_path):
    import prompts
    s.save_prompt(tmp_path, "saved", "a", "first")
    s.save_prompt(tmp_path, "saved", "a", "second")
    files = prompts.prompt_files(tmp_path, "saved", False)
    assert [prompts.read_prompt(tmp_path, f) for f in files] == ["first", "second"]


@pytest.mark.parametrize("name, expect", [("CON", "_CON"), ("nul", "_nul"), ("com1", "_com1"), ("Lpt9.txt", "_Lpt9.txt"),
                                          ("console", "console"), ("aux2", "aux2")])
def test_windows_reserved_names(tmp_path, name, expect):
    assert s.clean_parts(f"saved/{name}") == ["saved", expect]

