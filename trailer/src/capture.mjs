// Capture real MoodMix UI states for the trailer (headless Chrome over CDP).
// Usage: node trailer/src/capture.mjs <16x9|9x16> <outDir> [appUrl]
// Third-party content (album art, track titles/artists, Spotify embed) is
// blurred before every screenshot. Nothing on screen is invented.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [fmt = "16x9", outDir = "trailer/assets/screens", url = "http://localhost:3002"] = process.argv.slice(2);
const VIEW = fmt === "9x16" ? { w: 390, h: 844, dsf: 3, mobile: true } : { w: 1440, h: 900, dsf: 2, mobile: false };
const PORT = 9334;
mkdirSync(`${outDir}/${fmt}`, { recursive: true });

const chrome = spawn("C:/Program Files/Google/Chrome/Application/chrome.exe", [
  "--headless=new", `--remote-debugging-port=${PORT}`, "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
  "--hide-scrollbars", `--user-data-dir=${join(tmpdir(), `moodmix-capture-${fmt}-${Date.now()}`)}`, "about:blank",
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
  if (m.method === "Runtime.exceptionThrown") console.error("EXCEPTION", m.params.exceptionDetails.text);
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const js = async (expr) => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
const shot = async (name) => {
  await js(`new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`);
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(`${outDir}/${fmt}/${name}.png`, Buffer.from(r.result.data, "base64"));
  console.log("saved", fmt, name);
};
const waitFor = (sel, ms = 180000) => js(`(async()=>{const t=Date.now();while(!document.querySelector(${JSON.stringify(sel)})&&Date.now()-t<${ms})await new Promise(r=>setTimeout(r,250));return !!document.querySelector(${JSON.stringify(sel)})})()`);

await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: VIEW.w, height: VIEW.h, deviceScaleFactor: VIEW.dsf, mobile: VIEW.mobile });
// Clean slate: no saved history / mode from earlier sessions on this origin.
await send("Page.navigate", { url });
await waitFor(".bg-gl.is-on", 60000);
await js(`localStorage.clear(); true`);
await send("Page.navigate", { url });
await waitFor(".bg-gl.is-on", 60000);
// Blur third-party content; hide the pause button's focus etc. (style only).
await js(`(()=>{const s=document.createElement('style');s.textContent=\`
  .track img,.np img,.np-art,.track-noart{filter:blur(10px) saturate(.6)!important}
  .track-meta,.np-meta{filter:blur(5px)!important}
  .embed{filter:blur(8px)!important}
  :focus-visible{outline:none!important;box-shadow:none!important}\`;document.head.appendChild(s);return true})()`);
await sleep(1200);

// 1. Idle (voice)
await shot("01-idle");

// 2. Typing (text tab), progressive
const SENTENCE = "Finally got the job. I can't stop smiling.";
await js(`document.querySelector('#tab-text').click(); true`);
await sleep(400);
const steps = [0, 9, 17, 25, 33, SENTENCE.length];
for (const [i, n] of steps.entries()) {
  await js(`(()=>{const t=document.querySelector('textarea');const set=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;set.call(t, ${JSON.stringify(SENTENCE)}.slice(0, ${n}));t.dispatchEvent(new Event('input',{bubbles:true}));return true})()`);
  await sleep(150);
  await shot(`02-typing-${i}`);
}

// 3. Analyzing (button state) then the real result
await js(`[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Detect')).click(); true`);
await sleep(250);
await shot("03-analyzing");
await waitFor(".result-mood");
// let tracks load (they may arrive in a follow-up request)
await js(`(async()=>{const t=Date.now();while(!document.querySelector('.track')&&Date.now()-t<30000)await new Promise(r=>setTimeout(r,250));return true})()`);
await sleep(1500);
const happy = await js(`JSON.stringify({mood:document.querySelector('.result-mood')?.textContent, meta:document.querySelector('.result-meta')?.textContent, rows:[...document.querySelectorAll('.breakdown li')].map(l=>l.textContent)})`);
console.log("RESULT", happy);
writeFileSync(`${outDir}/${fmt}/04-result.json`, happy);
await js(`window.scrollTo(0,0); true`);
await sleep(300);
await shot("04-result");

// 5. Correction chip -> sad (scroll the chips into view first)
await js(`document.querySelector('.correct').scrollIntoView({block:'center'}); true`);
await sleep(500);
await shot("05-chips-before");
const chipBox = await js(`JSON.stringify((()=>{const b=[...document.querySelectorAll('.chip')].find(c=>c.textContent==='Sad').getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height,vw:innerWidth,vh:innerHeight}})())`);
writeFileSync(`${outDir}/${fmt}/05-chip-box.json`, chipBox);
await js(`[...document.querySelectorAll('.chip')].find(c=>c.textContent==='Sad').click(); true`);
await sleep(2500); // background blends ~1s
await shot("06-chips-after");
await js(`window.scrollTo(0,0); true`);
await sleep(600);
await shot("07-result-sad");

ws.close();
chrome.kill();
process.exit(0);
