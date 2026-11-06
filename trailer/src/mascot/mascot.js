// Moodie, the MoodMix mascot: a round mood buddy with headphones.
// One function draws every expression/pose as an SVG string, so the same code
// can drive the character sheet, the trailer animation and (later) the app.
//
// mascotSVG({ expr, color, squash, tilt, blink, look, extras })
//   expr:   neutral | listening | happy | sad | angry | calm | fearful | surprised | disgusted | vibing
//   color:  body fill (lilac at rest, the mood colour when it feels something)
//   squash: 0 = rest, +0.1 = squashed (landing), -0.1 = stretched (jump)
//   tilt:   degrees (head bob / vibing)
//   blink:  0..1 eyelid closure (for animation)
//   look:   [-1..1, -1..1] pupil offset
//   arms:   [leftDeg, rightDeg] rotation from the shoulder; 0 = hanging down,
//           90 = straight out, 160 = raised (wave/cheer). Default [12, 12].
//   extras: show the pose props (waves, tears, notes...) — default true

(function (root) {
  const INK = "#1A1712";

  function shade(hex, amt) {
    const n = parseInt(hex.slice(1), 16);
    const ch = (s) => Math.max(0, Math.min(255, Math.round(((n >> s) & 255) * (1 + amt))));
    return "#" + [16, 8, 0].map((s) => ch(s).toString(16).padStart(2, "0")).join("");
  }

  // ---- eyes -----------------------------------------------------------------
  function dotEyes({ blink = 0, look = [0, 0], r = 6.5, y = 116, gap = 26 }) {
    const lx = look[0] * 2.5, ly = look[1] * 2.5;
    const ry = r * (1 - 0.9 * blink);
    return [-1, 1].map((s) => `
      <ellipse cx="${100 + s * gap + lx}" cy="${y + ly}" rx="${r}" ry="${ry}" fill="${INK}"/>
      ${blink < 0.5 ? `<circle cx="${100 + s * gap + lx + 2}" cy="${y + ly - 2.4}" r="1.9" fill="#fff" opacity=".9"/>` : ""}`).join("");
  }
  const arcEyes = (dir = "up", y = 117, gap = 26) => [-1, 1].map((s) => {
    const x = 100 + s * gap;
    return dir === "up"
      ? `<path d="M${x - 8} ${y + 3} Q${x} ${y - 7} ${x + 8} ${y + 3}" stroke="${INK}" stroke-width="4.2" fill="none" stroke-linecap="round"/>`
      : `<path d="M${x - 8} ${y - 2} Q${x} ${y + 7} ${x + 8} ${y - 2}" stroke="${INK}" stroke-width="4.2" fill="none" stroke-linecap="round"/>`;
  }).join("");
  const wideEyes = (look = [0, 0]) => [-1, 1].map((s) => {
    const x = 100 + s * 27;
    return `<ellipse cx="${x}" cy="114" rx="10.5" ry="12" fill="#fff" stroke="${INK}" stroke-width="3"/>
            <circle cx="${x + look[0] * 3}" cy="${116 + look[1] * 3}" r="4.2" fill="${INK}"/>`;
  }).join("");
  const brows = (kind) => {
    const L = { angry: "M66 98 L88 106", fearful: "M66 104 L88 97", surprised: "M66 96 Q77 89 88 96", sad: "M68 104 L88 99", disgusted: "M66 100 L88 105" }[kind];
    const R = { angry: "M134 98 L112 106", fearful: "M134 104 L112 97", surprised: "M112 96 Q123 89 134 96", sad: "M132 104 L112 99", disgusted: "M112 104 L134 101" }[kind];
    return L ? `<path d="${L}" stroke="${INK}" stroke-width="4.2" stroke-linecap="round" fill="none"/><path d="${R}" stroke="${INK}" stroke-width="4.2" stroke-linecap="round" fill="none"/>` : "";
  };

  // ---- mouths ---------------------------------------------------------------
  const stroke = `stroke="${INK}" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round" fill="none"`;
  const mouths = {
    smile: `<path d="M88 140 Q100 150 112 140" ${stroke}/>`,
    grin: `<path d="M84 137 Q100 162 116 137 Z" fill="${INK}"/><path d="M92 150 Q100 156 108 150 Q100 146 92 150Z" fill="#FF8FA3"/>`,
    frown: `<path d="M88 150 Q100 139 112 150" ${stroke}/>`,
    angry: `<path d="M86 150 Q100 142 114 150" ${stroke}/><path d="M92 147 L108 147" stroke="${INK}" stroke-width="2" opacity=".0"/>`,
    calm: `<path d="M90 141 Q100 147 110 141" ${stroke}/>`,
    wavy: `<path d="M84 147 q4 -5 8 0 t8 0 t8 0 t8 0" ${stroke}/>`,
    o: `<ellipse cx="100" cy="146" rx="7" ry="9" fill="${INK}"/>`,
    zigzag: `<path d="M84 148 l6 -5 l6 5 l6 -5 l6 5 l6 -5" ${stroke}/>`,
  };

  const blush = (o = 0.55) => `<ellipse cx="66" cy="134" rx="9" ry="5.5" fill="#FF8FA3" opacity="${o}"/>
                               <ellipse cx="134" cy="134" rx="9" ry="5.5" fill="#FF8FA3" opacity="${o}"/>`;

  // ---- props ----------------------------------------------------------------
  const waves = (o = 1) => `<g stroke="${INK}" stroke-width="3.5" fill="none" stroke-linecap="round" opacity="${o}">
      <path d="M14 104 Q8 117 14 130"/><path d="M5 98 Q-3 117 5 136"/>
      <path d="M186 104 Q192 117 186 130"/><path d="M195 98 Q203 117 195 136"/></g>`;
  const note = (x, y, s = 1, r = 0) => `<g transform="translate(${x} ${y}) rotate(${r}) scale(${s})" fill="${INK}">
      <ellipse cx="0" cy="14" rx="6.5" ry="5" transform="rotate(-20 0 14)"/><rect x="5" y="-10" width="2.8" height="25" rx="1.4"/>
      <path d="M7.8 -10 q10 3 10 13 q-3 -6 -10 -6z"/></g>`;
  const tear = `<path d="M128 124 q-5 9 0 13 q5 -4 0 -13z" fill="#7FC3FF" stroke="${INK}" stroke-width="1.5"/>`;
  const sweat = `<path d="M156 78 q-6 10 0 14 q6 -4 0 -14z" fill="#9FD8FF" stroke="${INK}" stroke-width="1.5"/>`;
  const steam = `<g fill="none" stroke="${INK}" stroke-width="3" stroke-linecap="round"><path d="M46 52 q-6 -8 0 -16"/><path d="M154 52 q6 -8 0 -16"/></g>`;
  const spark = `<g stroke="${INK}" stroke-width="3.5" stroke-linecap="round"><path d="M100 22 v14"/><path d="M70 32 l7 10"/><path d="M130 32 l-7 10"/></g>`;
  const zz = `<g fill="${INK}" font-family="Bricolage Grotesque, sans-serif" font-weight="800"><text x="150" y="58" font-size="18">z</text><text x="164" y="42" font-size="13">z</text></g>`;

  function face(expr, o) {
    const look = o.look || [0, 0], blink = o.blink || 0;
    switch (expr) {
      case "listening": return arcEyes("down") + mouths.smile;
      case "vibing": return arcEyes("up") + mouths.grin + blush(0.7);
      case "happy": return arcEyes("up") + mouths.grin + blush(0.6);
      case "sad": return brows("sad") + dotEyes({ blink, look: [look[0], 0.6], y: 119 }) + mouths.frown;
      case "angry": return brows("angry") + dotEyes({ blink: Math.max(blink, 0.25), look, y: 118 }) + mouths.angry;
      case "calm": return arcEyes("down", 118) + mouths.calm + blush(0.35);
      case "fearful": return brows("fearful") + wideEyes(look) + mouths.wavy;
      case "surprised": return brows("surprised") + wideEyes(look) + mouths.o;
      case "disgusted":
        // one eye squeezed shut, one narrowed, zigzag mouth
        return brows("disgusted") + `<path d="M66 117 h18" ${stroke}/>` +
          `<ellipse cx="126" cy="117" rx="6.5" ry="${6.5 * (1 - 0.9 * Math.max(blink, 0.35))}" fill="${INK}"/>` + mouths.zigzag;
      default: return dotEyes({ blink, look }) + mouths.smile;
    }
  }

  function props(expr) {
    return {
      listening: waves(0.9),
      vibing: note(24, 54, 1, -12) + note(170, 40, 0.85, 14),
      sad: tear,
      angry: steam,
      calm: zz,
      fearful: sweat,
      surprised: spark,
    }[expr] || "";
  }

  // Arms sit behind the body: a rounded capsule + hand, rotated at the shoulder.
  function arm(side, deg, color, dark) {
    const sx = side < 0 ? 30 : 170, sy = 138; // shoulders on the silhouette edge
    const rot = side < 0 ? deg : -deg; // outward is away from the body on both sides
    return `<g transform="rotate(${rot} ${sx} ${sy})">
      <rect x="${sx - 7}" y="${sy}" width="14" height="48" rx="7" fill="${dark}"/>
      <circle cx="${sx}" cy="${sy + 50}" r="10" fill="${color}" stroke="${dark}" stroke-width="2.5"/>
    </g>`;
  }

  function mascotSVG(o = {}) {
    const expr = o.expr || "neutral";
    const color = o.color || "#E2D4E0";
    const sq = o.squash || 0, tilt = o.tilt || 0;
    const dark = shade(color, -0.32);
    const id = "m" + Math.random().toString(36).slice(2, 8);
    // squash & stretch around the feet (y = 190)
    const sx = 1 + sq, sy = 1 - sq;
    const extras = o.extras === false ? "" : props(expr);
    const [al, ar] = o.arms || [12, 12];
    return `<svg viewBox="-10 0 220 215" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <radialGradient id="${id}s" cx=".33" cy=".28" r=".75">
      <stop offset="0" stop-color="#fff" stop-opacity=".45"/><stop offset=".55" stop-color="#fff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <ellipse cx="100" cy="203" rx="${52 * sx}" ry="6.5" fill="#000" opacity=".28"/>
  <g transform="translate(100 196) rotate(${tilt}) scale(${sx} ${sy}) translate(-100 -196)">
    ${arm(-1, al, color, dark)}${arm(1, ar, color, dark)}
    <ellipse cx="80" cy="192" rx="15" ry="8" fill="${dark}"/>
    <ellipse cx="120" cy="192" rx="15" ry="8" fill="${dark}"/>
    <path d="M100 52 C152 52 176 88 176 124 C176 166 142 192 100 192 C58 192 24 166 24 124 C24 88 48 52 100 52Z" fill="${color}"/>
    <path d="M100 52 C152 52 176 88 176 124 C176 166 142 192 100 192 C58 192 24 166 24 124 C24 88 48 52 100 52Z" fill="url(#${id}s)"/>
    <path d="M30 116 C30 30 170 30 170 116" stroke="${INK}" stroke-width="9" fill="none" stroke-linecap="round"/>
    <rect x="16" y="98" width="24" height="42" rx="11" fill="${INK}"/>
    <rect x="160" y="98" width="24" height="42" rx="11" fill="${INK}"/>
    <rect x="21" y="106" width="5" height="26" rx="2.5" fill="#E2D4E0" opacity=".9"/>
    <rect x="174" y="106" width="5" height="26" rx="2.5" fill="#E2D4E0" opacity=".9"/>
    ${face(expr, o)}
  </g>
  ${extras}
</svg>`;
  }

  // Guide poses (arms + small body language), used by the trailer.
  const POSES = {
    rest: { arms: [12, 12] },
    point: { arms: [14, 100], tilt: 4 },        // right arm out toward the UI
    tap: { arms: [14, 58], tilt: 6, squash: 0.04 },
    wave: { arms: [14, 136], tilt: -3 },        // up and out, clear of the body
    cheer: { arms: [136, 136], squash: -0.08 },
    shrug: { arms: [104, 104], tilt: 0 },
  };
  root.MOODIE_POSES = POSES;
  root.mascotSVG = mascotSVG;
  if (typeof module !== "undefined") module.exports = { mascotSVG };
})(typeof window !== "undefined" ? window : globalThis);
