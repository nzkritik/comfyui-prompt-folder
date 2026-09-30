"""Writing prompts into the prompts tree, numbered like Save Image.

Pure functions over a root directory, so this module imports nothing from
ComfyUI and can be tested on its own.

The folder and name reaching the node come from the frontend, which anything
able to reach ComfyUI can drive, so both are treated as untrusted:

- They are cleaned into plain path components. '..', absolute paths, empty and
  '.' parts are dropped or refused, and odd characters become '_', so the
  result always stays under the root.
- New folders are created one component at a time.
- The file itself is created with O_CREAT|O_EXCL|O_NOFOLLOW, so an existing
  file, or a symlink planted at the name, is never written through. The
  number is bumped instead.

Existing folders inside the tree are followed even when they are symlinks,
the same as the reader. Only the local user can put a symlink there.
"""

import os
import re

try:
    from .prompts import natural_key
except ImportError:  # imported directly by the tests
    from prompts import natural_key

MAX_DEPTH = 8
MAX_COMPONENT = 100
MAX_PROMPT_BYTES = 256 * 1024
MAX_LISTED_DIRS = 2000
DEFAULT_NAME = "prompt"
DIGITS = 5

_UNSAFE = re.compile(r"[^\w .,+()@#&'!=~-]", re.UNICODE)


def clean_parts(value):
    """Untrusted 'a/b/c' text -> safe path components, or ValueError."""
    parts = []
    for raw in re.split(r"[\\/]+", str(value or "")):
        part = raw.strip()
        if part in ("", "."):
            continue
        if part == "..":
            raise ValueError("'..' is not allowed in a folder or name")
        part = _UNSAFE.sub("_", part.replace(":", "_")).strip(" .")
        if not part:
            continue
        parts.append(part[:MAX_COMPONENT])
    if len(parts) > MAX_DEPTH:
        raise ValueError(f"too many folder levels (at most {MAX_DEPTH})")
    return parts


def list_dirs(root):
    """Every folder under root, relative with '/', for the Browse dialog."""
    out, seen = [], set()
    root = os.path.abspath(root)
    for dirpath, dirnames, _ in os.walk(root, followlinks=True):
        real = os.path.realpath(dirpath)
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if real in seen or depth > MAX_DEPTH:
            dirnames[:] = []
            continue
        seen.add(real)
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if rel != ".":
            out.append(rel.replace(os.sep, "/"))
            if len(out) >= MAX_LISTED_DIRS:
                break
    return sorted(out, key=natural_key)


def _ensure_dirs(root, parts):
    path = root
    for part in parts:
        path = os.path.join(path, part)
        try:
            os.mkdir(path)
        except FileExistsError:
            if not os.path.isdir(path):
                raise ValueError(f"'{part}' exists and is not a folder") from None
    return path


def next_number(directory, prefix):
    """One past the highest prefix_NNNNN.txt already there, like Save Image."""
    pattern = re.compile(re.escape(prefix) + r"_(\d+)\.txt$", re.IGNORECASE)
    highest = 0
    try:
        for name in os.listdir(directory):
            m = pattern.match(name)
            if m:
                highest = max(highest, int(m.group(1)))
    except OSError:
        pass
    return highest + 1


def save_prompt(root, folder, name, text):
    """Write text to root/folder/name_NNNNN.txt; returns the path relative to root."""
    data = (str(text).strip() + "\n").encode("utf-8")
    if not str(text).strip():
        raise ValueError("the prompt is empty; nothing to save")
    if len(data) > MAX_PROMPT_BYTES:
        raise ValueError(f"the prompt is {len(data)} bytes; the limit is {MAX_PROMPT_BYTES}")
    folder_parts = clean_parts(folder)
    name_parts = clean_parts(name) or [DEFAULT_NAME]
    if len(folder_parts) + len(name_parts) > MAX_DEPTH + 1:
        raise ValueError(f"too many folder levels (at most {MAX_DEPTH})")
    prefix = name_parts[-1]
    directory = _ensure_dirs(os.path.abspath(root), folder_parts + name_parts[:-1])
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    number = next_number(directory, prefix)
    for _ in range(1000):
        filename = f"{prefix}_{number:0{DIGITS}d}.txt"
        path = os.path.join(directory, filename)
        try:
            fd = os.open(path, flags, 0o644)
        except FileExistsError:
            number += 1
            continue
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
        return "/".join(folder_parts + name_parts[:-1] + [filename])
    raise ValueError(f"could not find a free file name for {prefix} in {directory}")
