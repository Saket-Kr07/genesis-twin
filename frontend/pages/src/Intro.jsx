import { useEffect, useRef, useState, useCallback } from "react";

// Full-screen cinematic opening shown every time the site is opened.
// Timeline (seconds after the skull is ready; mirrored by the CSS delays in index.html):
//   0.0  fade up out of the dark, skull turns in from the side
//   1.6  "GENESIS TWIN" reveals letter by letter
//   3.2  title line, 4.2 subtitle, 5.4 "Enter" button
//   9.5  auto-continues (any key, click on Enter, or Skip does it sooner)
//   exit: camera pushes into the skull while the overlay dissolves into the dashboard
const MODEL_URL = `${import.meta.env.BASE_URL}models/skeletal.glb`;
const AUTO_MS = 9500;
const EXIT_MS = 1200;
const LOAD_TIMEOUT_MS = 12000;

const reducedMotion = () => {
  try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; }
};

export default function Intro({ onDone }) {
  const host = useRef(null);
  const scene = useRef(null);
  const [phase, setPhase] = useState("loading"); // loading -> play -> leave
  const [progress, setProgress] = useState(0);
  const phaseRef = useRef("loading");
  const doneRef = useRef(false);
  const reduced = useRef(reducedMotion());

  const go = (p) => { phaseRef.current = p; setPhase(p); };

  const finish = useCallback(() => {
    if (doneRef.current || phaseRef.current === "leave") return;
    go("leave");
    scene.current?.exit(EXIT_MS);
    setTimeout(() => { doneRef.current = true; onDone(); }, EXIT_MS + 100);
  }, [onDone]);

  // load the skull (lazily, so three.js never delays first paint)
  useEffect(() => {
    let dead = false;
    let timer = 0;
    const begin = (s) => {
      if (dead || phaseRef.current !== "loading") { s?.dispose(); return; }
      scene.current = s;
      s?.start();
      go("play");
    };
    // never leave the visitor stuck on a loader: after the timeout, play the text without the skull
    timer = setTimeout(() => begin(null), LOAD_TIMEOUT_MS);
    import("./skullScene.js")
      .then(({ createSkullScene }) => createSkullScene(host.current, { url: MODEL_URL, onProgress: setProgress, reducedMotion: reduced.current }))
      .then((s) => {
        if (dead) { s.dispose(); return; }
        clearTimeout(timer);
        begin(s);
      })
      .catch((e) => {
        // no WebGL / model missing: keep the branded text and carry on
        console.warn("Intro skull unavailable:", e);
        clearTimeout(timer);
        begin(null);
      });
    return () => { dead = true; clearTimeout(timer); };
  }, []);

  // auto-continue, keyboard, pointer parallax
  useEffect(() => {
    if (phase !== "play") return;
    const auto = setTimeout(finish, reduced.current ? AUTO_MS - 3000 : AUTO_MS);
    const key = (e) => { if (["Enter", " ", "Escape"].includes(e.key)) { e.preventDefault(); finish(); } };
    const move = (e) => scene.current?.setPointer((e.clientX / window.innerWidth) * 2 - 1, (e.clientY / window.innerHeight) * 2 - 1);
    window.addEventListener("keydown", key);
    window.addEventListener("pointermove", move);
    return () => { clearTimeout(auto); window.removeEventListener("keydown", key); window.removeEventListener("pointermove", move); };
  }, [phase, finish]);

  // free the GPU context and restore scrolling when the intro goes away
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; scene.current?.dispose(); scene.current = null; };
  }, []);

  const title = "GENESIS TWIN";
  return (
    <div className={`intro ${phase}`} role="dialog" aria-label="Genesis Twin introduction">
      <div className="intro-stage" ref={host} aria-hidden="true" />
      <div className="intro-vignette" aria-hidden="true" />

      <button className="intro-skip" onClick={finish}>Skip intro</button>

      {phase === "loading" && (
        <div className="intro-loader" aria-live="polite">
          <span className="eyebrow">Initialising digital twin</span>
          <span className="intro-bar"><i style={{ transform: `scaleX(${Math.max(0.04, progress)})` }} /></span>
        </div>
      )}

      <div className="intro-copy">
        <h1 className="intro-title">{title}</h1>
        <p className="intro-line">Explore the Human Body. Understand the Future of Health.</p>
        <p className="intro-sub">An Intelligent 3D Human Digital Twin Platform</p>
        <button className="btn main intro-enter" onClick={finish}>Enter the platform</button>
      </div>
    </div>
  );
}
