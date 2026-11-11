export type Role = "admin" | "recruiter" | "hiring_manager" | "viewer";
export const STAGES = ["applied", "screening", "interview", "offer", "hired", "rejected"] as const;
export type Stage = (typeof STAGES)[number];
export const EDU = ["high_school", "diploma", "bachelor", "master", "phd"] as const;
export const EDU_LABEL: Record<string, string> = { high_school: "High school", diploma: "Diploma", bachelor: "Bachelor's", master: "Master's", phd: "PhD" };

export interface User { id: number; email: string; name: string; role: Role; is_active: boolean }
export interface Weights { required_skills: number; preferred_skills: number; experience: number; education: number; certifications: number; semantic: number }
export interface Job {
  id: number; title: string; department?: string | null; description: string; required_skills: string[]; preferred_skills: string[];
  certifications: string[]; min_years: number; min_education: string | null; weights: Weights; status: string; candidate_count: number; created_at: string;
}
export interface Row {
  id: number; rank: number; name: string; email: string | null; score: number; stage: Stage; shortlisted: boolean; needs_review: boolean;
  total_years: number | null; highest_education: string | null; matched: string[]; missing_required: string[]; components: Record<string, number>; created_at: string;
}
export interface Match { requirement: string; kind: "exact" | "equivalent" | "semantic" | "missing"; credit: number; via: string | null; evidence: string | null; relation?: string }
export interface Item { text: string; evidence: string | null }
export interface Analysis {
  score: number; explanation: string; needs_manual_review: boolean; missing_required: string[]; missing_preferred: string[];
  components: Record<string, { weight: number; score: number; points: number; detail: string }>;
  required_matches: Match[]; preferred_matches: Match[]; certification_matches: Match[];
  strengths: Item[]; weaknesses: Item[]; experience: { total_years: number; relevant_years: number; relevance: number; min_years: number };
  ai_summary?: { summary: string; quotes: string[]; note: string }; model: { scorer: string; embedder: string; semantic: boolean };
}
export interface Detail extends Row {
  phone: string | null; filename: string; job_id: number; decision_reason: string | null; analysis: Analysis;
  notes: { id: number; user_id: number; text: string; created_at: string }[];
  events: { from: string | null; to: string; reason: string | null; user_id: number; at: string }[];
  parsed: {
    links: string[]; warnings: string[]; summary_text: string; total_years: number; sections_found: string[];
    experience: { title: string | null; company: string | null; heading: string; start: string; end: string; months: number; description: string[] }[];
    education: { degree: string; level: string }[]; certifications: string[];
    skills: Record<string, { name: string; demonstrated: boolean; evidence: string[] }>;
    projects: { name: string; description: string[] }[]; achievements: string[];
  };
}
