// Capture the Spotify music beat for the trailer: result with tracks + now
// playing, then the same after tapping "Lift". Album art (and the embed, which
// carries artwork) is blurred; track titles and artists stay readable (user decision).
// Usage: node trailer/src/capture_music.mjs <16x9|9x16> [outDir] [appUrl]
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [fmt = "16x9", outDir = "trailer/assets/screens", url = "http://localhost:3002"] = process.argv.slice(2);
const VIEW = fmt === "9x16" ? { w: 390, h: 844, dsf: 3, mobile: true } : { w: 1440, h: 900, dsf: 2, mobile: false };
const PORT = 9336;
mkdirSync(`${outDir}/${fmt}`, { recursive: true });

const chrome = spawn("C:/Program Files/Google/Chrome/Application/chrome.exe", [
  "--headless=new", `--remote-debugging-port=${PORT}`, "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
  "--hide-scrollbars", `--user-data-dir=${join(tmpdir(), `moodmix-music-${fmt}-${Date.now()}`)}`, "about:blank",
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
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const js = async (expr) => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
const shot = async (name) => {
  await js(`new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`);
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${outDir}/${fmt}/${name}.png`, Buffer.from(r.result.data, "base64"));
  console.log("saved", fmt, name);
};
const waitFor = (cond, ms = 180000) => js(`(async()=>{const t=Date.now();while(!(${cond})&&Date.now()-t<${ms})await new Promise(r=>setTimeout(r,250));return !!(${cond})})()`);
// Spotify on this connection sometimes drops (SSL EOF): press "Retry tracks" like a user would.
async function ensureTracks(lift = false) {
  for (let attempt = 0; attempt < 5; attempt++) {
    const ok = await waitFor(`document.querySelectorAll('.track').length >= 5${lift ? " && /lift/i.test(document.querySelector('.tracks .card-h')?.textContent||'')" : ""}`, 20000);
    if (ok) return true;
    console.log("tracks missing, retry", attempt + 1);
    await js(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>/Retry tracks/.test(x.textContent));if(b)b.click();return !!b})()`);
  }
  return false;
}
const rects = () => js(`JSON.stringify(Object.fromEntries([['player','.player'],['tracks','.tracks'],['list','.track-list']].map(([k,s])=>{const b=document.querySelector(s)?.getBoundingClientRect();return [k,b&&{x:b.x,y:b.y,w:b.width,h:b.height}]}).concat([['lift',(()=>{const b=[...document.querySelectorAll('.tracks .seg button')].find(x=>x.textContent.trim()==='Lift')?.getBoundingClientRect();return b&&{x:b.x,y:b.y,w:b.width,h:b.height}})()]])))`);

await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: VIEW.w, height: VIEW.h, deviceScaleFactor: VIEW.dsf, mobile: VIEW.mobile });
await send("Page.navigate", { url });
await waitFor("document.querySelector('.bg-gl.is-on')", 60000);
await js(`localStorage.clear(); true`);
await send("Page.navigate", { url });
await waitFor("document.querySelector('.bg-gl.is-on')", 60000);
await js(`(()=>{const s=document.createElement('style');s.textContent=\`
  .track img,.np img,.np-art,.track-noart{filter:blur(10px) saturate(.6)!important}
  .embed{filter:blur(8px)!important}
  :focus-visible{outline:none!important;box-shadow:none!important}\`;document.head.appendChild(s);return true})()`);

await js(`document.querySelector('#tab-text').click(); true`);
await sleep(300);
await js(`(()=>{const t=document.querySelector('textarea');const set=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;set.call(t,"Finally got the job. I can't stop smiling.");t.dispatchEvent(new Event('input',{bubbles:true}));return true})()`);
await sleep(200);
await js(`[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Detect')).click(); true`);
await waitFor("document.querySelector('.result-mood')");
if (!(await ensureTracks())) { console.log("FAILED: Spotify tracks never loaded"); process.exit(2); }
await sleep(6000); // let the Spotify embed load
await js(`window.scrollTo(0, document.querySelector('.player').getBoundingClientRect().top + scrollY - 70); true`);
await sleep(800);
await shot("08-music");
writeFileSync(`${outDir}/${fmt}/08-music.json`, await rects());

// Tap "Lift": the list swaps to tracks that lift the mood
await js(`[...document.querySelectorAll('.tracks .seg button')].find(x=>x.textContent.trim()==='Lift').click(); true`);
if (!(await ensureTracks(true))) { console.log("FAILED: lift tracks never loaded"); process.exit(2); }
await sleep(5000);
await js(`window.scrollTo(0, document.querySelector('.player').getBoundingClientRect().top + scrollY - 70); true`);
await sleep(800);
await shot("09-lift");
writeFileSync(`${outDir}/${fmt}/09-lift.json`, await rects());

ws.close();
chrome.kill();
process.exit(0);
