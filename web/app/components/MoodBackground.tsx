"use client";

import { useEffect, useRef } from "react";

import { micLevel } from "../micLevel";
import type { Motion } from "../moods";

/**
 * Lightweight mood gradient: one fullscreen triangle + one fragment shader
 * (domain-warped noise mapped across a 5-stop colour ramp), plain WebGL.
 *
 * Adapts to the mood in colour *and* motion (speed, turbulence, scale, drift,
 * flicker), all blended smoothly when the mood changes.
 *
 * Tactile:
 * - leans toward the pointer / touch point,
 * - brightens and stirs with the live mic level (shared `micLevel` store),
 * - ripples once when `pulseKey` changes (a mood lands).
 *
 * Cheap: half-resolution render (the gradient is soft), all easing inside the
 * rAF loop (no React re-renders), stops when the tab is hidden, one still frame
 * under reduced motion. Without WebGL, the CSS gradient underneath shows.
 */

type Props = {
  /** Five stops, dark -> light. */
  ramp: string[];
  motion: Motion;
  /** Change to trigger a one-off ripple (e.g. the detected mood). */
  pulseKey?: string;
  /** User paused the background: render a still frame, like reduced motion. */
  paused?: boolean;
};

const FRAG = `
precision mediump float;
uniform vec2  uRes;
uniform float uPhase;    // integrated flow time (speed already applied)
uniform vec2  uOffset;   // integrated drift
uniform float uWarp;     // turbulence
uniform float uScale;    // feature size
uniform float uFlicker;  // 0..1
uniform float uClock;    // wall time, for flicker
uniform vec2  uPtr;      // 0..1, y up
uniform float uPtrOn;
uniform float uLevel;    // 0..1 live mic level
uniform float uPulse;    // 0..1 decaying ripple
uniform vec3  uC0, uC1, uC2, uC3, uC4;

float hash(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float noise(vec2 p){
  vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p){
  float v = 0.0, a = 0.5; mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
  for (int i = 0; i < 4; i++) { v += a * noise(p); p = m * p; a *= 0.5; }
  return v;
}

// Sample the 5-stop ramp at x in 0..1.
vec3 ramp(float x){
  x = clamp(x, 0.0, 1.0) * 4.0;
  vec3 c = mix(uC0, uC1, clamp(x, 0.0, 1.0));
  c = mix(c, uC2, clamp(x - 1.0, 0.0, 1.0));
  c = mix(c, uC3, clamp(x - 2.0, 0.0, 1.0));
  return mix(c, uC4, clamp(x - 3.0, 0.0, 1.0));
}

void main(){
  vec2 n = gl_FragCoord.xy / uRes;
  float aspect = uRes.x / uRes.y;
  vec2 uv = vec2(n.x * aspect, n.y);
  vec2 ptr = vec2(uPtr.x * aspect, uPtr.y);
  float t = uPhase * 0.05;
  float stir = 1.0 + uLevel * 0.8;            // voice stirs the flow

  // Pointer pull: a soft well that bends the flow toward the finger/cursor.
  vec2 d = uv - ptr;
  float well = exp(-dot(d, d) * 3.0) * uPtrOn;

  // Ripple from the upper centre when a mood lands.
  float rd = length((n - vec2(0.5, 0.62)) * vec2(aspect, 1.0));
  float ring = uPulse * sin(rd * 16.0 - (1.0 - uPulse) * 14.0) * exp(-rd * 2.0);

  vec2 p = uv * uScale + uOffset;
  vec2 q = vec2(fbm(p * 1.2 + t), fbm(p * 1.2 + vec2(5.2, 1.3) - t));
  vec2 r = vec2(fbm(p + uWarp * stir * q + vec2(1.7, 9.2) + t * 1.3 - d * well * 1.4 + ring * 0.3),
                fbm(p + uWarp * stir * q + vec2(8.3, 2.8) - t));
  float f = fbm(p + 2.2 * r);

  // fbm clusters around 0.3-0.7: stretch it so the whole ramp is used.
  float x = smoothstep(0.22, 0.78, f);
  // Gentle vertical bias: a little brighter up top (behind the headline/ghost word).
  x += (n.y - 0.5) * 0.18 + well * 0.12 + uLevel * 0.15 + max(ring, 0.0) * 0.08;

  vec3 col = ramp(x);
  // Soft highlight streaks from the second warp layer.
  col = mix(col, uC4, pow(smoothstep(0.55, 0.9, r.y), 2.0) * 0.35);

  // Nervous moods: a faint, irregular brightness flicker.
  float fl = (noise(vec2(uClock * 6.0, 0.0)) - 0.5) * uFlicker;
  col *= 1.0 + fl * 0.5;

  col += (hash(gl_FragCoord.xy + fract(uClock) * 91.0) - 0.5) * 0.015; // dither against banding
  gl_FragColor = vec4(col, 1.0);
}`;

const VERT =
  "attribute vec2 a; void main(){ gl_Position = vec4(a, 0.0, 1.0); }";

const hexToRgb = (h: string) =>
  [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);

type MotionVec = [number, number, number, number, number, number]; // speed, warp, scale, dx, dy, flicker
const toVec = (m: Motion): MotionVec => [
  m.speed,
  m.warp,
  m.scale,
  m.drift[0],
  m.drift[1],
  m.flicker,
];

export default function MoodBackground({
  ramp,
  motion,
  pulseKey,
  paused = false,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  // Latest props, read by the render loop without re-subscribing.
  const rampRef = useRef<number[][]>(ramp.map(hexToRgb));
  const motionRef = useRef<MotionVec>(toVec(motion));
  const pulseRef = useRef(0);
  const kickRef = useRef<() => void>(() => undefined);
  const pausedRef = useRef(paused);
  const rampKey = ramp.join();
  const motionKey = toVec(motion).join();

  useEffect(() => {
    rampRef.current = ramp.map(hexToRgb);
    motionRef.current = toVec(motion);
    kickRef.current();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rampKey, motionKey]);

  useEffect(() => {
    pausedRef.current = paused;
    kickRef.current();
  }, [paused]);

  useEffect(() => {
    if (!pulseKey) return;
    pulseRef.current = 1;
    kickRef.current();
  }, [pulseKey]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const setup = (): (() => void) => {
      const gl = canvas.getContext("webgl", {
        antialias: false,
        alpha: false,
        depth: false,
        stencil: false,
        premultipliedAlpha: false,
        powerPreference: "low-power",
      });
      if (!gl || gl.isContextLost()) return () => undefined; // CSS gradient stays visible
      // Software WebGL (no GPU: SwiftShader, llvmpipe, Basic Render) makes a
      // full-screen shader very expensive. Keep the CSS gradient there.
      const dbg = gl.getExtension("WEBGL_debug_renderer_info");
      const renderer = String(
        gl.getParameter(dbg ? dbg.UNMASKED_RENDERER_WEBGL : gl.RENDERER) || "",
      );
      if (/swiftshader|llvmpipe|software|basic render/i.test(renderer)) {
        console.info(
          "MoodMix: software WebGL detected, using the CSS gradient.",
        );
        return () => undefined;
      }

      const compile = (type: number, src: string) => {
        const s = gl.createShader(type)!;
        gl.shaderSource(s, src);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS))
          throw new Error(gl.getShaderInfoLog(s) || "compile failed");
        return s;
      };
      let prog: WebGLProgram;
      try {
        prog = gl.createProgram()!;
        gl.attachShader(prog, compile(gl.VERTEX_SHADER, VERT));
        gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FRAG));
        gl.linkProgram(prog);
        if (!gl.getProgramParameter(prog, gl.LINK_STATUS))
          throw new Error(gl.getProgramInfoLog(prog) || "link failed");
        gl.useProgram(prog);
      } catch (e) {
        console.warn(
          "MoodMix: WebGL background off, using the CSS gradient.",
          e,
        );
        return () => undefined;
      }
      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(
        gl.ARRAY_BUFFER,
        new Float32Array([-1, -1, 3, -1, -1, 3]),
        gl.STATIC_DRAW,
      );
      const loc = gl.getAttribLocation(prog, "a");
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      const U = (k: string) => gl.getUniformLocation(prog, k);
      const u = {
        res: U("uRes"),
        phase: U("uPhase"),
        offset: U("uOffset"),
        warp: U("uWarp"),
        scale: U("uScale"),
        flicker: U("uFlicker"),
        clock: U("uClock"),
        ptr: U("uPtr"),
        ptrOn: U("uPtrOn"),
        level: U("uLevel"),
        pulse: U("uPulse"),
        c: [U("uC0"), U("uC1"), U("uC2"), U("uC3"), U("uC4")],
      };

      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
      // Adaptive quality. "full": half-res, 30 fps idle. "low": third-res, 20 fps.
      // "still": render only on changes (like reduced motion). Data Saver starts at "still".
      const nav = navigator as Navigator & {
        connection?: { saveData?: boolean };
      };
      let quality: "full" | "low" | "still" = nav.connection?.saveData
        ? "still"
        : "full";
      let SCALE = 0.5; // soft gradient: half-res is indistinguishable and ~4x cheaper
      const resize = () => {
        const w = Math.max(1, Math.round(window.innerWidth * SCALE));
        const h = Math.max(1, Math.round(window.innerHeight * SCALE));
        if (canvas.width !== w || canvas.height !== h) {
          canvas.width = w;
          canvas.height = h;
          gl.viewport(0, 0, w, h);
        }
      };
      resize();

      const col = rampRef.current.map((c) => [...c]);
      const mot = [...motionRef.current];
      const ptr = { x: 0.5, y: 0.6, tx: 0.5, ty: 0.6, on: 0, ton: 0 };
      let level = 0;
      let phase = 20;
      const offset = [0, 0];
      const t0 = performance.now();
      let last = t0;
      let raf = 0;
      let running = false;
      let shown = false;
      // Frame budget: full rate while something is reacting (pointer, voice, ripple,
      // colour blend); ~30fps otherwise. The idle flow is slow enough that 30fps
      // looks identical and halves continuous GPU work.
      let IDLE_FRAME_MS = 33;
      // Frame-interval samples taken only while running at full rate (reacting).
      const samples: number[] = [];
      let prevReacting = false;
      const degrade = () => {
        if (quality === "full") {
          quality = "low";
          SCALE = 0.33;
          IDLE_FRAME_MS = 50;
          resize();
        } else if (quality === "low") {
          quality = "still";
        }
        samples.length = 0;
      };
      const INTERACT_HOLD_MS = 1500;
      let lastDraw = 0;
      let lastInteract = t0;
      let blending = true;

      const ease = (rate: number, dt: number) => 1 - Math.exp(-dt * rate);

      const draw = (now: number) => {
        const reacting =
          blending ||
          now - lastInteract < INTERACT_HOLD_MS ||
          pulseRef.current > 0 ||
          micLevel.value > 0.01 ||
          level > 0.01;
        if (
          !reacting &&
          !reduce.matches &&
          !pausedRef.current &&
          quality !== "still" &&
          now - lastDraw < IDLE_FRAME_MS
        ) {
          prevReacting = false;
          raf = requestAnimationFrame(draw);
          return;
        }
        // Measure real frame pacing while drawing every frame; degrade if the
        // device can't hold ~30 fps (full) or ~20 fps (low).
        if (
          reacting &&
          prevReacting &&
          quality !== "still" &&
          !document.hidden
        ) {
          samples.push(now - lastDraw);
          if (samples.length >= 40) {
            const median = [...samples].sort((a, b) => a - b)[20];
            if (
              (quality === "full" && median > 34) ||
              (quality === "low" && median > 52)
            )
              degrade();
            else samples.length = 0;
          }
        }
        prevReacting = reacting;
        lastDraw = now;
        const dt = Math.min(0.05, (now - last) / 1000);
        last = now;
        const still =
          reduce.matches || pausedRef.current || quality === "still";

        // Blend colours and motion toward the current mood (~1s).
        const k = still ? 1 : ease(3.2, dt);
        let settling = false;
        col.forEach((c, i) =>
          c.forEach((v, j) => {
            const tv = rampRef.current[i][j];
            c[j] = v + (tv - v) * k;
            if (Math.abs(tv - c[j]) > 0.002) settling = true;
          }),
        );
        mot.forEach((v, i) => (mot[i] = v + (motionRef.current[i] - v) * k));
        blending = settling;

        level += (micLevel.value - level) * ease(10, dt);
        if (!still) {
          phase += dt * mot[0] * (1 + level * 1.5); // integrate speed: no jumps when it changes
          offset[0] += dt * mot[3];
          offset[1] += dt * mot[4];
        }
        ptr.x += (ptr.tx - ptr.x) * ease(6, dt);
        ptr.y += (ptr.ty - ptr.y) * ease(6, dt);
        ptr.on += (ptr.ton - ptr.on) * ease(2.5, dt);
        pulseRef.current = still ? 0 : Math.max(0, pulseRef.current - dt / 1.6);

        gl.uniform2f(u.res, canvas.width, canvas.height);
        gl.uniform1f(u.phase, phase);
        gl.uniform2f(u.offset, offset[0], offset[1]);
        gl.uniform1f(u.warp, mot[1]);
        gl.uniform1f(u.scale, mot[2]);
        gl.uniform1f(u.flicker, still ? 0 : mot[5]);
        gl.uniform1f(u.clock, (now - t0) / 1000);
        gl.uniform2f(u.ptr, ptr.x, ptr.y);
        gl.uniform1f(u.ptrOn, still ? 0 : ptr.on);
        gl.uniform1f(u.level, level);
        gl.uniform1f(u.pulse, pulseRef.current);
        col.forEach((c, i) => gl.uniform3f(u.c[i], c[0], c[1], c[2]));
        gl.drawArrays(gl.TRIANGLES, 0, 3);
        if (!shown) {
          shown = true;
          canvas.classList.add("is-on"); // fade in over the CSS gradient
        }

        // Reduced motion: stop once colours have settled. Otherwise keep flowing.
        if (document.hidden || (still && !settling)) {
          running = false;
          return;
        }
        raf = requestAnimationFrame(draw);
      };

      const start = () => {
        if (running || document.hidden) return;
        running = true;
        last = performance.now();
        raf = requestAnimationFrame(draw);
      };
      kickRef.current = start;

      const onMove = (e: PointerEvent) => {
        ptr.tx = e.clientX / window.innerWidth;
        ptr.ty = 1 - e.clientY / window.innerHeight;
        ptr.ton = e.pointerType === "touch" ? 0.8 : 1;
        lastInteract = performance.now();
        start();
      };
      const onLeave = () => {
        ptr.ton = 0;
      };
      const onUp = (e: PointerEvent) => {
        if (e.pointerType === "touch") ptr.ton = 0;
      };
      const onVis = () => {
        if (document.hidden) {
          cancelAnimationFrame(raf);
          running = false;
        } else start();
      };
      const onResize = () => {
        resize();
        start();
      };

      window.addEventListener("pointermove", onMove, { passive: true });
      window.addEventListener("pointerdown", onMove, { passive: true });
      window.addEventListener("pointerup", onUp, { passive: true });
      document.documentElement.addEventListener("pointerleave", onLeave);
      document.addEventListener("visibilitychange", onVis);
      window.addEventListener("resize", onResize);
      reduce.addEventListener("change", start);
      start();

      return () => {
        cancelAnimationFrame(raf);
        running = false;
        kickRef.current = () => undefined;
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerdown", onMove);
        window.removeEventListener("pointerup", onUp);
        document.documentElement.removeEventListener("pointerleave", onLeave);
        document.removeEventListener("visibilitychange", onVis);
        window.removeEventListener("resize", onResize);
        reduce.removeEventListener("change", start);
        // Free GPU objects but keep the context: React strict mode remounts in dev,
        // and a deliberately lost context cannot be reused by the same canvas.
        gl.deleteBuffer(buf);
        gl.deleteProgram(prog);
      };
    };

    // Boot after the page has loaded and gone idle, so compiling the shader
    // never competes with first paint or the first tap. The CSS gradient
    // underneath is already showing.
    let cancelled = false;
    let teardown: () => void = () => undefined;
    let idleId = 0;
    let timer = 0;
    const w = window as Window & {
      requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    const boot = () => {
      if (cancelled) return;
      teardown = setup();
    };
    const schedule = () => {
      if (w.requestIdleCallback)
        idleId = w.requestIdleCallback(boot, { timeout: 1500 });
      else timer = window.setTimeout(boot, 600);
    };
    if (document.readyState === "complete") schedule();
    else window.addEventListener("load", schedule, { once: true });

    return () => {
      cancelled = true;
      window.removeEventListener("load", schedule);
      if (idleId && w.cancelIdleCallback) w.cancelIdleCallback(idleId);
      window.clearTimeout(timer);
      teardown();
    };
  }, []);

  return <canvas ref={canvasRef} className="bg-gl" aria-hidden />;
}
