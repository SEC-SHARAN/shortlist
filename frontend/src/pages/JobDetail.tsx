import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, download } from "../api";
import { useAuth } from "../auth";
import { Chip, ErrorBox, Page, ScoreBar, Spinner, eduLabel, useAsync } from "../components/ui";
import { Job, Row, STAGES } from "../types";

interface UploadResult { filename: string; status: string; message: string }

export default function JobDetail() {
  const { id } = useParams(); const nav = useNavigate(); const { can } = useAuth();
  const [flt, setFlt] = useState({ q: "", min_score: 0, stage: "", shortlisted: false, needs_review: false, blind: false, sort: "score", skill: "" });
  const [picked, setPicked] = useState<number[]>([]);
  const [results, setResults] = useState<UploadResult[] | null>(null);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState<unknown>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const job = useAsync(() => api<Job>(`/jobs/${id}`), [id]);
  const list = useAsync(() => api<{ total: number; items: Row[] }>(`/jobs/${id}/candidates`, { params: {
    q: flt.q, min_score: flt.min_score || undefined, stage: flt.stage, shortlisted: flt.shortlisted || undefined, needs_review: flt.needs_review || undefined,
    blind: flt.blind || undefined, sort: flt.sort, skill: flt.skill ? flt.skill.split(",").map((s) => s.trim()).filter(Boolean) : undefined, limit: 200 } }),
    [id, flt.q, flt.min_score, flt.stage, flt.shortlisted, flt.needs_review, flt.blind, flt.sort, flt.skill]);

  const upload = async (files: FileList | File[]) => {
    const fd = new FormData();
    Array.from(files).forEach((f) => fd.append("files", f));
    setBusy(true); setErr(null);
    try { const r = await api<{ results: UploadResult[] }>(`/jobs/${id}/resumes`, { form: fd }); setResults(r.results); list.reload(); job.reload(); }
    catch (e) { setErr(e); } finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };
  const act = async (fn: () => Promise<unknown>) => { setBusy(true); setErr(null); try { await fn(); list.reload(); } catch (e) { setErr(e); } finally { setBusy(false); } };
  const toggle = (cid: number) => setPicked((p) => (p.includes(cid) ? p.filter((x) => x !== cid) : p.length < 4 ? [...p, cid] : p));
  const j = job.data;
  if (job.loading && !j) return <Spinner />;
  if (!j) return <Page title="Job"><ErrorBox error={job.error} /></Page>;
  const writer = can("admin", "recruiter"); const exporter = can("admin", "recruiter", "hiring_manager");

  return (
    <Page title={j.title} sub={<>{j.department ?? "—"} · {j.candidate_count} candidates · requires {j.min_years || 0}+ yrs</>}
      actions={<>
        <Link to={`/jobs/${id}/pipeline`} className="btn-ghost">Pipeline</Link>
        {writer && <Link to={`/jobs/${id}/edit`} className="btn-ghost">Edit criteria</Link>}
        {exporter && <button className="btn-ghost" onClick={() => act(() => download(`/jobs/${id}/export.csv`, { blind: flt.blind || undefined }, `job-${id}-ranking.csv`))}>Export CSV</button>}
        {exporter && <button className="btn-ghost" onClick={() => act(() => download(`/jobs/${id}/report.pdf`, { blind: true }, `job-${id}-report.pdf`))}>PDF report</button>}
      </>}>
      <div className="mb-4 flex flex-wrap gap-1.5">
        {j.required_skills.map((s) => <Chip key={s} tone="accent">{s}</Chip>)}{j.preferred_skills.map((s) => <Chip key={s}>{s} (preferred)</Chip>)}
      </div>
      <ErrorBox error={err} />

      {writer && (
        <div className="card mb-5 border-dashed p-5 text-center" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); upload(e.dataTransfer.files); }}>
          <p className="text-sm text-ink-soft">Drop PDF or DOCX resumes here (up to 50 files, 10 MB each)</p>
          <input ref={fileRef} type="file" multiple accept=".pdf,.docx" className="sr-only" id="files" onChange={(e) => e.target.files && upload(e.target.files)} />
          <label htmlFor="files" className={`btn-primary mt-3 cursor-pointer ${busy ? "pointer-events-none opacity-50" : ""}`}>{busy ? "Analysing…" : "Choose files"}</label>
          {results && (
            <ul className="mx-auto mt-4 max-w-xl space-y-1 text-left text-sm">
              {results.map((r, i) => <li key={i} className="flex items-center gap-2"><Chip tone={r.status === "ok" ? "good" : r.status === "duplicate" ? "warn" : "bad"}>{r.status}</Chip><span className="truncate">{r.filename}</span><span className="text-ink-mute">{r.status === "ok" ? "" : r.message}</span></li>)}
            </ul>
          )}
        </div>
      )}

      <div className="card mb-4 flex flex-wrap items-end gap-4 p-4">
        <div className="min-w-48 flex-1"><label className="label" htmlFor="q">Search</label><input id="q" className="input" placeholder="Name, skill or job title" value={flt.q} onChange={(e) => setFlt({ ...flt, q: e.target.value })} /></div>
        <div className="w-48"><label className="label" htmlFor="sk">Must have skills (comma)</label><input id="sk" className="input" placeholder="Python, Docker" value={flt.skill} onChange={(e) => setFlt({ ...flt, skill: e.target.value })} /></div>
        <div className="w-36"><label className="label" htmlFor="ms">Min score: {flt.min_score}</label><input id="ms" type="range" min={0} max={100} step={5} className="w-full accent-accent" value={flt.min_score} onChange={(e) => setFlt({ ...flt, min_score: Number(e.target.value) })} /></div>
        <div><label className="label" htmlFor="st">Stage</label><select id="st" className="input" value={flt.stage} onChange={(e) => setFlt({ ...flt, stage: e.target.value })}><option value="">All</option>{STAGES.map((s) => <option key={s}>{s}</option>)}</select></div>
        <div><label className="label" htmlFor="so">Sort</label><select id="so" className="input" value={flt.sort} onChange={(e) => setFlt({ ...flt, sort: e.target.value })}><option value="score">Score</option><option value="years">Experience</option><option value="name">Name</option><option value="created">Newest</option></select></div>
        <label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={flt.shortlisted} onChange={(e) => setFlt({ ...flt, shortlisted: e.target.checked })} /> Shortlisted</label>
        <label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={flt.needs_review} onChange={(e) => setFlt({ ...flt, needs_review: e.target.checked })} /> Needs review</label>
        <label className="flex items-center gap-2 pb-2 text-sm" title="Hide names and contact details to reduce bias while screening"><input type="checkbox" checked={flt.blind} onChange={(e) => setFlt({ ...flt, blind: e.target.checked })} /> Blind mode</label>
        {writer && <button className="btn-ghost" disabled={busy} onClick={() => act(() => api(`/jobs/${id}/rescore`, { method: "POST" }))}>Re-score</button>}
      </div>

      <div className="mb-2 flex items-center justify-between text-sm text-ink-soft">
        <span>{list.data ? `${list.data.total} candidate${list.data.total === 1 ? "" : "s"} · ranked most to least suitable` : ""}</span>
        <button className="btn-primary" disabled={picked.length < 2} onClick={() => nav(`/jobs/${id}/compare?ids=${picked.join(",")}${flt.blind ? "&blind=1" : ""}`)}>Compare selected ({picked.length}/4)</button>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[900px]">
          <thead><tr className="border-b border-paper-line"><th className="th w-8"><span className="sr-only">Select</span></th><th className="th w-12">Rank</th><th className="th">Candidate</th><th className="th">Score</th><th className="th">Matched / missing required skills</th><th className="th">Experience</th><th className="th">Stage</th><th className="th w-10"><span className="sr-only">Shortlist</span></th></tr></thead>
          <tbody>
            {list.loading && !list.data && <tr><td colSpan={8}><Spinner /></td></tr>}
            {list.data?.items.length === 0 && <tr><td colSpan={8} className="p-8 text-center text-sm text-ink-mute">No candidates match. Upload resumes or relax the filters.</td></tr>}
            {list.data?.items.map((r) => (
              <tr key={r.id} className="border-b border-paper-line last:border-0 hover:bg-paper/60">
                <td className="td"><input type="checkbox" aria-label={`Select ${r.name}`} checked={picked.includes(r.id)} onChange={() => toggle(r.id)} /></td>
                <td className="td font-mono text-ink-mute">{r.rank}</td>
                <td className="td"><Link to={`/candidates/${r.id}${flt.blind ? "?blind=1" : ""}`} className="font-medium text-accent-dark hover:underline">{r.name}</Link>
                  {r.needs_review && <div><Chip tone="warn">needs manual review</Chip></div>}</td>
                <td className="td"><ScoreBar score={r.score} components={r.components} /></td>
                <td className="td max-w-sm"><div className="flex flex-wrap gap-1">{r.matched.slice(0, 6).map((s) => <Chip key={s} tone="good">{s}</Chip>)}{r.missing_required.map((s) => <Chip key={s} tone="bad">{s}</Chip>)}</div></td>
                <td className="td text-ink-soft">{r.total_years ?? "—"} yrs<div className="text-xs text-ink-mute">{eduLabel(r.highest_education)}</div></td>
                <td className="td"><Chip tone={r.stage === "rejected" ? "bad" : r.stage === "hired" ? "good" : "mute"}>{r.stage}</Chip></td>
                <td className="td"><button aria-label={r.shortlisted ? "Remove from shortlist" : "Shortlist"} aria-pressed={r.shortlisted} disabled={!can("admin", "recruiter", "hiring_manager")}
                  className={`text-xl leading-none ${r.shortlisted ? "text-warn" : "text-ink-mute/50 hover:text-warn"}`} onClick={() => act(() => api(`/candidates/${r.id}/shortlist`, { method: "PATCH", body: { shortlisted: !r.shortlisted } }))}>{r.shortlisted ? "★" : "☆"}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 flex flex-wrap gap-3 text-xs text-ink-mute">Score bar segments: <span>■ required</span><span>■ preferred</span><span>■ experience</span><span>■ education</span><span>■ certifications</span><span>■ relevance</span></p>
    </Page>
  );
}
