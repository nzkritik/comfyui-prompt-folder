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
import { api } from "../../scripts/api.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

const NODE = "PromptFromFolder";
const SAVER = "PromptToFolder";
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

// Shows how many prompt files the current folder holds, before any run, so
// the user knows how many runs cover every prompt once.
async function showCount(node) {
  const folder = node.widgets?.find((w) => w.name === "folder")?.value;
  const sub = !!node.widgets?.find((w) => w.name === "include_subfolders")?.value;
  if (folder === undefined) return;
  const ticket = (node._pfCountTicket = (node._pfCountTicket || 0) + 1);
  let text;
  try {
    const res = await api.fetchApi(
      `/prompt_folder/count?folder=${encodeURIComponent(folder)}&subfolders=${sub ? 1 : 0}`
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    const where = (folder === "(root)" ? "input/prompts" : folder) + (sub ? " and its subfolders" : "");
    const n = data.count;
    text = n
      ? `${n} prompt file${n === 1 ? "" : "s"} in ${where}\nQueue ${n} run${n === 1 ? "" : "s"} to use each prompt once.`
      : `No .txt prompt files in ${where}.`;
  } catch (e) {
    text = `Could not count prompt files: ${e.message || e}`;
  }
  if (ticket !== node._pfCountTicket) return; // a newer change won the race
  shownWidget(node).value = text;
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

function shownWidget(node, placeholder = "The picked prompt appears here after a run.") {
  let w = node.widgets?.find((x) => x.name === SHOWN);
  if (w) return w;
  w = ComfyWidgets.STRING(node, SHOWN, ["STRING", { multiline: true }], app).widget;
  w.options = { ...(w.options || {}), serialize: false };
  w.serialize = false;
  w.value = "";
  if (w.inputEl) {
    w.inputEl.readOnly = true;
    w.inputEl.placeholder = placeholder;
    w.inputEl.style.opacity = 0.85;
  }
  return w;
}

// Browse dialog for Prompt To Folder. The server only ever lists folders under
// input/prompts, so this can offer nothing outside that tree.
async function browseFolders(current) {
  let dirs = [];
  try {
    const res = await api.fetchApi("/prompt_folder/dirs");
    dirs = (await res.json()).dirs || [];
  } catch (e) {
    alert("Could not list the prompt folders: " + e);
    return null;
  }
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    Object.assign(overlay.style, {
      position: "fixed", inset: "0", background: "rgba(0,0,0,0.5)", zIndex: 10000,
      display: "flex", alignItems: "center", justifyContent: "center",
    });
    const box = document.createElement("div");
    Object.assign(box.style, {
      background: "var(--comfy-menu-bg, #222)", color: "var(--fg-color, #ddd)",
      border: "1px solid var(--border-color, #444)", borderRadius: "8px", padding: "14px",
      width: "min(520px, 90vw)", maxHeight: "70vh", display: "flex", flexDirection: "column", gap: "8px",
      fontFamily: "sans-serif", fontSize: "14px",
    });
    const title = document.createElement("div");
    title.textContent = "Choose a folder in input/prompts";
    title.style.fontWeight = "bold";
    const filter = document.createElement("input");
    filter.placeholder = "Filter, or type a new folder name and press Enter";
    Object.assign(filter.style, { padding: "6px", background: "var(--comfy-input-bg, #111)",
      color: "inherit", border: "1px solid var(--border-color, #444)", borderRadius: "4px" });
    const list = document.createElement("div");
    Object.assign(list.style, { overflowY: "auto", flex: "1", minHeight: "120px" });
    const close = (value) => { overlay.remove(); resolve(value); };
    const render = () => {
      list.replaceChildren();
      const q = filter.value.trim().toLowerCase();
      const shown = ["(root)", ...dirs].filter((d) => !q || d.toLowerCase().includes(q));
      for (const d of shown) {
        const row = document.createElement("div");
        row.textContent = d === "(root)" ? "(input/prompts itself)" : d;
        Object.assign(row.style, { padding: "5px 8px", cursor: "pointer", borderRadius: "4px",
          background: d === current ? "var(--comfy-input-bg, #333)" : "" });
        row.onmouseenter = () => (row.style.background = "var(--border-color, #444)");
        row.onmouseleave = () => (row.style.background = d === current ? "var(--comfy-input-bg, #333)" : "");
        row.onclick = () => close(d === "(root)" ? "" : d);
        list.appendChild(row);
      }
      if (!shown.length) {
        const empty = document.createElement("div");
        empty.textContent = q ? `Press Enter to use a new folder "${filter.value.trim()}"` : "No folders yet.";
        empty.style.opacity = 0.7;
        list.appendChild(empty);
      }
    };
    filter.oninput = render;
    filter.onkeydown = (e) => {
      if (e.key === "Escape") close(null);
      if (e.key === "Enter" && filter.value.trim()) close(filter.value.trim());
    };
    const cancel = document.createElement("button");
    cancel.textContent = "Cancel";
    cancel.onclick = () => close(null);
    overlay.onclick = (e) => { if (e.target === overlay) close(null); };
    box.append(title, filter, list, cancel);
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    render();
    filter.focus();
  });
}

function setupSaver(node) {
  const folder = node.widgets?.find((w) => w.name === "folder");
  if (folder && !node.widgets.find((w) => w.name === "browse")) {
    node.addWidget("button", "browse", "Browse…", async () => {
      const picked = await browseFolders(folder.value);
      if (picked === null) return;
      folder.value = picked;
      folder.callback?.(picked);
      node.setDirtyCanvas?.(true, true);
    }, { serialize: false });
  }
  shownWidget(node, "Where the prompt was saved appears here after a run.");
  node.setSize([Math.max(node.size[0], 380), Math.max(node.size[1], 230)]);
}

app.registerExtension({
  name: "prompt_folder.node",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE && nodeData.name !== SAVER) return;
    const saver = nodeData.name === SAVER;
    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      onExecuted?.apply(this, arguments);
      const [label, text] = message?.text ?? [];
      if (label === undefined) return;
      shownWidget(this).value = saver ? `Saved: input/prompts/${label}` : `${label}\n\n${text ?? ""}`;
      this.setDirtyCanvas?.(true, true);
    };
  },

  nodeCreated(node) {
    if (node.comfyClass === SAVER) return setupSaver(node);
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
    afterChange(node, "folder", () => { restartSequence(node); showCount(node); });
    afterChange(node, "include_subfolders", () => { restartSequence(node); showCount(node); });
    // After a saved workflow has put its values in (configure runs after this).
    setTimeout(() => showCount(node), 0);
    // A node just added gets the default mode's control; a loaded one is
    // configured after this and keeps its saved value.
    syncControl(node, mode.value);
  },
});
