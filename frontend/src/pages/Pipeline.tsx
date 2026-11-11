import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Chip, ErrorBox, Page, ReasonModal, Spinner, useAsync } from "../components/ui";
import { Job, Row, STAGES, Stage } from "../types";

export default function Pipeline() {
  const { id } = useParams(); const { can } = useAuth();
  const job = useAsync(() => api<Job>(`/jobs/${id}`), [id]);
  const { data, error, loading, reload } = useAsync(() => api<{ items: Row[] }>(`/jobs/${id}/candidates`, { params: { limit: 200 } }), [id]);
  const [pending, setPending] = useState<{ row: Row; stage: Stage } | null>(null); const [err, setErr] = useState<unknown>(null);
  const move = async (row: Row, stage: Stage, reason?: string) => { setErr(null); try { await api(`/candidates/${row.id}/stage`, { method: "PATCH", body: { stage, reason } }); reload(); } catch (e) { setErr(e); } };
  const request = (row: Row, stage: Stage) => (stage === "hired" || stage === "rejected" ? setPending({ row, stage }) : move(row, stage));
  const canMove = can("admin", "recruiter");
  return (
    <Page title={`Pipeline · ${job.data?.title ?? ""}`} sub="Moving a candidate is always a manual action. Hiring or rejecting requires a written reason." actions={<Link to={`/jobs/${id}`} className="btn-ghost">← Ranking</Link>}>
      <ErrorBox error={error ?? err} />{loading && <Spinner />}
      <div className="grid gap-3 overflow-x-auto pb-2 md:grid-cols-6" style={{ gridAutoFlow: "column", gridAutoColumns: "minmax(200px, 1fr)" }}>
        {STAGES.map((s) => {
          const col = data?.items.filter((r) => r.stage === s) ?? [];
          return (
            <section key={s} aria-label={s} className="rounded-xl bg-white/60 p-2">
              <h2 className="mb-2 flex items-center justify-between px-1 text-sm font-semibold capitalize">{s}<span className="font-mono text-xs text-ink-mute">{col.length}</span></h2>
              <div className="space-y-2">{col.map((r) => (
                <div key={r.id} className="card p-3">
                  <div className="flex items-start justify-between gap-2"><Link to={`/candidates/${r.id}`} className="text-sm font-medium text-accent-dark hover:underline">{r.name}</Link><span className="font-mono text-sm">{r.score.toFixed(0)}</span></div>
                  <div className="mt-1 flex flex-wrap gap-1">{r.shortlisted && <Chip tone="warn">★</Chip>}{r.needs_review && <Chip tone="warn">review</Chip>}</div>
                  {canMove && <select aria-label={`Move ${r.name}`} className="input mt-2 py-1 text-xs" value={r.stage} onChange={(e) => request(r, e.target.value as Stage)}>{STAGES.map((x) => <option key={x}>{x}</option>)}</select>}
                </div>))}</div>
            </section>
          );
        })}
      </div>
      <ReasonModal open={!!pending} title={pending ? `Mark ${pending.row.name} as ${pending.stage}` : ""} onCancel={() => setPending(null)} onSubmit={(r) => { const p = pending!; setPending(null); move(p.row, p.stage, r); }} />
    </Page>
  );
}
