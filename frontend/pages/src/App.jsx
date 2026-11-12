import { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const VIEWER = import.meta.env.VITE_VIEWER_URL || ""; // optional: URL of Rudraksh's viewer
const ORGANS = ["brain", "heart", "lungs", "liver", "stomach", "intestines", "kidneys", "bladder", "pancreas", "spleen", "thyroid", "reproductive"];
const PATHOGENS = ["respiratory_virus", "gut_virus", "bloodstream_bacterium"];
const col = (s) => (s >= 80 ? "#2ecc71" : s >= 50 ? "#f1c40f" : "#e74c3c");
const fmt = (v) => (v && typeof v === "object" ? `${v.value}${v.unit ? " " + v.unit : ""}` : String(v));

async function call(path, { method = "GET", body, token, file } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let data;
  if (file) { data = new FormData(); data.append("file", file); }
  else if (body) { headers["Content-Type"] = "application/json"; data = JSON.stringify(body); }
  const r = await fetch(API + path, { method, headers, body: data });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : `Error ${r.status}`);
  return j;
}

function Gauge({ s }) {
  const c = 2 * Math.PI * 17;
  return (
    <svg width="46" height="46" viewBox="0 0 44 44">
      <circle cx="22" cy="22" r="17" fill="none" stroke="rgba(255,255,255,.09)" strokeWidth="4" />
      <circle cx="22" cy="22" r="17" fill="none" stroke={col(s)} strokeWidth="4" strokeLinecap="round" strokeDasharray={`${(s / 100) * c} ${c}`} transform="rotate(-90 22 22)" />
      <text x="22" y="26" textAnchor="middle" fontSize="12" fill="#e7ecf6" className="mono">{Math.round(s)}</text>
    </svg>
  );
}

function Organ({ id, o }) {
  const st = o.score >= 80 ? "Healthy" : o.score >= 50 ? "Watch" : "Impaired";
  return (
    <div className="organ">
      <Gauge s={o.score} />
      <div style={{ flex: 1 }}>
        <b>{id}</b><span className="st" style={{ color: col(o.score) }}>{st}</span>
        <div className="vit">{Object.entries(o.vitals || {}).map(([k, v]) => <div key={k}><span>{(v && v.label) || k.replace(/_/g, " ")}</span><span className="mono">{fmt(v)}</span></div>)}</div>
      </div>
    </div>
  );
}

function Slide({ label, value, min, max, step = 1, onChange }) {
  return (
    <label>{label}: {value}
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

function Viewer() {
  return VIEWER
    ? <iframe title="3D viewer" src={VIEWER} style={{ width: "100%", height: 560, border: "1px solid var(--line)", borderRadius: 8 }} />
    : <p className="tag">3D viewer: set VITE_VIEWER_URL to the address of frontend/viewer (npm run dev there).</p>;
}

function Landing({ go }) {
  const pillars = [
    ["Traceable", "Every source carries a DOI. Preprints are flagged as not peer reviewed."],
    ["Governed", "Model updates pass a held-out validation gate and an admin decision before use."],
    ["Pathogen lab", "Upload a time series, fit growth and decay with uncertainty, watch organ impact by day."],
    ["Honest uncertainty", "Ranges and reliability flags, never a bare number."],
  ];
  return (
    <>
      <section className="hero">
        <span className="eyebrow">Digital twin research platform</span>
        <h1>A body model you can audit.</h1>
        <p>Explore how age, lifestyle and infection change organ function in a layered 3D anatomy, with every number tied to its evidence.</p>
        <div className="row">
          <button className="btn main" onClick={() => go("explorer")}>Open the explorer</button>
          <button className="btn" onClick={() => go("lab")}>Run a pathogen simulation</button>
        </div>
      </section>
      <div className="tiles">{pillars.map(([t, d]) => <div className="tile" key={t}><b>{t}</b><p>{d}</p></div>)}</div>
      <h2>Live 3D anatomy</h2>
      <Viewer />
    </>
  );
}

function Auth({ onLogin }) {
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [consent, setConsent] = useState(false);
  const [msg, setMsg] = useState("");
  const run = async (register) => {
    try {
      if (register) {
        if (!consent) return setMsg("Please accept the consent text first.");
        await call("/auth/register", { method: "POST", body: { email, password: pw } });
      }
      const r = await call("/auth/login", { method: "POST", body: { email, password: pw } });
      onLogin(r.access_token);
    } catch (e) { setMsg(e.message); }
  };
  return (
    <>
      <h2>Log in or register</h2>
      <div className="row">
        <label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Password<input type="password" value={pw} onChange={(e) => setPw(e.target.value)} /></label>
      </div>
      <label style={{ flexDirection: "row", gap: 8 }}>
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        I understand this platform is for research and education only, and I consent to my account data being stored. Uploads must be anonymised.
      </label>
      <div className="row">
        <button className="btn main" onClick={() => run(false)}>Log in</button>
        <button className="btn" onClick={() => run(true)}>Register</button>
      </div>
      <p className="err">{msg}</p>
      <p className="tag">Test accounts: pro@genesis.test, admin@genesis.test (password in backend/app/seed.py)</p>
    </>
  );
}

function Pricing({ token, me, refresh, go }) {
  const [msg, setMsg] = useState("");
  const buy = async () => {
    try {
      const r = await call("/billing/checkout", { method: "POST", token, body: { plan: "pro_monthly" } });
      setMsg(r.note); refresh();
    } catch (e) { setMsg(e.message); }
  };
  const pro = me && (me.role === "pro" || me.role === "admin");
  return (
    <>
      <h2 style={{ marginTop: 0 }}>Plans</h2>
      <div className="plans">
        <div className="plan">
          <span className="eyebrow">Public</span><div className="big">Free</div>
          <ul><li>Layered 3D anatomy, 6 main organs</li><li>Age and lifestyle simulation</li><li>3 infection presets</li><li>Latest 5 sources</li></ul>
          <button className="btn" onClick={() => go("explorer")}>Open the explorer</button>
        </div>
        <div className="plan rec">
          <span className="eyebrow">Professional</span><div className="big">Research access</div>
          <ul><li>All body systems in full detail</li><li>Upload your own pathogen data and fit it</li><li>Save, fork and export experiments</li><li>Full evidence list and model version history</li><li>Personal twin and PDF reports</li></ul>
          {pro ? <span className="chip ok">Active</span> : token ? <button className="btn main" onClick={buy}>Start Pro (test mode)</button> : <button className="btn main" onClick={() => go("auth")}>Log in to start</button>}
        </div>
      </div>
      <p className={me?.role === "pro" ? "ok" : "tag"}>{msg || "Test mode: no real payment is made and no card details are collected."}</p>
    </>
  );
}

const SYSTEMS = { Cardiovascular: ["heart"], Respiratory: ["lungs"], Nervous: ["brain"], Digestive: ["liver", "stomach", "intestines", "pancreas"], Urinary: ["kidneys", "bladder"], Endocrine: ["thyroid", "pancreas"], Immune: ["spleen"], Reproductive: ["reproductive"] };

function Explorer() {
  const [f, setF] = useState({ age: 40, sex: "male", sleep: 7, exercise: 3, smoking: 0, diet: 3 });
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [sys, setSys] = useState("All systems");
  useEffect(() => { call("/twin/predict", { method: "POST", body: f }).then((r) => { setD(r); setErr(""); }).catch((e) => setErr(e.message)); }, [f]);
  const set = (k) => (v) => setF({ ...f, [k]: v });
  const ids = sys === "All systems" ? ORGANS : SYSTEMS[sys];
  return (
    <>
      <h2 style={{ marginTop: 0 }}>Body explorer</h2>
      <div className="ex">
        <div className="stick"><Viewer /></div>
        <div className="stack">
          <div className="panel row">
            <label>Sex<select value={f.sex} onChange={(e) => set("sex")(e.target.value)}><option>male</option><option>female</option></select></label>
            <Slide label="Age" value={f.age} min={20} max={80} onChange={set("age")} />
            <Slide label="Sleep (h)" value={f.sleep} min={3} max={12} onChange={set("sleep")} />
            <Slide label="Exercise (days/week)" value={f.exercise} min={0} max={7} onChange={set("exercise")} />
            <Slide label="Smoking (per day)" value={f.smoking} min={0} max={40} onChange={set("smoking")} />
            <Slide label="Diet (1-5)" value={f.diet} min={1} max={5} onChange={set("diet")} />
          </div>
          <p className="err">{err}</p>
          <div className="row">{["All systems", ...Object.keys(SYSTEMS)].map((k) => <button key={k} className={"btn" + (sys === k ? " main" : "")} onClick={() => setSys(k)}>{k}</button>)}</div>
          <p className="tag">Simulated outputs. Scores: 80+ healthy, 50-79 watch, below 50 impaired.</p>
          <div className="grid">{d && ids.filter((id) => d[id]).map((id) => <Organ key={id} id={id} o={d[id]} />)}</div>
        </div>
      </div>
    </>
  );
}

function Chart({ times, load, i }) {
  const W = 560, H = 160, x = (k) => 32 + (k / (load.length - 1)) * (W - 44), y = (v) => H - 24 - v * (H - 44);
  const pts = load.map((v, k) => `${x(k)},${y(v)}`).join(" ");
  const pk = load.indexOf(Math.max(...load));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%" }}>
      {[0, 0.5, 1].map((g) => <g key={g}><line x1="32" x2={W - 12} y1={y(g)} y2={y(g)} stroke="rgba(255,255,255,.08)" /><text x="4" y={y(g) + 4} fontSize="10" fill="#8d9bb8">{g}</text></g>)}
      {[0, 10, 20, 30].map((t) => <text key={t} x={x(t * 4)} y={H - 6} fontSize="10" fill="#8d9bb8" textAnchor="middle">{t} d</text>)}
      <polygon points={`${x(0)},${y(0)} ${pts} ${x(load.length - 1)},${y(0)}`} fill="rgba(94,234,212,.12)" />
      <polyline points={pts} fill="none" stroke="#5eead4" strokeWidth="2" />
      <line x1={x(i)} x2={x(i)} y1="8" y2={H - 24} stroke="#8b9cff" strokeDasharray="3 3" />
      <circle cx={x(pk)} cy={y(load[pk])} r="3.5" fill="#fbbf24" />
      <text x={x(pk) + 8} y={y(load[pk]) + 4} fontSize="10" fill="#fbbf24">peak, day {times[pk]}</text>
    </svg>
  );
}

function Lab({ token, me }) {
  const [p, setP] = useState(PATHOGENS[0]);
  const [treatment, setTreatment] = useState(0);
  const [start, setStart] = useState(0);
  const [day, setDay] = useState(0);
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [up, setUp] = useState(null);
  useEffect(() => {
    call("/pathogens/timeline", { method: "POST", token, body: { pathogen_id: p, day: 0, treatment, treatment_start: start } })
      .then((r) => { setD(r); setErr(""); }).catch((e) => setErr(e.message));
  }, [p, treatment, start]);
  const i = Math.round(day * 4);
  const pro = me && (me.role === "pro" || me.role === "admin");
  const upload = async (file) => {
    try { setUp(await call("/pathogens/upload", { method: "POST", token, file })); } catch (e) { setUp({ error: e.message }); }
  };
  const rows = d ? ORGANS.map((id) => ({ id, score: d.scores[id][i], vitals: d.days[Math.min(30, Math.floor(day))].organs[id].vitals })) : [];
  const worst = [...rows].sort((a, b) => a.score - b.score).slice(0, 3);
  return (
    <>
      <h2 style={{ marginTop: 0 }}>Pathogen lab</h2>
      <p className="tag">Sample parameters, not claims about real outbreaks.</p>
      <div className="split2">
        <div className="panel stack">
          <label>Pathogen<select value={p} onChange={(e) => setP(e.target.value)}>{PATHOGENS.map((x) => <option key={x}>{x}</option>)}</select></label>
          <Slide label="Day" value={day} min={0} max={30} step={0.25} onChange={setDay} />
          <Slide label="Treatment strength" value={treatment} min={0} max={1} step={0.05} onChange={setTreatment} />
          <Slide label="Treatment starts (day)" value={start} min={0} max={30} onChange={setStart} />
          <span className="tag">Treatment lowers the growth rate in the model. Earlier start, smaller peak.</span>
          <p className="err">{err}</p>
        </div>
        {d && (
          <div className="stack">
            <div className="panel">
              <div className="row" style={{ justifyContent: "space-between", margin: 0 }}><b>Pathogen load, relative to the untreated peak</b><span className="tag mono">day {day} · load {d.load[i]} · {d.model_version}</span></div>
              <Chart times={d.times} load={d.load} i={i} />
            </div>
            <b>Most affected at day {day}</b>
            <div className="grid">{worst.map((r) => <Organ key={r.id} id={r.id} o={r} />)}</div>
          </div>
        )}
      </div>
      {d && <><h2>All organs</h2><div className="grid">{rows.map((r) => <Organ key={r.id} id={r.id} o={r} />)}</div></>}
      <h2>Fit your own pathogen data</h2>
      {pro ? (
        <div className="panel">
          <p className="tag">CSV with columns day and load, at least 5 time points. Anonymised data only.</p>
          <input type="file" accept=".csv" onChange={(e) => e.target.files[0] && upload(e.target.files[0])} />
          {up && <pre className="pre">{JSON.stringify(up, null, 2)}</pre>}
        </div>
      ) : <p className="tag">Log in with a Pro account to upload a CSV.</p>}
    </>
  );
}

function Research({ token }) {
  const [src, setSrc] = useState([]);
  const [ver, setVer] = useState([]);
  useEffect(() => {
    call("/research/sources", { token }).then(setSrc).catch(() => {});
    call("/research/model-versions", { token }).then(setVer).catch(() => {});
  }, [token]);
  return (
    <>
      <h2>Research feed: sources used</h2>
      <p className="tag">Model version in use: {src[0]?.model_version || "n/a"}. Preprints are not peer reviewed.</p>
      <div className="grid">
        {src.map((s) => (
          <div className="card" key={s.doi}>
            <b>{s.title}</b>
            <small>{s.date} · <span className="tag">{s.type === "preprint" ? "PREPRINT (not peer reviewed)" : "peer reviewed"}</span></small>
            <small>DOI {s.doi}</small><small>{s.change}</small>
          </div>
        ))}
      </div>
      <h2>Model version history</h2>
      {ver.length === 0 && <p className="tag">No versions registered yet.</p>}
      {ver.map((v) => <div className="card" key={v.version}><b>{v.version}</b> <span className="tag">{v.status}</span><small>{v.change_log}</small><small>approved: {v.approved_at || "-"}</small></div>)}
    </>
  );
}

function Admin({ token, me }) {
  const [version, setVersion] = useState("v1.1");
  const [log, setLog] = useState("");
  const [out, setOut] = useState("");
  const [list, setList] = useState([]);
  const load = () => call("/admin/models", { token }).then(setList).catch(() => {});
  useEffect(() => { if (me?.role === "admin") load(); }, [me]);
  if (me?.role !== "admin") return <p className="err">Administrators only. Log in as admin@genesis.test.</p>;
  const act = async (path, body) => {
    try { setOut(JSON.stringify(await call(path, { method: "POST", token, body }), null, 2)); load(); } catch (e) { setOut(e.message); }
  };
  return (
    <>
      <h2>Admin: model versions</h2>
      <div className="row">
        <label>Version<input value={version} onChange={(e) => setVersion(e.target.value)} /></label>
        <label>Change log<input value={log} onChange={(e) => setLog(e.target.value)} /></label>
        <button className="btn" onClick={() => act("/admin/model-versions", { version, change_log: log || "Candidate", papers: [] })}>Register candidate</button>
        <button className="btn main" onClick={() => act("/admin/models/approve", { model_version: version, approve: true })}>Approve</button>
        <button className="btn" onClick={() => act("/admin/models/approve", { model_version: version, approve: false })}>Reject</button>
      </div>
      {out && <pre className="pre">{out}</pre>}
      <h2>Decision log</h2>
      {list.map((x) => <div className="card" key={x.id}>{x.model_version}: {x.status} <small>{x.created_at}</small></div>)}
    </>
  );
}

function Dashboard({ token, me, go }) {
  const [tab, setTab] = useState("overview");
  const [pf, setPf] = useState({ age: 40, sex: "male", sleep: 7, exercise: 3, smoking: 0, diet: 3, height_cm: 175, weight_kg: 70, measurements: {} });
  const [tw, setTw] = useState(null);
  const [out, setOut] = useState("");
  const pro = me && (me.role === "pro" || me.role === "admin");
  const show = (p) => p.then((r) => setOut(JSON.stringify(r, null, 2))).catch((e) => setOut(e.message));
  if (!me) return <p>Please <button className="btn" onClick={() => go("auth")}>log in</button> to open the dashboard.</p>;
  if (!pro) return <p>The dashboard is for Pro users. <button className="btn main" onClick={() => go("pricing")}>See pricing</button></p>;
  const set = (k) => (v) => setPf({ ...pf, [k]: v });
  const personal = () => call("/twin/personal", { method: "POST", token, body: pf }).then(setTw).catch((e) => setOut(e.message));
  return (
    <>
      <h2>Pro dashboard</h2>
      <div className="row">{["overview", "personal", "experiments", "billing"].map((t) => <button key={t} className={"btn" + (tab === t ? " main" : "")} onClick={() => setTab(t)}>{t}</button>)}</div>
      {tab === "overview" && <div className="tiles">{[["Account", me.email], ["Access", me.role], ["Unlocked", "All systems, CSV upload, experiments, full evidence list"], ["Mode", "Test billing, simulated data"]].map(([a, b]) => <div className="tile" key={a}><span className="tag">{a}</span><p style={{ color: "var(--text)", margin: ".3em 0 0" }}>{b}</p></div>)}</div>}
      {tab === "personal" && (
        <>
          <p className="tag">Personal twin from measurements. Use anonymised data only; no real patient data.</p>
          <div className="row">
            <Slide label="Age" value={pf.age} min={20} max={80} onChange={set("age")} />
            <Slide label="Height (cm)" value={pf.height_cm} min={140} max={210} onChange={set("height_cm")} />
            <Slide label="Weight (kg)" value={pf.weight_kg} min={40} max={150} onChange={set("weight_kg")} />
            <button className="btn main" onClick={personal}>Build my twin</button>
          </div>
          {tw && <><pre className="pre">{JSON.stringify(tw.morph, null, 2)}</pre><div className="grid">{ORGANS.filter((id) => tw[id]).map((id) => <Organ key={id} id={id} o={tw[id]} />)}</div></>}
        </>
      )}
      {tab === "experiments" && (
        <div className="row">
          <button className="btn" onClick={() => show(call("/experiments", { token }))}>List my experiments</button>
          <button className="btn main" onClick={() => show(call("/experiments", { method: "POST", token, body: { name: "Lab run", pathogen_id: "respiratory_virus", parameters: { treatment: 0.5, treatment_start: 2 } } }))}>Save a sample experiment</button>
        </div>
      )}
      {tab === "billing" && <div className="row"><button className="btn main" onClick={() => show(call("/billing/checkout", { method: "POST", token, body: { plan: "pro_monthly" } }))}>Renew Pro (TEST MODE)</button></div>}
      {out && <pre className="pre">{out}</pre>}
    </>
  );
}

export default function App() {
  const [page, setPage] = useState("landing");
  const [token, setToken] = useState(() => { try { return localStorage.getItem("gt_token") || ""; } catch { return ""; } });
  const [me, setMe] = useState(null);
  const save = (t) => { setToken(t); try { t ? localStorage.setItem("gt_token", t) : localStorage.removeItem("gt_token"); } catch {} };
  const refresh = () => token ? call("/auth/me", { token }).then(setMe).catch(() => { save(""); setMe(null); }) : setMe(null);
  useEffect(() => { refresh(); }, [token]);
  const nav = [["landing", "Overview"], ["explorer", "Body explorer"], ["lab", "Pathogen lab"], ["research", "Evidence"], ["dashboard", "Workspace"], ["pricing", "Plans"], ["admin", "Governance"]];
  const title = (nav.find((n) => n[0] === page) || [0, "Account"])[1];
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><span className="logo" />Genesis Twin<small>Research platform</small></div>
        {nav.map(([k, l]) => <button key={k} className={"nv" + (page === k ? " on" : "")} onClick={() => setPage(k)}>{l}</button>)}
        <div className="grow" />
        <span className="tag" style={{ padding: "0 10px" }}>Credits: Z-Anatomy, BodyParts3D, NHANES, Human Protein Atlas, Europe PMC</span>
      </aside>
      <div className="col">
        <header className="top">
          <span className="crumb">{title}</span>
          <span className="grow" />
          {me ? <><span className="chip">{me.role}</span><span className="chip">{me.email}</span><button className="btn" onClick={() => { save(""); setPage("landing"); }}>Log out</button></> : <button className="btn main" onClick={() => setPage("auth")}>Log in</button>}
        </header>
        <main>
          {page === "landing" && <Landing go={setPage} />}
          {page === "auth" && <Auth onLogin={(t) => { save(t); setPage("explorer"); }} />}
          {page === "pricing" && <Pricing token={token} me={me} refresh={refresh} go={setPage} />}
          {page === "explorer" && <Explorer />}
          {page === "lab" && <Lab token={token} me={me} />}
          {page === "research" && <Research token={token} />}
          {page === "dashboard" && <Dashboard token={token} me={me} go={setPage} />}
          {page === "admin" && <Admin token={token} me={me} />}
          <div className="row"><button className="btn" onClick={() => window.print()}>Export this page as PDF</button></div>
        </main>
        <footer className="disc">Simulation for research and education. Not medical advice. Vitals are model outputs, not measurements.</footer>
      </div>
    </div>
  );
}
