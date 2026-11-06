// Render frames of the trailer composition with headless Chrome (CDP).
// Usage: node trailer/src/render.mjs <16x9|9x16> <frames> <outDir> [baseUrl]
//   frames: "all" | "0-749" | "60,200,400"
// Each frame is a deterministic call to window.renderFrame(f): any frame renders on its own.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [fmt = "16x9", spec = "all", outDir = "trailer/frames", base = "http://localhost:8765"] = process.argv.slice(2);
const V = fmt === "9x16" ? { w: 1080, h: 1920 } : { w: 1920, h: 1080 };
const N = Number(process.env.FRAMES || 909);
const frames = spec === "all" ? [...Array(N).keys()]
  : spec.includes("-") ? (() => { const [a, b] = spec.split("-").map(Number); return [...Array(b - a + 1).keys()].map((i) => a + i); })()
  : spec.split(",").map(Number);
const dir = join(outDir, fmt);
mkdirSync(dir, { recursive: true });

const PORT = 9335;
const chrome = spawn("C:/Program Files/Google/Chrome/Application/chrome.exe", [
  "--headless=new", `--remote-debugging-port=${PORT}`, "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
  "--hide-scrollbars", "--force-color-profile=srgb", `--user-data-dir=${join(tmpdir(), `moodmix-render-${Date.now()}`)}`, "about:blank",
]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets;
for (let i = 0; i < 120 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json(); } catch { await sleep(250); }
}
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0;
const pending = new Map();
ws.addEventListener("message", (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") console.error("EXCEPTION", JSON.stringify(m.params.exceptionDetails).slice(0, 400));
  if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") console.error("CONSOLE", m.params.args.map((a) => a.value ?? a.description).join(" "));
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const js = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400));
  return r.result?.result?.value;
};

await send("Runtime.enable");
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: V.w, height: V.h, deviceScaleFactor: 1, mobile: false });
await send("Page.navigate", { url: `${base}/src/index.html?fmt=${fmt}` });
for (let i = 0; i < 240; i++) { if (await js("typeof window.ready !== 'undefined'").catch(() => false)) break; await sleep(250); }
await js("window.ready");
const t0 = Date.now();
for (const [n, f] of frames.entries()) {
  await js(`window.renderFrame(${f})`);
  const r = await send("Page.captureScreenshot", { format: "jpeg", quality: 95, clip: { x: 0, y: 0, width: V.w, height: V.h, scale: 1 } });
  writeFileSync(join(dir, `${String(f).padStart(4, "0")}.jpg`), Buffer.from(r.result.data, "base64"));
  if (n % 25 === 0 || n === frames.length - 1) {
    const per = (Date.now() - t0) / (n + 1) / 1000;
    console.log(`frame ${f} (${n + 1}/${frames.length})  ${per.toFixed(2)} s/frame  eta ${Math.round(per * (frames.length - n - 1))} s`);
  }
}
ws.close();
chrome.kill();
process.exit(0);
