# Prompt Folder

ComfyUI nodes for folders of `.txt` prompts. **Prompt From Folder** loads one prompt,
at random or in sequence, and shows you which prompt it picked. **Prompt To Folder**
saves prompts into those folders.

## Prompt From Folder

| Input | What it does |
| --- | --- |
| `folder` | A folder under `ComfyUI/input/prompts/`. Press **R** in ComfyUI to refresh the list after adding folders. |
| `include_subfolders` | Also pick from the folder's subfolders. |
| `mode` | `sequence` takes each file in name order, one per run. `random` is a seeded random pick. |
| `seed` | Sequence: the position in the list (it wraps). Random: the same seed always picks the same file. |

The seed's **control after generate** follows the mode by itself: `sequence`
sets it to *increment* (the next file every run) and `random` to *randomize*.

In `sequence` mode the seed is the position in the list, starting at 0. It goes
back to 0, the first file, whenever you switch the mode to `sequence`, pick
another folder, or toggle `include_subfolders`, so a sequence never starts part
way through a folder. A seed you type in yourself, or one saved in a workflow,
is kept, so you can resume a sequence where you left off.

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

## Prompt To Folder

Saves a prompt as a numbered `.txt` file, ready for Prompt From Folder to load
later.

| Input | What it does |
| --- | --- |
| `prompt` | The text to save. Connect the same string you send to CLIP Text Encode. |
| `folder` | A folder under `ComfyUI/input/prompts/`. Type a name (a new one is created), or use **Browse…** to pick an existing one. |
| `name` *(optional)* | The file name prefix, numbered like Save Image: `name_00001.txt`, `name_00002.txt`, and so on. A `/` in the name makes subfolders. Defaults to `prompt`. |

It never overwrites a file; it takes the next free number instead. It saves on
every run, even when the prompt has not changed. A box on the node shows where
the last prompt was saved, and the `file` output gives the same path.

Everything is written inside `input/prompts/`:

- `..` is refused.
- Absolute paths such as `/etc` become ordinary subfolders under
  `input/prompts/`.
- Characters that are unsafe in file names, including `:`, become `_`.
- Files are created exclusively and without following symlinks, so a symlink
  planted at the target is never written through.
- The Browse dialog lists only folders under `input/prompts/`.

## Example workflow

`example_workflows/Prompt From Folder - Z-Image Turbo.json` is ComfyUI's standard
**Z-Image Turbo** template, unchanged, with its prompt coming from Prompt From Folder.

1. Copy `example_prompts/` to `ComfyUI/input/prompts/examples/`.
2. Load the workflow and press **R** so the folder list includes `examples`.
3. Run it. In `sequence` mode each run takes the next prompt.

It uses the template's own model files (`z_image_turbo_bf16`, `qwen_3_4b`, `ae`).
Download links are in the workflow's model note.

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
python tests/ui_check.py examples sequence 1 # against a running, idle ComfyUI; needs aiohttp
```

`ui_check.py` drives the real frontend in headless Chromium, and blocks writes
to ComfyUI settings.

## Licence

MIT
