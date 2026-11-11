import { useState } from "react";
import { api } from "../api";
import { ErrorBox, Page, Spinner, useAsync } from "../components/ui";
import type { Job } from "../types";

interface A { totals: { jobs: number; candidates: number; shortlisted: number; avg_score: number | null; needs_review: number }; stages: Record<string, number>;
  score_distribution: { range: string; count: number }[]; top_missing_skills: [string, number][]; top_candidate_skills: [string, number][];
  funnel: { stage: string; count: number }[]; per_job: { job_id: number; title: string; candidates: number; avg_score: number | null }[] }

function Bars({ rows }: { rows: [string, number][] }) {
  const max = Math.max(1, ...rows.map((r) => r[1]));
  return <ul className="space-y-2">{rows.length === 0 && <li className="text-sm text-ink-mute">No data yet.</li>}{rows.map(([k, v]) => (
    <li key={k} className="grid grid-cols-[110px_1fr_32px] items-center gap-2 text-sm"><span className="truncate capitalize">{k}</span><div className="h-2 rounded-full bg-paper-line"><div className="h-2 rounded-full bg-accent" style={{ width: `${(v / max) * 100}%` }} /></div><span className="text-right font-mono text-ink-soft">{v}</span></li>))}</ul>;
}

export default function Analytics() {
  const [jobId, setJobId] = useState("");
  const jobs = useAsync(() => api<Job[]>("/jobs"), []);
  const { data, error, loading } = useAsync(() => api<A>("/analytics/overview", { params: { job_id: jobId || undefined } }), [jobId]);
  return (
    <Page title="Analytics" actions={<><label className="sr-only" htmlFor="aj">Job</label><select id="aj" className="input w-64" value={jobId} onChange={(e) => setJobId(e.target.value)}><option value="">All jobs</option>{jobs.data?.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}</select></>}>
      <ErrorBox error={error} />{loading && !data && <Spinner />}
      {data && <>
        <div className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[["Jobs", data.totals.jobs], ["Candidates", data.totals.candidates], ["Shortlisted", data.totals.shortlisted], ["Average score", data.totals.avg_score ?? "—"], ["Need manual review", data.totals.needs_review]].map(([k, v]) => (
            <div key={String(k)} className="card p-4"><div className="text-sm text-ink-soft">{k}</div><div className="font-mono text-2xl">{v}</div></div>))}
        </div>
        <div className="grid gap-5 md:grid-cols-2">
          <section className="card p-5"><h2 className="mb-3 font-semibold">Recruitment funnel</h2><Bars rows={data.funnel.map((f) => [f.stage, f.count])} /></section>
          <section className="card p-5"><h2 className="mb-3 font-semibold">Score distribution</h2><Bars rows={data.score_distribution.map((s) => [s.range, s.count])} /></section>
          <section className="card p-5"><h2 className="mb-1 font-semibold">Most common missing required skills</h2><p className="mb-3 text-xs text-ink-mute">Useful for sourcing, or for questioning whether a requirement is realistic.</p><Bars rows={data.top_missing_skills} /></section>
          <section className="card p-5"><h2 className="mb-3 font-semibold">Most common candidate skills</h2><Bars rows={data.top_candidate_skills} /></section>
          {!jobId && <section className="card p-5 md:col-span-2"><h2 className="mb-3 font-semibold">By job</h2>
            <table className="w-full"><thead><tr><th className="th">Job</th><th className="th">Candidates</th><th className="th">Avg score</th></tr></thead><tbody>
              {data.per_job.map((j) => <tr key={j.job_id} className="border-t border-paper-line"><td className="td">{j.title}</td><td className="td font-mono">{j.candidates}</td><td className="td font-mono">{j.avg_score ?? "—"}</td></tr>)}</tbody></table></section>}
        </div></>}
    </Page>
  );
}
