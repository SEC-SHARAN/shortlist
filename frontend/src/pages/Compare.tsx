import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Chip, ErrorBox, Page, ScoreBar, Spinner, eduLabel, useAsync } from "../components/ui";
import type { Row } from "../types";

interface Cmp extends Row { strengths: { text: string }[]; weaknesses: { text: string }[]; experience: { total_years: number; relevant_years: number };
  skills: Record<string, { kind: string; credit: number; via: string | null }> }
const TONE: Record<string, "good" | "accent" | "warn" | "bad"> = { exact: "good", equivalent: "accent", semantic: "warn", missing: "bad" };

export default function Compare() {
  const { id } = useParams(); const [sp] = useSearchParams();
  const ids = sp.get("ids") ?? ""; const blind = sp.get("blind") === "1";
  const { data, error, loading } = useAsync(() => api<{ requirements: { skill: string; type: string }[]; candidates: Cmp[] }>(`/jobs/${id}/compare`, { params: { ids, blind: blind || undefined } }), [id, ids, blind]);
  if (loading) return <Spinner />;
  if (!data) return <Page title="Compare"><ErrorBox error={error} /></Page>;
  return (
    <Page title="Side-by-side comparison" actions={<Link to={`/jobs/${id}`} className="btn-ghost">← Ranking</Link>}>
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[720px]">
          <thead><tr className="border-b border-paper-line"><th className="th w-48">&nbsp;</th>{data.candidates.map((c) => <th key={c.id} className="th"><Link className="text-sm font-semibold text-accent-dark hover:underline" to={`/candidates/${c.id}${blind ? "?blind=1" : ""}`}>{c.name}</Link><div className="font-normal">rank #{c.rank}</div></th>)}</tr></thead>
          <tbody>
            <tr><td className="td font-medium">Match score</td>{data.candidates.map((c) => <td key={c.id} className="td"><ScoreBar score={c.score} components={c.components} /></td>)}</tr>
            <tr className="border-t border-paper-line"><td className="td font-medium">Experience</td>{data.candidates.map((c) => <td key={c.id} className="td">{c.experience.total_years} yrs <span className="text-xs text-ink-mute">({c.experience.relevant_years} relevant)</span></td>)}</tr>
            <tr className="border-t border-paper-line"><td className="td font-medium">Education</td>{data.candidates.map((c) => <td key={c.id} className="td">{eduLabel(c.highest_education)}</td>)}</tr>
            {data.requirements.map((r) => (
              <tr key={r.skill} className="border-t border-paper-line"><td className="td font-medium">{r.skill} <span className="text-xs font-normal text-ink-mute">{r.type}</span></td>
                {data.candidates.map((c) => { const m = c.skills[r.skill]; return <td key={c.id} className="td"><Chip tone={TONE[m.kind]}>{m.kind === "missing" ? "missing" : `${Math.round(m.credit * 100)}%`}</Chip>{m.kind !== "exact" && m.via && <span className="ml-1.5 text-xs text-ink-mute">via {m.via}</span>}</td>; })}</tr>))}
            <tr className="border-t border-paper-line"><td className="td font-medium">Strengths</td>{data.candidates.map((c) => <td key={c.id} className="td"><ul className="list-disc space-y-1 pl-4 text-ink-soft">{c.strengths.slice(0, 4).map((s, i) => <li key={i}>{s.text}</li>)}</ul></td>)}</tr>
            <tr className="border-t border-paper-line"><td className="td font-medium">Weaknesses</td>{data.candidates.map((c) => <td key={c.id} className="td"><ul className="list-disc space-y-1 pl-4 text-ink-soft">{c.weaknesses.slice(0, 4).map((s, i) => <li key={i}>{s.text}</li>)}</ul></td>)}</tr>
          </tbody>
        </table>
      </div>
    </Page>
  );
}
