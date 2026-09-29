// Prompt From Folder, frontend side.
//
// 1. The seed's "control after generate" follows the mode, so each mode does
//    what it says without a second setting: random -> randomize (a new pick
//    every run), sequence -> increment (the next file every run). Only on a
//    change of mode, or for a node just added, so a saved workflow keeps
//    whatever its seed control was saved with.
// 2. A read-only box shows the file and prompt that were picked, filled in
//    from the node's UI output after each run. It is display only: never sent
//    with the prompt and not saved with the workflow.
import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

const NODE = "PromptFromFolder";
const CONTROL_FOR = { random: "randomize", sequence: "increment" };
const SHOWN = "selected";

function seedControl(node) {
  const seed = node.widgets?.find((w) => w.name === "seed");
  return (
    seed?.linkedWidgets?.find((w) => w.name === "control_after_generate") ??
    node.widgets?.find((w) => w.name === "control_after_generate")
  );
}

function syncControl(node, mode) {
  const control = seedControl(node);
  const wanted = CONTROL_FOR[mode];
  if (!control || !wanted || control.value === wanted) return;
  control.value = wanted;
  node.setDirtyCanvas?.(true, true);
}

// In sequence mode the seed is the position in the file list, so a seed
// carried over from random mode (a huge number) or from another folder would
// start the sequence part-way through. Start it at the first file instead.
// Only on a change made in the UI: a loaded workflow, or a seed typed in by
// hand, keeps its value, so a sequence can still be resumed.
function restartSequence(node) {
  const mode = node.widgets?.find((w) => w.name === "mode");
  const seed = node.widgets?.find((w) => w.name === "seed");
  if (!seed || mode?.value !== "sequence" || seed.value === 0) return;
  seed.value = 0;
  node.setDirtyCanvas?.(true, true);
}

function afterChange(node, name, fn) {
  const w = node.widgets?.find((x) => x.name === name);
  if (!w) return;
  const original = w.callback;
  w.callback = function (value, ...rest) {
    const result = original?.call(this, value, ...rest);
    fn(value);
    return result;
  };
}

function shownWidget(node) {
  let w = node.widgets?.find((x) => x.name === SHOWN);
  if (w) return w;
  w = ComfyWidgets.STRING(node, SHOWN, ["STRING", { multiline: true }], app).widget;
  w.options = { ...(w.options || {}), serialize: false };
  w.serialize = false;
  w.value = "";
  if (w.inputEl) {
    w.inputEl.readOnly = true;
    w.inputEl.placeholder = "The picked prompt appears here after a run.";
    w.inputEl.style.opacity = 0.85;
  }
  return w;
}

app.registerExtension({
  name: "prompt_folder.node",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE) return;
    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      onExecuted?.apply(this, arguments);
      const [label, text] = message?.text ?? [];
      if (label === undefined) return;
      shownWidget(this).value = `${label}\n\n${text ?? ""}`;
      this.setDirtyCanvas?.(true, true);
    };
  },

  nodeCreated(node) {
    if (node.comfyClass !== NODE) return;
    shownWidget(node);
    // Room for the file line plus a few lines of prompt. A loaded workflow
    // is configured after this and keeps the size it was saved with.
    node.setSize([Math.max(node.size[0], 380), node.size[1] + 110]);
    const mode = node.widgets?.find((w) => w.name === "mode");
    if (!mode) return;
    afterChange(node, "mode", (value) => {
      syncControl(node, value);
      restartSequence(node);
    });
    afterChange(node, "folder", () => restartSequence(node));
    afterChange(node, "include_subfolders", () => restartSequence(node));
    // A node just added gets the default mode's control; a loaded one is
    // configured after this and keeps its saved value.
    syncControl(node, mode.value);
  },
});
