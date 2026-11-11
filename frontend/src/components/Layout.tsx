import { NavLink, Outlet, Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Spinner } from "./ui";

export default function Layout() {
  const { user, loading, logout, can } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  const link = ({ isActive }: { isActive: boolean }) => `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "bg-accent-soft text-accent-dark" : "text-ink-soft hover:bg-paper"}`;
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-paper-line bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1280px] items-center gap-6 px-6 py-3">
          <div className="text-lg font-bold tracking-tight">Shortlist<span className="text-accent">.</span></div>
          <nav className="flex gap-1" aria-label="Main">
            <NavLink to="/" end className={link}>Jobs</NavLink>
            <NavLink to="/analytics" className={link}>Analytics</NavLink>
            {can("admin") && <NavLink to="/admin" className={link}>Admin</NavLink>}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-ink-soft">{user.name} · <span className="font-mono text-xs">{user.role}</span></span>
            <button className="btn-ghost" onClick={logout}>Sign out</button>
          </div>
        </div>
      </header>
      <main><Outlet /></main>
      <footer className="mx-auto max-w-[1280px] px-6 pb-8 text-xs text-ink-mute">
        Scores are advisory decision support. Name, contact details, gender, age and other personal attributes are excluded from scoring; final hiring decisions are made by people.
      </footer>
    </div>
  );
}
