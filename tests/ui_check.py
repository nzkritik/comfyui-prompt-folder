"""Frontend check against a running ComfyUI (headless Chromium over CDP).

Adds a Prompt From Folder node feeding a PreviewAny, checks the display box
exists and is not sent with the prompt, queues the graph, and checks the box
then shows the picked file and prompt. Settings/userdata writes are blocked so
the user's ComfyUI settings are not touched. Needs aiohttp (ComfyUI's venv).

    python tests/ui_check.py [folder] [mode] [seed]
"""
import asyncio, json, subprocess, sys, tempfile

import aiohttp

URL = "http://127.0.0.1:8188"
FOLDER, MODE, SEED = (sys.argv[1:] + ["examples", "sequence", "1"])[:3]

JS = f"""(async () => {{
  const graph = app.graph;
  graph.clear();
  const n = LiteGraph.createNode("PromptFromFolder");
  graph.add(n); n.pos = [100, 100];
  const p = LiteGraph.createNode("PreviewAny");
  graph.add(p); p.pos = [600, 100];
  n.connect(0, p, 0);
  const w = (name) => n.widgets.find(x => x.name === name);
  w("folder").value = {json.dumps(FOLDER)};
  w("mode").value = {json.dumps(MODE)};
  w("mode").callback?.({json.dumps(MODE)});
  w("seed").value = {int(SEED)};
  const control = n.widgets.find(x => x.name === "control_after_generate");
  const shown = w("selected");
  const before = shown ? shown.value : null;
  const prompt = (await app.graphToPrompt()).output;
  const sent = Object.keys(prompt[String(n.id)].inputs);
  control.value = "fixed";
  await app.queuePrompt(0, 1);
  for (let i = 0; i < 100 && !(shown && shown.value); i++) await new Promise(r => setTimeout(r, 200));
  return JSON.stringify({{has_box: !!shown, readonly: !!shown?.inputEl?.readOnly, before, sent,
                          control_for_mode: null, after: shown?.value ?? null}});
}})()"""

CONTROL_JS = """(() => {
  const n = LiteGraph.createNode("PromptFromFolder"); app.graph.add(n);
  const mode = n.widgets.find(x => x.name === "mode");
  const ctl = () => n.widgets.find(x => x.name === "control_after_generate").value;
  const out = {initial: [mode.value, ctl()]};
  mode.value = "random"; mode.callback?.("random"); out.random = ctl();
  mode.value = "sequence"; mode.callback?.("sequence"); out.sequence = ctl();
  app.graph.remove(n);
  return JSON.stringify(out);
})()"""


async def main():
    prof = tempfile.mkdtemp(prefix="cdp-")
    proc = subprocess.Popen(["chromium", "--headless=new", "--remote-debugging-port=9334", f"--user-data-dir={prof}",
                             "--window-size=1600,1000", "--no-first-run", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        async with aiohttp.ClientSession() as s:
            for _ in range(50):
                try:
                    tabs = await (await s.get("http://127.0.0.1:9334/json")).json(); break
                except Exception:
                    await asyncio.sleep(0.2)
            ws_url = next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"]
            async with s.ws_connect(ws_url, max_msg_size=0) as ws:
                mid, pending, errors = 0, {}, []

                async def send(method, **params):
                    nonlocal mid
                    mid += 1
                    f = asyncio.get_event_loop().create_future(); pending[mid] = f
                    await ws.send_str(json.dumps({"id": mid, "method": method, "params": params}))
                    return (await f).get("result", {})

                async def reader():
                    async for msg in ws:
                        d = json.loads(msg.data)
                        if "id" in d and d["id"] in pending:
                            pending.pop(d["id"]).set_result(d)
                        elif d.get("method") == "Fetch.requestPaused":
                            p = d["params"]; req = p["request"]
                            if req["method"] != "GET" and any(x in req["url"] for x in ("/settings", "/userdata")):
                                asyncio.ensure_future(send("Fetch.failRequest", requestId=p["requestId"], errorReason="BlockedByClient"))
                            else:
                                asyncio.ensure_future(send("Fetch.continueRequest", requestId=p["requestId"]))
                        elif d.get("method") == "Runtime.exceptionThrown":
                            errors.append(str(d["params"]["exceptionDetails"].get("exception", {}).get("description", ""))[:300])

                asyncio.ensure_future(reader())
                await send("Fetch.enable", patterns=[{"urlPattern": "*", "requestStage": "Request"}])
                await send("Runtime.enable")
                await send("Page.navigate", url=URL)

                async def ev(expr):
                    r = await send("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True, timeout=60000)
                    if r.get("exceptionDetails"):
                        raise RuntimeError(json.dumps(r["exceptionDetails"])[:1200])
                    return r["result"].get("value")

                for _ in range(120):
                    try:
                        if await ev("!!(window.app && app.graph && window.LiteGraph)"): break
                    except Exception:
                        pass
                    await asyncio.sleep(0.5)
                await asyncio.sleep(2)
                print("seed control follows mode:", await ev(CONTROL_JS))
                r = json.loads(await ev(JS))
                print("display box present:", r["has_box"], "| read-only:", r["readonly"])
                print("inputs sent with the prompt:", r["sent"])
                print("box after run:", json.dumps(r["after"])[:220])
                shot = await send("Page.captureScreenshot", format="png", clip={"x": 0, "y": 0, "width": 1100, "height": 600, "scale": 1})
                import base64
                open("/tmp/prompt_folder_ui.png", "wb").write(base64.b64decode(shot["data"]))
                for e in errors:
                    if "prompt_folder" in e or "PromptFromFolder" in e:
                        print("JS error:", e)
    finally:
        proc.terminate(); proc.wait()


asyncio.run(main())
