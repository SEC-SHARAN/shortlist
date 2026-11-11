import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { COMP_LABEL, ErrorBox, Page } from "../components/ui";
import { EDU, EDU_LABEL, Job, Weights } from "../types";

const DEFAULT_W: Weights = { required_skills: 40, preferred_skills: 15, experience: 20, education: 10, certifications: 5, semantic: 10 };

function TagInput({ label, value, onChange, suggest }: { label: string; value: string[]; onChange: (v: string[]) => void; suggest?: boolean }) {
  const [text, setText] = useState(""); const [opts, setOpts] = useState<string[]>([]);
  const id = label.replace(/\W/g, "");
  useEffect(() => { if (suggest && text.length > 0) api<string[]>("/skills/suggest", { params: { q: text } }).then(setOpts).catch(() => setOpts([])); else setOpts([]); }, [text, suggest]);
  const add = () => { const t = text.trim(); if (t && !value.some((v) => v.toLowerCase() === t.toLowerCase())) onChange([...value, t]); setText(""); };
  return (
    <div>
      <label className="label" htmlFor={id}>{label}</label>
      <div className="flex gap-2">
        <input id={id} list={`${id}-list`} className="input" value={text} placeholder="Type and press Enter" onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
        <datalist id={`${id}-list`}>{opts.map((o) => <option key={o} value={o} />)}</datalist>
        <button type="button" className="btn-ghost" onClick={add}>Add</button>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {value.map((v) => (
          <span key={v} className="chip bg-accent-soft text-accent-dark">{v}
            <button type="button" aria-label={`Remove ${v}`} className="ml-1.5 opacity-60 hover:opacity-100" onClick={() => onChange(value.filter((x) => x !== v))}>×</button></span>
        ))}
      </div>
    </div>
  );
}

export default function JobForm() {
  const { id } = useParams(); const nav = useNavigate();
  const [f, setF] = useState({ title: "", department: "", description: "", required_skills: [] as string[], preferred_skills: [] as string[], certifications: [] as string[],
    min_years: 0, min_education: "" as string, weights: DEFAULT_W, status: "open" });
  const [error, setError] = useState<unknown>(null); const [busy, setBusy] = useState(false);
  useEffect(() => { if (id) api<Job>(`/jobs/${id}`).then((j) => setF({ ...j, department: j.department ?? "", min_education: j.min_education ?? "" })).catch(setError); }, [id]);
  const total = Object.values(f.weights).reduce((a, b) => a + b, 0) || 1;
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      const body = { ...f, department: f.department || null, min_education: f.min_education || null };
      const j = await api<Job>(id ? `/jobs/${id}` : "/jobs", { method: id ? "PUT" : "POST", body });
      nav(`/jobs/${j.id}`);
    } catch (err) { setError(err); setBusy(false); }
  };
  return (
    <Page title={id ? "Edit job" : "New job"} sub={id ? "Saving re-scores every candidate against the updated criteria." : undefined}>
      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-3">
        <div className="card space-y-4 p-5 lg:col-span-2">
          <ErrorBox error={error} />
          <div className="grid gap-4 sm:grid-cols-2">
            <div><label className="label" htmlFor="t">Title</label><input id="t" required minLength={2} className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></div>
            <div><label className="label" htmlFor="d">Department</label><input id="d" className="input" value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} /></div>
          </div>
          <div><label className="label" htmlFor="desc">Job description</label>
            <textarea id="desc" className="input h-40" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
            <p className="mt-1 text-xs text-ink-mute">Used for semantic relevance. Avoid wording that implies age, gender or other protected attributes.</p></div>
          <TagInput label="Required skills" suggest value={f.required_skills} onChange={(v) => setF({ ...f, required_skills: v })} />
          <TagInput label="Preferred skills" suggest value={f.preferred_skills} onChange={(v) => setF({ ...f, preferred_skills: v })} />
          <TagInput label="Certifications" value={f.certifications} onChange={(v) => setF({ ...f, certifications: v })} />
          <div className="grid gap-4 sm:grid-cols-3">
            <div><label className="label" htmlFor="y">Minimum years of experience</label><input id="y" type="number" min={0} max={50} step={0.5} className="input" value={f.min_years} onChange={(e) => setF({ ...f, min_years: Number(e.target.value) })} /></div>
            <div><label className="label" htmlFor="e">Minimum education</label>
              <select id="e" className="input" value={f.min_education} onChange={(e) => setF({ ...f, min_education: e.target.value })}>
                <option value="">Not required</option>{EDU.map((x) => <option key={x} value={x}>{EDU_LABEL[x]}</option>)}</select></div>
            <div><label className="label" htmlFor="s">Status</label>
              <select id="s" className="input" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option>open</option><option>draft</option><option>closed</option></select></div>
          </div>
        </div>
        <div className="space-y-4">
          <div className="card p-5">
            <h2 className="font-semibold">Scoring weights</h2>
            <p className="mb-3 text-xs text-ink-mute">Relative importance. Normalised to 100; criteria that don't apply to this job are redistributed automatically.</p>
            {(Object.keys(f.weights) as (keyof Weights)[]).map((k) => (
              <div key={k} className="mb-3">
                <div className="flex justify-between text-sm"><label htmlFor={`w-${k}`}>{COMP_LABEL[k]}</label><span className="font-mono text-ink-soft">{((f.weights[k] / total) * 100).toFixed(0)}%</span></div>
                <input id={`w-${k}`} type="range" min={0} max={100} className="w-full accent-accent" value={f.weights[k]} onChange={(e) => setF({ ...f, weights: { ...f.weights, [k]: Number(e.target.value) } })} />
              </div>
            ))}
            <button type="button" className="btn-ghost w-full" onClick={() => setF({ ...f, weights: DEFAULT_W })}>Reset to defaults</button>
          </div>
          <button className="btn-primary w-full" disabled={busy}>{busy ? "Saving…" : id ? "Save & re-score" : "Create job"}</button>
        </div>
      </form>
    </Page>
  );
}
