import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Chip, ErrorBox, Page, Spinner, useAsync } from "../components/ui";
import type { Role, User } from "../types";

const ROLES: Role[] = ["admin", "recruiter", "hiring_manager", "viewer"];
interface Log { id: number; at: string; user: string | null; action: string; entity: string | null; entity_id: number | null; detail: Record<string, unknown>; ip: string | null }

export default function Admin() {
  const { can, user } = useAuth();
  const users = useAsync(() => api<User[]>("/users"), []);
  const [action, setAction] = useState("");
  const logs = useAsync(() => api<{ total: number; items: Log[] }>("/audit", { params: { action: action || undefined, limit: 100 } }), [action]);
  const [f, setF] = useState({ email: "", name: "", role: "recruiter" as Role, password: "" });
  const [err, setErr] = useState<unknown>(null);
  if (!can("admin")) return <Navigate to="/" replace />;
  const create = async (e: FormEvent) => { e.preventDefault(); setErr(null); try { await api("/users", { body: f }); setF({ email: "", name: "", role: "recruiter", password: "" }); users.reload(); logs.reload(); } catch (x) { setErr(x); } };
  const patch = async (id: number, body: object) => { setErr(null); try { await api(`/users/${id}`, { method: "PATCH", body }); users.reload(); logs.reload(); } catch (x) { setErr(x); } };
  return (
    <Page title="Administration" sub="User access and the audit trail.">
      <ErrorBox error={err ?? users.error ?? logs.error} />
      <div className="grid gap-5 lg:grid-cols-3">
        <section className="card overflow-x-auto lg:col-span-2"><h2 className="border-b border-paper-line px-4 py-3 font-semibold">Users</h2>
          {users.loading && <Spinner />}
          <table className="w-full"><thead><tr><th className="th">Name</th><th className="th">Email</th><th className="th">Role</th><th className="th">Status</th></tr></thead><tbody>
            {users.data?.map((u) => (
              <tr key={u.id} className="border-t border-paper-line"><td className="td">{u.name}</td><td className="td text-ink-soft">{u.email}</td>
                <td className="td"><select aria-label={`Role for ${u.email}`} className="input py-1" value={u.role} disabled={u.id === user?.id} onChange={(e) => patch(u.id, { role: e.target.value })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></td>
                <td className="td"><button disabled={u.id === user?.id} className="btn-ghost py-1 text-xs" onClick={() => patch(u.id, { is_active: !u.is_active })}>{u.is_active ? "Deactivate" : "Activate"}</button></td></tr>))}</tbody></table></section>
        <form onSubmit={create} className="card space-y-3 p-5"><h2 className="font-semibold">Add user</h2>
          <div><label className="label" htmlFor="un">Name</label><input id="un" required className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
          <div><label className="label" htmlFor="ue">Email</label><input id="ue" type="email" required className="input" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
          <div><label className="label" htmlFor="ur">Role</label><select id="ur" className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value as Role })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></div>
          <div><label className="label" htmlFor="up">Temporary password</label><input id="up" type="password" required minLength={10} className="input" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></div>
          <button className="btn-primary w-full">Create user</button>
          <p className="text-xs text-ink-mute">Admin: everything · Recruiter: jobs, uploads, pipeline · Hiring manager: review, shortlist, notes · Viewer: read-only, names hidden.</p></form>
      </div>
      <section className="card mt-5 overflow-x-auto"><div className="flex items-center justify-between border-b border-paper-line px-4 py-3"><h2 className="font-semibold">Audit log <span className="font-normal text-ink-mute">({logs.data?.total ?? 0})</span></h2>
        <label className="sr-only" htmlFor="af">Filter by action</label><select id="af" className="input w-56" value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="">All actions</option>{["login", "login_failed", "job_created", "job_updated", "resumes_uploaded", "stage_changed", "shortlisted", "export_csv", "export_pdf", "candidate_viewed", "resume_downloaded", "candidate_erased", "user_created", "user_updated"].map((a) => <option key={a}>{a}</option>)}</select></div>
        <table className="w-full min-w-[760px]"><thead><tr><th className="th">Time</th><th className="th">User</th><th className="th">Action</th><th className="th">Entity</th><th className="th">Detail</th><th className="th">IP</th></tr></thead><tbody>
          {logs.data?.items.map((l) => <tr key={l.id} className="border-t border-paper-line"><td className="td font-mono text-xs">{new Date(l.at).toLocaleString()}</td><td className="td">{l.user ?? "—"}</td><td className="td"><Chip tone={l.action === "login_failed" ? "bad" : "mute"}>{l.action}</Chip></td><td className="td text-ink-soft">{l.entity ? `${l.entity} #${l.entity_id ?? ""}` : "—"}</td><td className="td font-mono text-xs text-ink-soft">{Object.keys(l.detail).length ? JSON.stringify(l.detail) : ""}</td><td className="td font-mono text-xs">{l.ip}</td></tr>)}</tbody></table></section>
    </Page>
  );
}
