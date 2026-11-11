"""Configurable, explainable scoring. Pure function of (scoring_view(parsed), job).

Principles
 * Every matched/missing claim is derived from parsed resume content and carries an evidence sentence.
 * Name, contact details, gender, age/graduation year, address etc. are not inputs (see privacy.scoring_view).
 * Employment gaps are NOT penalised. Only relevant, dated experience adds credit.
 * The score is advisory. Nothing here changes a candidate's pipeline stage.
"""
from __future__ import annotations
import re
from datetime import date

from . import skills as sk
from .embeddings import Embedder, get_embedder
from .parser import EDU_LEVELS
from .privacy import scoring_view

MODEL_VERSION = "ats-scorer-1.0"
DEFAULT_WEIGHTS = {"required_skills": 40, "preferred_skills": 15, "experience": 20,
                   "education": 10, "certifications": 5, "semantic": 10}
LISTED_ONLY_FACTOR = 0.90        # skill appears only in a skills list, never in a role/project
SEMANTIC_SKILL_THRESHOLD = 0.62  # only used with a real embedding model
EDU_LABEL = {"high_school": "High school", "diploma": "Diploma", "bachelor": "Bachelor's", "master": "Master's", "phd": "PhD"}


def normalize_weights(w: dict | None) -> dict:
    w = {k: max(0.0, float(v)) for k, v in {**DEFAULT_WEIGHTS, **(w or {})}.items() if k in DEFAULT_WEIGHTS}
    total = sum(w.values()) or 1.0
    return {k: v * 100.0 / total for k, v in w.items()}


def _sentences(view: dict) -> list[str]:
    out = []
    for e in view.get("experience") or []:
        out += e.get("description") or []
    for p in view.get("projects") or []:
        out += [p.get("name", "")] + (p.get("description") or [])
    out += (view.get("summary_text") or "").split(". ")
    return [s for s in out if len(s) > 15]


def match_requirement(req: str, view: dict, emb: Embedder, raw_sentences: list[str]) -> dict:
    """Return {requirement, kind, credit, via, evidence}. kind in exact|equivalent|semantic|missing."""
    t = sk.taxonomy()
    have = view.get("skills") or {}
    key = sk.canonical(req)
    res = {"requirement": req, "kind": "missing", "credit": 0.0, "via": None, "evidence": None}
    if key:
        if key in have:
            d = have[key]
            return {**res, "kind": "exact", "via": d["name"], "evidence": (d["evidence"] or [None])[0],
                    "credit": 1.0 if d.get("demonstrated") else LISTED_ONLY_FACTOR,
                    "demonstrated": bool(d.get("demonstrated"))}
        best = None
        for other, d in have.items():
            for w, why in ((t["equiv"].get(key, {}).get(other), "equivalent"), (t["implies"].get(other, {}).get(key), "implied")):
                if w and (best is None or w > best[0]):
                    best = (w, other, why)
        if best:
            w, other, why = best
            d = have[other]
            return {**res, "kind": "equivalent", "credit": round(w * (1.0 if d.get("demonstrated") else LISTED_ONLY_FACTOR), 3),
                    "via": d["name"], "relation": why, "evidence": (d["evidence"] or [None])[0]}
    else:  # skill not in taxonomy: try literal phrase in resume text
        pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(req.strip()) + r"(?![A-Za-z0-9])", re.I)
        for s in raw_sentences + [view.get("summary_text") or ""]:
            if pat.search(s):
                return {**res, "kind": "exact", "credit": 1.0, "via": req, "evidence": s[:240]}
    if emb.semantic and raw_sentences:
        sim, sent = emb.best_sentence(req, raw_sentences)
        if sim >= SEMANTIC_SKILL_THRESHOLD:
            return {**res, "kind": "semantic", "credit": round(min(0.7, sim - 0.1), 3), "via": "semantic similarity",
                    "evidence": sent[:240], "similarity": round(sim, 3)}
    return res


def _cert_match(req: str, view: dict) -> dict | None:
    norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", s.lower())
    rt = set(norm(req).split()) - {"certified", "certification", "certificate", "professional", "the", "of", "a"}
    pool = list(view.get("certifications") or []) + [l for l in (view.get("certification_lines") or [])]
    for c in pool:
        if norm(req).strip() in norm(c):
            return {"requirement": req, "kind": "exact", "credit": 1.0, "evidence": c}
        ct = set(norm(c).split())
        if rt and len(rt & ct) / len(rt) >= 0.75:
            return {"requirement": req, "kind": "equivalent", "credit": 0.8, "evidence": c}
    return None


def score_candidate(parsed: dict, job: dict, emb: Embedder | None = None, today: date | None = None) -> dict:
    emb = emb or get_embedder()
    view = scoring_view(parsed)
    weights = normalize_weights(job.get("weights"))
    req = [s for s in (job.get("required_skills") or []) if s.strip()]
    pref = [s for s in (job.get("preferred_skills") or []) if s.strip()]
    certs_req = [s for s in (job.get("certifications") or []) if s.strip()]
    min_years = float(job.get("min_years") or 0)
    min_edu = job.get("min_education") or None
    sents = _sentences(view)

    req_m = [match_requirement(s, view, emb, sents) for s in req]
    pref_m = [match_requirement(s, view, emb, sents) for s in pref]
    cert_m = [(_cert_match(c, view) or {"requirement": c, "kind": "missing", "credit": 0.0, "evidence": None}) for c in certs_req]

    comps: dict[str, dict] = {}

    def frac(ms): return sum(m["credit"] for m in ms) / len(ms)
    if req: comps["required_skills"] = {"score": frac(req_m), "detail": f"{sum(1 for m in req_m if m['credit']>0)}/{len(req)} required skills matched"}
    if pref: comps["preferred_skills"] = {"score": frac(pref_m), "detail": f"{sum(1 for m in pref_m if m['credit']>0)}/{len(pref)} preferred skills matched"}

    # ---- experience: years vs. requirement (60%) + share of experience relevant to this job (40%)
    target = {sk.canonical(s) or s.lower() for s in req + pref}
    exps = view.get("experience") or []
    relevant_months = 0
    for e in exps:
        blob = " ".join([e.get("heading") or ""] + (e.get("description") or []))
        found = set(sk.find_skills(blob)) | {k for k in target if k and not sk.canonical(k) and k in blob.lower()}
        covered = {k for k in found if k in target or any(sk.taxonomy()["equiv"].get(k, {}).get(t) or sk.taxonomy()["implies"].get(k, {}).get(t) for t in target)}
        if covered:
            relevant_months += e.get("months", 0)
    total_years = float(parsed.get("total_years") or 0)
    all_months = sum(e.get("months", 0) for e in exps) or 1
    relevance = min(1.0, relevant_months / all_months) if exps else 0.0
    rel_years = round(relevant_months / 12, 1)
    years_ratio = 1.0 if min_years <= 0 else min(1.0, total_years / min_years)
    if not exps:
        exp_score, exp_detail = 0.0, "No dated work experience found in resume"
    else:
        exp_score = (0.6 * years_ratio + 0.4 * relevance) if min_years > 0 else (0.5 + 0.5 * relevance)
        exp_detail = f"{total_years} yrs total, ~{rel_years} yrs in roles using job-relevant skills" + (f" (requires {min_years:g})" if min_years else "")
    comps["experience"] = {"score": exp_score, "detail": exp_detail}

    # ---- education (vs minimum level)
    if min_edu in EDU_LEVELS:
        have_lv = view and parsed.get("highest_education")
        if have_lv:
            gap = EDU_LEVELS[min_edu] - EDU_LEVELS[have_lv]
            s = 1.0 if gap <= 0 else 0.5 if gap == 1 else 0.2
            comps["education"] = {"score": s, "detail": f"Highest detected: {EDU_LABEL[have_lv]}; required: {EDU_LABEL[min_edu]}"}
        else:
            comps["education"] = {"score": 0.0, "detail": f"No degree detected; required: {EDU_LABEL[min_edu]}"}
    if certs_req:
        comps["certifications"] = {"score": frac(cert_m), "detail": f"{sum(1 for m in cert_m if m['credit']>0)}/{len(certs_req)} certifications matched"}

    # ---- semantic similarity of redacted resume text with the job description
    jd = (job.get("description") or "").strip()
    sem_text = parsed.get("scoring_text") or ""
    if jd and sem_text:
        raw = emb.similarity(jd, sem_text)
        comps["semantic"] = {"score": emb.calibrate(raw), "detail": f"Overall relevance to job description ({'semantic model' if emb.semantic else 'lexical fallback'}; raw similarity {raw:.2f})"}

    active_w = sum(weights[k] for k in comps) or 1.0
    for k, c in comps.items():
        c["weight"] = round(weights[k] * 100.0 / active_w, 1)      # effective weight after redistributing unused components
        c["points"] = round(c["score"] * c["weight"], 1)
        c["score"] = round(c["score"], 3)
    total = round(sum(c["points"] for c in comps.values()), 1)

    # ---- explanation material (deterministic; every item is traceable to the resume)
    strengths, weaknesses = [], []
    for m in req_m + pref_m:
        if m["kind"] == "exact" and m.get("demonstrated", True) and m["evidence"]:
            strengths.append({"text": f"Demonstrates {m['via']}", "evidence": m["evidence"]})
    strengths = strengths[:6]
    if exps and total_years >= max(min_years, 0.1) and min_years:
        strengths.append({"text": f"{total_years} years of experience (requirement: {min_years:g})", "evidence": exps[0].get("heading")})
    if parsed.get("achievements"):
        strengths.append({"text": "Quantified achievements present", "evidence": parsed["achievements"][0]})
    miss_req = [m["requirement"] for m in req_m if m["credit"] == 0]
    miss_pref = [m["requirement"] for m in pref_m if m["credit"] == 0]
    if miss_req: weaknesses.append({"text": "Missing required: " + ", ".join(miss_req), "evidence": None})
    for m in req_m:
        if m["kind"] == "exact" and not m.get("demonstrated", True):
            weaknesses.append({"text": f"{m['via']} only appears in a skills list, not in any role or project", "evidence": m["evidence"]})
    if min_years and total_years < min_years:
        weaknesses.append({"text": f"{total_years} years of experience vs {min_years:g} required", "evidence": None})
    if min_years and exps and relevance < 0.5:
        weaknesses.append({"text": "Less than half of the experience involves job-relevant skills", "evidence": None})
    if comps.get("education", {}).get("score", 1) < 1:
        weaknesses.append({"text": comps["education"]["detail"], "evidence": None})
    miss_cert = [m["requirement"] for m in cert_m if m["credit"] == 0]
    if miss_cert: weaknesses.append({"text": "Certifications not found: " + ", ".join(miss_cert), "evidence": None})

    eq = [m for m in req_m + pref_m if m["kind"] in ("equivalent", "semantic")]
    parts = [f"Score {total}/100."]
    if req:
        ex = sum(1 for m in req_m if m["kind"] == "exact")
        parts.append(f"{ex} of {len(req)} required skills matched directly" + (f", {sum(1 for m in req_m if m['kind'] in ('equivalent','semantic'))} through equivalent/related skills" if any(m['kind'] in ('equivalent','semantic') for m in req_m) else "") + ".")
    for m in eq[:3]:
        parts.append(f"'{m['via']}' counted toward '{m['requirement']}' at {int(m['credit']*100)}% credit ({m.get('relation') or 'semantic'}).")
    if miss_req: parts.append("Missing: " + ", ".join(miss_req) + ".")
    parts.append(comps["experience"]["detail"] + ".")
    if "education" in comps: parts.append(comps["education"]["detail"] + ".")
    parts.append("Advisory only: protected/personal attributes were excluded; a human makes the hiring decision.")

    needs_review = bool(parsed.get("warnings")) and (parsed.get("text_length", 0) < 300 or not exps)
    return {
        "score": total, "components": comps,
        "required_matches": req_m, "preferred_matches": pref_m, "certification_matches": cert_m,
        "missing_required": miss_req, "missing_preferred": miss_pref,
        "experience": {"total_years": total_years, "relevant_years": rel_years, "relevance": round(relevance, 2), "min_years": min_years},
        "strengths": strengths, "weaknesses": weaknesses, "explanation": " ".join(parts),
        "needs_manual_review": needs_review, "weights_used": {k: round(v, 1) for k, v in weights.items()},
        "model": {"scorer": MODEL_VERSION, "embedder": emb.name, "semantic": emb.semantic},
    }
