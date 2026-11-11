import { FormEvent, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, download } from "../api";
import { useAuth } from "../auth";
import { COMP_LABEL, Chip, ErrorBox, Page, ReasonModal, ScoreBar, Spinner, eduLabel, useAsync } from "../components/ui";
import { Detail, Match, STAGES, Stage } from "../types";

const KIND: Record<string, { tone: "good" | "accent" | "warn" | "bad"; label: string }> = {
  exact: { tone: "good", label: "Direct match" }, equivalent: { tone: "accent", label: "Equivalent" }, semantic: { tone: "warn", label: "Semantic" }, missing: { tone: "bad", label: "Not found" },
};

function MatchTable({ title, rows }: { title: string; rows: Match[] }) {
  if (!rows.length) return null;
  return (
    <div className="card overflow-x-auto">
      <h3 className="border-b border-paper-line px-4 py-3 font-semibold">{title}</h3>
      <table className="w-full min-w-[640px]"><thead><tr><th className="th">Requirement</th><th className="th">Result</th><th className="th">Credit</th><th className="th">Evidence from resume</th></tr></thead>
        <tbody>{rows.map((m) => (
          <tr key={m.requirement} className="border-t border-paper-line">
            <td className="td font-medium">{m.requirement}</td>
            <td className="td"><Chip tone={KIND[m.kind].tone}>{KIND[m.kind].label}</Chip>{m.via && m.via !== m.requirement && <div className="mt-1 text-xs text-ink-mute">via {m.via}</div>}</td>
            <td className="td font-mono">{Math.round(m.credit * 100)}%</td>
            <td className="td text-ink-soft">{m.evidence ? <q className="italic">{m.evidence}</q> : <span className="text-ink-mute">No supporting text found</span>}</td>
          </tr>))}</tbody></table>
    </div>
  );
}

export default function CandidatePage() {
  const { cid } = useParams(); const [sp] = useSearchParams(); const blind = sp.get("blind") === "1";
  const { can } = useAuth();
  const { data: d, error, loading, reload } = useAsync(() => api<Detail>(`/candidates/${cid}`, { params: { blind: blind || undefined } }), [cid, blind]);
  const [pending, setPending] = useState<Stage | null>(null); const [note, setNote] = useState(""); const [err, setErr] = useState<unknown>(null);
  if (loading && !d) return <Spinner />;
  if (!d) return <Page title="Candidate"><ErrorBox error={error} /></Page>;
  const a = d.analysis; const p = d.parsed;
  const run = async (fn: () => Promise<unknown>) => { setErr(null); try { await fn(); reload(); } catch (e) { setErr(e); } };
  const setStage = (s: Stage, reason?: string) => run(() => api(`/candidates/${d.id}/stage`, { method: "PATCH", body: { stage: s, reason } }));
  const onStage = (s: Stage) => (s === "hired" || s === "rejected" ? setPending(s) : setStage(s));
  const addNote = (e: FormEvent) => { e.preventDefault(); if (note.trim()) run(async () => { await api(`/candidates/${d.id}/notes`, { body: { text: note } }); setNote(""); }); };

  return (
    <Page title={d.name} sub={<>{d.email ?? "Contact hidden"} {d.phone ? `· ${d.phone}` : ""} · rank #{d.rank} for this job</>}
      actions={<>
        <Link to={`/jobs/${d.job_id}`} className="btn-ghost">← Ranking</Link>
        {can("admin", "recruiter", "hiring_manager") && <button className="btn-ghost" onClick={() => run(() => api(`/candidates/${d.id}/shortlist`, { method: "PATCH", body: { shortlisted: !d.shortlisted } }))}>{d.shortlisted ? "★ Shortlisted" : "☆ Shortlist"}</button>}
        {can("admin", "recruiter", "hiring_manager") && <button className="btn-ghost" onClick={() => run(() => download(`/candidates/${d.id}/file`, {}, d.filename))}>Original file</button>}
      </>}>
      <ErrorBox error={err} />
      {(a.needs_manual_review || p.warnings.length > 0) && (
        <div role="note" className="mb-4 rounded-lg border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-warn"><strong>Review the original resume.</strong> {p.warnings.join(" ")}</div>
      )}
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <section className="card p-5">
            <div className="flex flex-wrap items-center gap-6"><ScoreBar score={d.score} components={d.components} />
              <p className="min-w-60 flex-1 text-sm text-ink-soft">{a.explanation}</p></div>
            {a.ai_summary && <div className="mt-4 rounded-lg bg-accent-soft p-3 text-sm"><div className="mb-1 text-xs font-medium text-accent-dark">AI-assisted summary — verify against the resume</div>{a.ai_summary.summary}
              <ul className="mt-2 list-disc pl-5 text-xs text-ink-soft">{a.ai_summary.quotes.map((q) => <li key={q}>“{q}”</li>)}</ul></div>}
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {Object.entries(a.components).map(([k, c]) => (
                <div key={k}><div className="flex justify-between text-sm"><span>{COMP_LABEL[k]}</span><span className="font-mono text-ink-soft">{c.points}/{c.weight}</span></div>
                  <div className="mt-1 h-1.5 rounded-full bg-paper-line"><div className="h-1.5 rounded-full bg-accent" style={{ width: `${c.score * 100}%` }} /></div>
                  <p className="mt-1 text-xs text-ink-mute">{c.detail}</p></div>))}
            </div>
          </section>

          <div className="grid gap-5 md:grid-cols-2">
            <section className="card p-5"><h3 className="mb-2 font-semibold text-good">Strengths</h3>
              {a.strengths.length === 0 && <p className="text-sm text-ink-mute">None evidenced.</p>}
              <ul className="space-y-3">{a.strengths.map((s, i) => <li key={i} className="text-sm">{s.text}{s.evidence && <q className="mt-0.5 block text-xs italic text-ink-mute">{s.evidence}</q>}</li>)}</ul></section>
            <section className="card p-5"><h3 className="mb-2 font-semibold text-bad">Gaps &amp; weaknesses</h3>
              {a.weaknesses.length === 0 && <p className="text-sm text-ink-mute">None identified against the criteria.</p>}
              <ul className="space-y-3">{a.weaknesses.map((s, i) => <li key={i} className="text-sm">{s.text}{s.evidence && <q className="mt-0.5 block text-xs italic text-ink-mute">{s.evidence}</q>}</li>)}</ul></section>
          </div>

          <MatchTable title="Required skills" rows={a.required_matches} />
          <MatchTable title="Preferred skills" rows={a.preferred_matches} />
          <MatchTable title="Certifications" rows={a.certification_matches} />

          <section className="card p-5"><h3 className="mb-3 font-semibold">Work experience <span className="font-normal text-ink-mute">· {p.total_years} yrs total, ~{a.experience.relevant_years} yrs job-relevant</span></h3>
            {p.experience.length === 0 && <p className="text-sm text-ink-mute">No dated roles detected.</p>}
            <ol className="space-y-4 border-l-2 border-paper-line pl-4">{p.experience.map((e, i) => (
              <li key={i}><div className="font-medium">{e.title ?? e.heading}{e.company && <span className="text-ink-soft"> · {e.company}</span>}</div>
                <div className="font-mono text-xs text-ink-mute">{e.start} → {e.end} ({Math.round(e.months / 12 * 10) / 10} yrs)</div>
                <ul className="mt-1 list-disc pl-5 text-sm text-ink-soft">{e.description.slice(0, 5).map((x, j) => <li key={j}>{x}</li>)}</ul></li>))}</ol></section>

          <div className="grid gap-5 md:grid-cols-2">
            <section className="card p-5"><h3 className="mb-2 font-semibold">Education</h3>{p.education.length === 0 ? <p className="text-sm text-ink-mute">None detected.</p> :
              <ul className="space-y-1 text-sm">{p.education.map((e, i) => <li key={i}>{e.degree} <Chip>{eduLabel(e.level)}</Chip></li>)}</ul>}
              {p.certifications.length > 0 && <><h3 className="mb-2 mt-4 font-semibold">Certifications</h3><ul className="list-disc pl-5 text-sm">{p.certifications.map((c) => <li key={c}>{c}</li>)}</ul></>}</section>
            <section className="card p-5"><h3 className="mb-2 font-semibold">Projects &amp; achievements</h3>
              <ul className="space-y-2 text-sm">{p.projects.map((x) => <li key={x.name}><strong>{x.name}</strong><div className="text-ink-soft">{x.description[0]}</div></li>)}</ul>
              <ul className="mt-3 list-disc pl-5 text-sm text-ink-soft">{p.achievements.slice(0, 6).map((x) => <li key={x}>{x}</li>)}</ul></section>
          </div>
          <section className="card p-5"><h3 className="mb-2 font-semibold">All detected skills</h3>
            <div className="flex flex-wrap gap-1.5">{Object.values(p.skills).map((s) => <Chip key={s.name} tone={s.demonstrated ? "good" : "mute"}>{s.name}</Chip>)}</div>
            <p className="mt-2 text-xs text-ink-mute">Green = used in a role or project. Grey = only listed in a skills section.</p></section>
        </div>

        <aside className="space-y-5">
          <section className="card p-5"><h3 className="mb-3 font-semibold">Pipeline stage</h3>
            <div className="grid grid-cols-2 gap-2">{STAGES.map((s) => (
              <button key={s} disabled={!can("admin", "recruiter") || s === d.stage} onClick={() => onStage(s)} aria-pressed={s === d.stage}
                className={`btn text-xs ${s === d.stage ? "bg-accent text-white" : "border border-paper-line bg-white hover:bg-paper"}`}>{s}</button>))}</div>
            {!can("admin", "recruiter") && <p className="mt-2 text-xs text-ink-mute">Only recruiters can move candidates.</p>}
            {d.decision_reason && <p className="mt-3 rounded-lg bg-paper p-3 text-sm"><span className="text-xs text-ink-mute">Recorded decision reason</span><br />{d.decision_reason}</p>}
            <ol className="mt-4 space-y-1 text-xs text-ink-mute">{d.events.map((e, i) => <li key={i}>{new Date(e.at).toLocaleString()} · {e.from ?? "new"} → <strong>{e.to}</strong>{e.reason && ` — ${e.reason}`}</li>)}</ol></section>
          <section className="card p-5"><h3 className="mb-3 font-semibold">Notes</h3>
            {can("admin", "recruiter", "hiring_manager") && <form onSubmit={addNote} className="mb-3"><label className="sr-only" htmlFor="note">Add note</label><textarea id="note" className="input h-20" placeholder="Add a note for the team" value={note} onChange={(e) => setNote(e.target.value)} /><button className="btn-primary mt-2 w-full" disabled={!note.trim()}>Add note</button></form>}
            <ul className="space-y-3">{d.notes.map((n) => <li key={n.id} className="text-sm">{n.text}<div className="text-xs text-ink-mute">{new Date(n.created_at).toLocaleString()}</div></li>)}</ul></section>
          <p className="text-xs text-ink-mute">Model: {a.model.scorer} · embeddings: {a.model.embedder}{a.model.semantic ? "" : " (lexical fallback — install sentence-transformers for semantic matching)"}</p>
        </aside>
      </div>
      <ReasonModal open={!!pending} title={`Mark as ${pending}`} onCancel={() => setPending(null)} onSubmit={(r) => { const s = pending!; setPending(null); setStage(s, r); }} />
    </Page>
  );
}
