// Extract the real MoodMix pieces for the trailer composition, straight from the
// app source (no hand-copied values): shader, mood ramps/motion, logo, faces.
// Usage: node trailer/src/build.mjs   ->  trailer/src/gen/data.js
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const WEB = join(here, "..", "..", "web");
const require = createRequire(join(WEB, "package.json"));
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

const gen = join(here, "gen");
mkdirSync(gen, { recursive: true });

function transpile(srcRel, outName) {
  const src = readFileSync(join(WEB, srcRel), "utf8");
  const out = ts.transpileModule(src, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const file = join(gen, outName);
  // Resolve react from the app's node_modules (a second React copy breaks hooks).
  const pin = (spec) => require.resolve(spec).split("\\").join("/");
  const fixed = out
    .replace(/require\("react\/jsx-runtime"\)/g, `require("${pin("react/jsx-runtime")}")`)
    .replace(/require\("react"\)/g, `require("${pin("react")}")`);
  writeFileSync(file, fixed);
  return file;
}

// moods.ts and MoodFace.tsx (MoodFace imports ../moods -> point it at the generated copy)
const moodsFile = transpile("app/moods.ts", "moods.cjs");
const faceFile = transpile("app/components/MoodFace.tsx", "MoodFace.cjs");
writeFileSync(faceFile, readFileSync(faceFile, "utf8").replace(/require\("\.\.\/moods"\)/g, 'require("./moods.cjs")'));
const logoFile = transpile("app/logo.tsx", "logo.cjs");

const moods = require(moodsFile);
const { MoodFace } = require(faceFile);
const { LogoMark } = require(logoFile);

const faces = Object.fromEntries(
  moods.MOODS.map((m) => [m, renderToStaticMarkup(React.createElement(MoodFace, { mood: m, size: 200 }))]),
);
const logo = renderToStaticMarkup(React.createElement(LogoMark));

const bg = readFileSync(join(WEB, "app/components/MoodBackground.tsx"), "utf8");
const frag = bg.match(/const FRAG = `([\s\S]*?)`;/)[1];
const vert = bg.match(/const VERT = "([^"]*)";/)[1];

const data = {
  moods: moods.MOODS,
  style: moods.MOOD_STYLE,
  idle: { ramp: moods.IDLE_RAMP, motion: moods.IDLE_MOTION, css: moods.IDLE_CSS },
  faces,
  logo,
  frag,
  vert,
};
writeFileSync(join(gen, "data.js"), `window.MM = ${JSON.stringify(data)};\n`);
console.log("built", Object.keys(faces).length, "faces; frag", frag.length, "chars; logo", logo.length, "chars");
