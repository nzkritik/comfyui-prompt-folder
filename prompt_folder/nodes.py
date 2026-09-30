"""Prompt From Folder (load a prompt from a folder of .txt files, at random or in sequence)
and Prompt To Folder (save a prompt as a numbered .txt file for it).

Written against ComfyUI's V3 node API (comfy_api.latest).
"""

import os
import time

import folder_paths
from aiohttp import web
from comfy_api.latest import io
from server import PromptServer

from . import prompts, saving

CATEGORY = "utils/Prompt Folder"

MODE_TOOLTIP = "random: a seeded random pick. sequence: each prompt in file-name order, one per run."
SEED_TOOLTIP = ("Random: the same seed always picks the same prompt. Sequence: the position in the "
                "sorted list, so set this to increment to take the next prompt on every run.")


def prompts_root():
    """ComfyUI/input/prompts, created on first use so the dropdown has somewhere to look."""
    root = os.path.join(folder_paths.get_input_directory(), "prompts")
    os.makedirs(root, exist_ok=True)
    return root


class PromptFromFolder(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="PromptFromFolder",
            display_name="Prompt From Folder",
            category=CATEGORY,
            description=("Load one prompt from a folder of .txt files in ComfyUI/input/prompts, "
                         "at random or in sequence. Press R to refresh the folder list."),
            inputs=[
                io.Combo.Input("folder", options=prompts.list_folders(prompts_root()),
                               tooltip="A folder under ComfyUI/input/prompts. Symlinked folders work too."),
                io.Boolean.Input("include_subfolders", default=False),
                io.Combo.Input("mode", options=list(prompts.MODES), default="sequence", tooltip=MODE_TOOLTIP),
                io.Int.Input("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF, control_after_generate=True,
                             tooltip=SEED_TOOLTIP),
            ],
            outputs=[io.String.Output("prompt"), io.String.Output("file")],
        )

    @classmethod
    def fingerprint_inputs(cls, folder, include_subfolders, mode, seed):
        # Re-run when the folder's files change, not only when the inputs do.
        try:
            return prompts.fingerprint(prompts_root(), prompts.prompt_files(prompts_root(), folder, include_subfolders))
        except ValueError:
            return None

    @classmethod
    def execute(cls, folder, include_subfolders, mode, seed):
        root = prompts_root()
        files = prompts.prompt_files(root, folder, include_subfolders)
        if not files:
            where = folder + (" or its subfolders" if include_subfolders else "")
            raise ValueError(f"No .txt prompt files in {where} (under {root}).")
        index = prompts.pick(files, mode, seed)
        name = files[index]
        text = prompts.read_prompt(root, name)
        label = f"{name}  ({index + 1} of {len(files)})"
        return io.NodeOutput(text, name, ui={"text": [label, text]})


class PromptToFolder(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="PromptToFolder",
            display_name="Prompt To Folder",
            category=CATEGORY,
            description=("Save a prompt as a numbered .txt file in a folder under ComfyUI/input/prompts, "
                         "ready for Prompt From Folder. Never overwrites: name_00001.txt, name_00002.txt, ..."),
            is_output_node=True,
            inputs=[
                io.String.Input("prompt", force_input=True, tooltip="The text to save."),
                io.String.Input("folder", default="saved",
                                tooltip=("A folder under ComfyUI/input/prompts, e.g. 'saved' or 'saved/portraits'. "
                                         "Created if missing. Use Browse to pick an existing one.")),
                io.String.Input("name", optional=True, force_input=True,
                                tooltip=("File name prefix, numbered like Save Image (name_00001.txt). "
                                         "A '/' makes subfolders. Defaults to 'prompt'.")),
            ],
            outputs=[io.String.Output("file")],
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        # A save node: write on every run, even when the prompt is unchanged.
        return time.time_ns()

    @classmethod
    def execute(cls, prompt, folder, name=None):
        rel = saving.save_prompt(prompts_root(), folder, name, prompt)
        return io.NodeOutput(rel, ui={"text": [rel]})


NODES = [PromptFromFolder, PromptToFolder]


# Browse dialog: the folders under input/prompts, and nothing else.
@PromptServer.instance.routes.get("/prompt_folder/dirs")
async def list_prompt_dirs(request):
    return web.json_response({"root": "input/prompts", "dirs": saving.list_dirs(prompts_root())})
