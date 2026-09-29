# Prompt Folder

A ComfyUI node that loads one prompt from a folder of `.txt` files, **at random
or in sequence**, and shows you which prompt it picked.

## Prompt From Folder

| Input | What it does |
| --- | --- |
| `folder` | A folder under `ComfyUI/input/prompts/`. Press **R** in ComfyUI to refresh the list after adding folders. |
| `include_subfolders` | Also pick from the folder's subfolders. |
| `mode` | `sequence` takes each file in name order, one per run. `random` is a seeded random pick. |
| `seed` | Sequence: the position in the list (it wraps). Random: the same seed always picks the same file. |

The seed's **control after generate** follows the mode by itself: `sequence`
sets it to *increment* (the next file every run) and `random` to *randomize*.

| Output | |
| --- | --- |
| `prompt` | The file's text, ready for a CLIP Text Encode node's `text` input. |
| `file` | The file's path within `input/prompts/`. |

After each run, a box on the node shows the file that was picked, its position
(for example `2 of 12`), and the prompt. The box is display only: it is not sent
with the prompt and is not saved with the workflow.

### Prompt files

- Each `.txt` file holds one prompt.
- Files are read as UTF-8, and leading and trailing whitespace is stripped.
- Names sort naturally, so `2.txt` comes before `10.txt`. Number your files to
  set the order.
- Hidden files and non-`.txt` files are ignored.
- To use a collection stored elsewhere, symlink its folder into
  `input/prompts/`. Symlinked folders are followed, and link loops are skipped.

If you edit a prompt file, the node notices and runs again, even with a fixed
seed.

## Safety

ComfyUI is often reachable from other machines on the network, so the node
only ever lists and reads inside `input/prompts/`:

- A folder value that is not in the current list is rejected, so `../` or
  `/etc` never reach the filesystem.
- Each file is opened without following a symlink at the file itself, without
  blocking (a FIFO cannot hang ComfyUI), and only up to 256 KB.

## Install

Clone into `ComfyUI/custom_nodes/` and restart ComfyUI. There are no Python
dependencies.

## Tests

```bash
uvx pytest -q tests                          # the folder/pick/read logic, no ComfyUI needed
python tests/ui_check.py examples sequence 1 # against a running ComfyUI; needs aiohttp
```

`ui_check.py` drives the real frontend in headless Chromium, and blocks writes
to ComfyUI settings.

## Licence

MIT
