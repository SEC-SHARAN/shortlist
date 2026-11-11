"""Application services: resume ingestion pipeline, (re)scoring, serialisation with privacy masking."""
from __future__ import annotations
import hashlib, os, re, uuid
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select

from .config import get_settings
from .engine import extract, parser, scoring, llm
from .engine.embeddings import get_embedder
from .models import Candidate, Job, User


def job_dict(job: Job) -> dict:
    return {"title": job.title, "description": job.description, "required_skills": job.required_skills,
            "preferred_skills": job.preferred_skills, "certifications": job.certifications,
            "min_years": job.min_years, "min_education": job.min_education, "weights": job.weights}


def safe_filename(name: str) -> str:
    name = os.path.basename(name or "resume")
    return re.sub(r"[\x00-\x1f<>:\"|?*]", "_", name)[:200] or "resume"


def analyse(job: Job, parsed: dict) -> dict:
    result = scoring.score_candidate(parsed, job_dict(job), get_embedder(), date.today())
    ev = {"matched": [m for m in result["required_matches"] if m["credit"] > 0][:8], "missing": result["missing_required"]}
    ai = llm.summarise(parsed.get("scoring_text", ""), ev)
    if ai:
        result["ai_summary"] = {"summary": ai["summary"], "quotes": ai["quotes"], "note": "AI-generated from redacted resume text; quotes verified verbatim. Advisory only."}
    return result


def ingest(db: Session, job: Job, filename: str, data: bytes, user: User) -> dict:
    s = get_settings()
    filename = safe_filename(filename)
    if len(data) == 0:
        return {"filename": filename, "status": "error", "message": "Empty file"}
    if len(data) > s.max_upload_mb * 1024 * 1024:
        return {"filename": filename, "status": "error", "message": f"File exceeds {s.max_upload_mb} MB"}
    digest = hashlib.sha256(data).hexdigest()
    dup = db.scalar(select(Candidate).where(Candidate.job_id == job.id, Candidate.file_sha256 == digest))
    if dup:
        return {"filename": filename, "status": "duplicate", "message": "This exact file was already uploaded for this job", "candidate_id": dup.id}
    try:
        kind = extract.detect_type(data)
        text = extract.extract_text(data, kind)
        parsed = parser.parse_resume(text, use_spacy=s.use_spacy)
        analysis = analyse(job, parsed)
    except extract.ExtractionError as e:
        return {"filename": filename, "status": "error", "message": str(e)}
    except Exception:
        return {"filename": filename, "status": "error", "message": "Unexpected error while analysing this resume"}
    os.makedirs(s.storage_dir, exist_ok=True)
    path = os.path.join(s.storage_dir, f"{uuid.uuid4().hex}.{kind}")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    parsed_store = {k: v for k, v in parsed.items() if k not in ("name", "email", "phone", "links")}
    c = Candidate(job_id=job.id, name=parsed["name"], email=parsed["email"], phone=parsed["phone"], original_filename=filename,
                  stored_path=path, file_sha256=digest, parsed=parsed_store, analysis=analysis, score=analysis["score"],
                  needs_review=analysis["needs_manual_review"])
    c.parsed["links"] = parsed["links"]
    db.add(c); db.flush()
    return {"filename": filename, "status": "ok", "candidate_id": c.id, "score": c.score, "message": "Analysed"}


def rescore_job(db: Session, job: Job) -> int:
    n = 0
    for c in db.scalars(select(Candidate).where(Candidate.job_id == job.id)):
        c.analysis = analyse(job, c.parsed); c.score = c.analysis["score"]; c.needs_review = c.analysis["needs_manual_review"]; n += 1
    return n


# ------------------------------------------------------------------ serialisation
def masked(user: User, blind: bool) -> bool:
    return blind or user.role == "viewer"


def display_name(c: Candidate, mask: bool) -> str:
    if mask:
        return f"Candidate #{c.id}"
    return c.name or f"Unnamed ({c.original_filename})"


def candidate_row(c: Candidate, rank: int, user: User, blind: bool = False) -> dict:
    mask = masked(user, blind)
    a, p = c.analysis or {}, c.parsed or {}
    return {
        "id": c.id, "rank": rank, "name": display_name(c, mask), "email": None if mask else c.email,
        "score": c.score, "stage": c.stage, "shortlisted": c.shortlisted, "needs_review": c.needs_review,
        "total_years": p.get("total_years"), "highest_education": p.get("highest_education"),
        "matched": [m["via"] for m in a.get("required_matches", []) if m["credit"] > 0][:8],
        "missing_required": a.get("missing_required", []), "components": {k: v["points"] for k, v in a.get("components", {}).items()},
        "created_at": c.created_at.isoformat(),
    }


def candidate_detail(c: Candidate, rank: int, user: User, blind: bool = False) -> dict:
    mask = masked(user, blind)
    row = candidate_row(c, rank, user, blind)
    parsed = {k: v for k, v in (c.parsed or {}).items() if k != "scoring_text"}
    if mask:
        parsed["links"] = []
    row.update({
        "phone": None if mask else c.phone, "filename": f"resume-{c.id}" if mask else c.original_filename,
        "parsed": parsed, "analysis": c.analysis, "decision_reason": c.decision_reason, "job_id": c.job_id,
        "notes": [{"id": n.id, "user_id": n.user_id, "text": n.text, "created_at": n.created_at.isoformat()} for n in c.notes],
        "events": [{"from": e.from_stage, "to": e.to_stage, "reason": e.reason, "user_id": e.user_id, "at": e.created_at.isoformat()} for e in c.events],
    })
    return row


def ranked(db: Session, job_id: int) -> list[Candidate]:
    return list(db.scalars(select(Candidate).where(Candidate.job_id == job_id).order_by(Candidate.score.desc(), Candidate.id)))
