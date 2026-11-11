import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Chip, ErrorBox, Page, Spinner, useAsync } from "../components/ui";
import type { Job } from "../types";

export default function Jobs() {
  const { can } = useAuth();
  const { data, error, loading } = useAsync(() => api<Job[]>("/jobs"), []);
  return (
    <Page title="Job postings" sub="Create a role, upload resumes, review the ranked shortlist."
      actions={can("admin", "recruiter") && <Link to="/jobs/new" className="btn-primary">New job</Link>}>
      <ErrorBox error={error} />{loading && <Spinner />}
      {data && data.length === 0 && <div className="card p-10 text-center text-ink-soft">No jobs yet. Create your first posting to start screening.</div>}
      <div className="grid gap-4 md:grid-cols-2">
        {data?.map((j) => (
          <Link key={j.id} to={`/jobs/${j.id}`} className="card block p-5 transition-shadow hover:shadow-md">
            <div className="flex items-start justify-between gap-3">
              <div><h2 className="text-lg font-semibold">{j.title}</h2><p className="text-sm text-ink-mute">{j.department ?? "No department"}</p></div>
              <Chip tone={j.status === "open" ? "good" : "mute"}>{j.status}</Chip>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">{j.required_skills.slice(0, 7).map((s) => <Chip key={s} tone="accent">{s}</Chip>)}</div>
            <p className="mt-4 font-mono text-sm text-ink-soft">{j.candidate_count} candidate{j.candidate_count === 1 ? "" : "s"}</p>
          </Link>
        ))}
      </div>
    </Page>
  );
}
