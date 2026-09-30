"""Listing prompt folders and picking a prompt file from one.

Pure functions over a root directory, so this module imports nothing from
ComfyUI and can be tested on its own. Everything is confined to the root: the
folder value reaching the node comes from the frontend, which is reachable by
anything that can reach ComfyUI, so it is only ever matched against the list
this module built, never joined onto the root as a path.
"""

import os
import random
import re
import stat

ROOT_FOLDER = "(root)"
MODES = ("random", "sequence")
EXTENSION = ".txt"

# Bounds on what a folder scan and a prompt read will take on.
MAX_DEPTH = 8
MAX_FILES = 10000
MAX_PROMPT_BYTES = 256 * 1024


def natural_key(name):
    """Sort '2.txt' before '10.txt', ignoring case."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def _scan(root):
    """(folder, [files]) for every folder under root holding .txt files.

    Folder and file names are relative to root with '/' separators. Symlinked
    folders are followed, so existing prompt collections can be linked in, but
    each real directory is visited once, which stops link loops.
    """
    found = {}
    seen = set()
    count = 0
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        real = os.path.realpath(dirpath)
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if real in seen or depth > MAX_DEPTH:
            dirnames[:] = []
            continue
        seen.add(real)
        dirnames[:] = sorted((d for d in dirnames if not d.startswith(".")), key=natural_key)
        folder = "" if rel == "." else rel.replace(os.sep, "/")
        txts = sorted((f for f in filenames if f.lower().endswith(EXTENSION) and not f.startswith(".")),
                      key=natural_key)
        if txts:
            found[folder] = txts
            count += len(txts)
            if count >= MAX_FILES:
                break
    return found


def _folders_of(scan):
    """Every folder holding prompts, and every folder above one."""
    folders = set()
    for folder in scan:
        while folder:
            folders.add(folder)
            folder = folder.rsplit("/", 1)[0] if "/" in folder else ""
    return folders


def list_folders(root):
    """The dropdown: (root) first, then every prompt folder in natural order."""
    return [ROOT_FOLDER] + sorted(_folders_of(_scan(root)), key=natural_key)


def prompt_files(root, folder, include_subfolders):
    """The prompt files a pick chooses from, as paths relative to root, in natural order.

    Raises ValueError for a folder that is not one list_folders would offer.
    One scan serves both that check and the file list.
    """
    scan = _scan(root)
    if folder != ROOT_FOLDER and folder not in _folders_of(scan):
        raise ValueError(f"'{folder}' is not a prompt folder under {root}")
    target = "" if folder == ROOT_FOLDER else folder.strip("/")
    out = []
    for f, files in scan.items():
        if f == target or (include_subfolders and (target == "" or f.startswith(target + "/"))):
            out.extend(f"{f}/{name}" if f else name for name in files)
    return sorted(out, key=natural_key)


def pick(files, mode, seed):
    """Index into files: sequence walks them in order, random is a seeded pick."""
    if not files:
        raise ValueError("no prompt files to choose from")
    if mode == "sequence":
        return seed % len(files)
    if mode == "random":
        return random.Random(seed).randrange(len(files))
    raise ValueError(f"unknown mode {mode!r}")


def read_prompt(root, relpath):
    """The text of one prompt file, stripped.

    The file itself must be a regular file reached without a symlink at the last
    step, and is read without blocking (a FIFO planted in the folder cannot hang
    the ComfyUI process) and only up to MAX_PROMPT_BYTES.
    """
    path = os.path.join(root, *relpath.split("/"))
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise ValueError(f"cannot open {relpath}: {e.strerror}") from None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError(f"{relpath} is not a regular file")
        if st.st_size > MAX_PROMPT_BYTES:
            raise ValueError(f"{relpath} is {st.st_size} bytes; prompts are limited to {MAX_PROMPT_BYTES}")
        data = os.read(fd, MAX_PROMPT_BYTES + 1)
    finally:
        os.close(fd)
    return data.decode("utf-8", errors="replace").strip()


def fingerprint(root, files):
    """Changes whenever a candidate file is added, removed or edited."""
    out = []
    for rel in files:
        try:
            st = os.stat(os.path.join(root, *rel.split("/")))
            out.append((rel, st.st_mtime_ns, st.st_size))
        except OSError:
            out.append((rel, None, None))
    return tuple(out)
