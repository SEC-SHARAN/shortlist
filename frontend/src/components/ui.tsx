import { ReactNode, useEffect, useState } from "react";
import { EDU_LABEL } from "../types";

export const scoreTone = (s: number) => (s >= 75 ? "good" : s >= 50 ? "warn" : "bad");
const TONE = { good: "text-good", warn: "text-warn", bad: "text-bad" } as const;

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <div role="status" className="p-8 text-center text-sm text-ink-mute">{label}</div>;
}
export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return <div role="alert" className="rounded-lg border border-bad/30 bg-bad-soft px-4 py-3 text-sm text-bad">{String((error as Error).message ?? error)}</div>;
}
export function Page({ title, actions, children, sub }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-[1280px] px-6 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="text-2xl font-semibold">{title}</h1>{sub && <p className="mt-1 text-sm text-ink-soft">{sub}</p>}</div>
        <div className="flex flex-wrap gap-2">{actions}</div>
      </div>
      {children}
    </div>
  );
}

/** Score + stacked bar of component contributions (so a recruiter can see *why* at a glance). */
const COMP_COLORS: Record<string, string> = { required_skills: "bg-accent", preferred_skills: "bg-[#7E8BEA]", experience: "bg-[#1E8E5A]", education: "bg-[#B7791F]", certifications: "bg-[#8A5BD0]", semantic: "bg-[#8892AA]" };
export const COMP_LABEL: Record<string, string> = { required_skills: "Required skills", preferred_skills: "Preferred skills", experience: "Experience", education: "Education", certifications: "Certifications", semantic: "Overall relevance" };
export function ScoreBar({ score, components }: { score: number; components?: Record<string, number> }) {
  return (
    <div className="w-40">
      <div className={`font-mono text-xl font-medium ${TONE[scoreTone(score)]}`}>{score.toFixed(1)}<span className="text-xs text-ink-mute"> /100</span></div>
      <div className="mt-1 flex h-1.5 w-full overflow-hidden rounded-full bg-paper-line" title="Contribution of each criterion">
        {Object.entries(components ?? {}).map(([k, v]) => <div key={k} className={COMP_COLORS[k]} style={{ width: `${v}%` }} />)}
      </div>
    </div>
  );
}
export const Chip = ({ children, tone = "mute" }: { children: ReactNode; tone?: "good" | "bad" | "mute" | "accent" | "warn" }) => {
  const c = { good: "bg-good-soft text-good", bad: "bg-bad-soft text-bad", mute: "bg-paper text-ink-soft", accent: "bg-accent-soft text-accent-dark", warn: "bg-warn-soft text-warn" }[tone];
  return <span className={`chip ${c}`}>{children}</span>;
};
export const eduLabel = (l: string | null) => (l ? EDU_LABEL[l] ?? l : "—");

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEffect(() => { const f = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", f); return () => window.removeEventListener("keydown", f); }, [onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} className="card w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-3 text-lg font-semibold">{title}</h2>{children}
      </div>
    </div>
  );
}

/** Confirmation modal that collects a written reason (final decisions must be justified by a human). */
export function ReasonModal({ open, title, onCancel, onSubmit }: { open: boolean; title: string; onCancel: () => void; onSubmit: (reason: string) => void }) {
  const [reason, setReason] = useState("");
  return (
    <Modal open={open} onClose={onCancel} title={title}>
      <label className="label" htmlFor="reason">Reason for this decision (required, recorded in the audit trail)</label>
      <textarea id="reason" className="input h-24" value={reason} onChange={(e) => setReason(e.target.value)} />
      <div className="mt-4 flex justify-end gap-2">
        <button className="btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="btn-primary" disabled={reason.trim().length < 10} onClick={() => { onSubmit(reason.trim()); setReason(""); }}>Confirm</button>
      </div>
    </Modal>
  );
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true; setLoading(true);
    fn().then((d) => live && (setData(d), setError(null))).catch((e) => live && setError(e)).finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, loading, reload: () => setTick((t) => t + 1), setData };
}
