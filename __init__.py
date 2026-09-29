from typing_extensions import override

from comfy_api.latest import ComfyExtension, io

from .prompt_folder.nodes import NODES

WEB_DIRECTORY = "./js"


class PromptFolderExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return NODES


async def comfy_entrypoint() -> PromptFolderExtension:
    return PromptFolderExtension()


__all__ = ["WEB_DIRECTORY", "comfy_entrypoint"]
