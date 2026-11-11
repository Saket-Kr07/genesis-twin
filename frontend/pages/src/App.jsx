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

function Organ({ id, o }) {
  return (
    <div className="card" style={{ borderColor: col(o.score) }}>
      <b>{id}</b> <span style={{ color: col(o.score), float: "right" }}>{o.score}</span>
      <small>{Object.entries(o.vitals || {}).map(([k, v]) => `${(v && v.label) || k}: ${fmt(v)}`).join(" · ")}</small>
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
    ? <iframe title="3D viewer" src={VIEWER} style={{ width: "100%", height: 420, border: "1px solid var(--line)", borderRadius: 8 }} />
    : <p className="tag">3D viewer: set VITE_VIEWER_URL to the address of frontend/viewer (npm run dev there).</p>;
}

function Landing({ go }) {
  return (
    <>
      <h1>Genesis Twin</h1>
      <p>A 3D digital twin of the human body for research and education. Explore how age, lifestyle and common infections change organ health, all as simulations.</p>
      <div className="row">
        <button className="btn main" onClick={() => go("explorer")}>Open the explorer</button>
        <button className="btn" onClick={() => go("lab")}>Pathogen lab</button>
        <button className="btn" onClick={() => go("pricing")}>Pricing</button>
      </div>
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
  return (
    <>
      <h2>Pricing</h2>
      <div className="grid">
        <div className="card"><b>Public (free)</b><small>6 main organs, age and lifestyle sliders, 3 infection presets, latest 5 papers.</small></div>
        <div className="card"><b>Professional</b><small>All systems, upload your own pathogen data, experiments, full paper list and model history, API access.</small>
          {token
            ? <button className="btn main" onClick={buy}>Buy Pro (TEST MODE)</button>
            : <button className="btn" onClick={() => go("auth")}>Log in to buy</button>}
        </div>
      </div>
      <p className={me?.role === "pro" ? "ok" : ""}>{msg}{me ? ` Current role: ${me.role}` : ""}</p>
      <p className="tag">Test mode: no real payment is made and no card details are collected.</p>
    </>
  );
}

function Explorer() {
  const [f, setF] = useState({ age: 40, sex: "male", sleep: 7, exercise: 3, smoking: 0, diet: 3 });
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { call("/twin/predict", { method: "POST", body: f }).then((r) => { setD(r); setErr(""); }).catch((e) => setErr(e.message)); }, [f]);
  const set = (k) => (v) => setF({ ...f, [k]: v });
  return (
    <>
      <h2>Explorer: age and lifestyle</h2>
      <Viewer />
      <div className="row">
        <label>Sex<select value={f.sex} onChange={(e) => set("sex")(e.target.value)}><option>male</option><option>female</option></select></label>
        <Slide label="Age" value={f.age} min={20} max={80} onChange={set("age")} />
        <Slide label="Sleep (h)" value={f.sleep} min={3} max={12} onChange={set("sleep")} />
        <Slide label="Exercise (days/week)" value={f.exercise} min={0} max={7} onChange={set("exercise")} />
        <Slide label="Smoking (per day)" value={f.smoking} min={0} max={40} onChange={set("smoking")} />
        <Slide label="Diet (1-5)" value={f.diet} min={1} max={5} onChange={set("diet")} />
      </div>
      <p className="err">{err}</p>
      <div className="grid">{d && ORGANS.filter((id) => d[id]).map((id) => <Organ key={id} id={id} o={d[id]} />)}</div>
    </>
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
  return (
    <>
      <h2>Pathogen lab</h2>
      <p className="tag">Sample parameters, not claims about real outbreaks.</p>
      <Viewer />
      <div className="row">
        <label>Pathogen<select value={p} onChange={(e) => setP(e.target.value)}>{PATHOGENS.map((x) => <option key={x}>{x}</option>)}</select></label>
        <Slide label="Day" value={day} min={0} max={30} step={0.25} onChange={setDay} />
        <Slide label="Treatment strength" value={treatment} min={0} max={1} step={0.05} onChange={setTreatment} />
        <Slide label="Treatment starts on day" value={start} min={0} max={30} onChange={setStart} />
      </div>
      <p className="err">{err}</p>
      {d && (
        <>
          <small className="tag">Model {d.model_version} · load {d.load[i]}</small>
          <svg viewBox="0 0 300 60" style={{ width: "100%", maxWidth: 500, display: "block", margin: "6px 0" }}>
            <polyline fill="none" stroke="#4f8cff" strokeWidth="2" points={d.load.map((v, k) => `${(k / (d.load.length - 1)) * 300},${58 - v * 55}`).join(" ")} />
            <line x1={(i / (d.load.length - 1)) * 300} x2={(i / (d.load.length - 1)) * 300} y1="0" y2="60" stroke="#e74c3c" />
          </svg>
          <div className="grid">
            {ORGANS.map((id) => <Organ key={id} id={id} o={{ score: d.scores[id][i], vitals: d.days[Math.min(30, Math.floor(day))].organs[id].vitals }} />)}
          </div>
        </>
      )}
      <h2>Upload your own pathogen data (Pro)</h2>
      {pro ? (
        <>
          <input type="file" accept=".csv" onChange={(e) => e.target.files[0] && upload(e.target.files[0])} />
          {up && <pre className="pre">{JSON.stringify(up, null, 2)}</pre>}
        </>
      ) : <p className="tag">Log in as a Pro user to upload a CSV (columns: day, load).</p>}
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
      {tab === "overview" && <div className="card"><b>{me.email}</b><small>Role: {me.role}</small><small>Pro: all systems, pathogen upload, experiments, full research list, personal twin.</small></div>}
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
  const tabs = [["landing", "Home"], ["explorer", "Explorer"], ["lab", "Pathogen lab"], ["research", "Research"], ["pricing", "Pricing"], ["dashboard", "Dashboard"], ["admin", "Admin"]];
  return (
    <>
      <div className="banner">Simulation for research and education. Not medical advice.</div>
      <nav>
        {tabs.map(([k, l]) => <button key={k} className={page === k ? "on" : ""} onClick={() => setPage(k)}>{l}</button>)}
        <span style={{ flex: 1 }} />
        {me ? <><span className="tag">{me.email} ({me.role})</span><button onClick={() => { save(""); setPage("landing"); }}>Log out</button></> : <button onClick={() => setPage("auth")}>Log in</button>}
      </nav>
      <main>
        {page === "landing" && <Landing go={setPage} />}
        {page === "auth" && <Auth onLogin={(t) => { save(t); setPage("explorer"); }} />}
        {page === "pricing" && <Pricing token={token} me={me} refresh={refresh} go={setPage} />}
        {page === "explorer" && <Explorer />}
        {page === "lab" && <Lab token={token} me={me} />}
        {page === "research" && <Research token={token} />}
        {page === "dashboard" && <Dashboard token={token} me={me} go={setPage} />}
        {page === "admin" && <Admin token={token} me={me} />}
        <button className="btn" onClick={() => window.print()}>Export this page as PDF (print)</button>
        <p className="tag">Credits: Z-Anatomy and BodyParts3D (3D models), NHANES (health data), Human Protein Atlas (tissue expression), Europe PMC (papers).</p>
      </main>
    </>
  );
}
