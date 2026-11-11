import csv, io
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..config import get_settings
from ..db import get_db
from ..deps import current_user, require, audit
from ..engine import skills as sk
from ..models import Job, Candidate, User
from ..schemas import JobIn, JobOut
from .. import services as svc

router = APIRouter(prefix="/api", tags=["jobs"])
WRITE = ("admin", "recruiter")


def _job(db: Session, job_id: int) -> Job:
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


def _out(db: Session, j: Job) -> dict:
    n = db.scalar(select(func.count()).select_from(Candidate).where(Candidate.job_id == j.id)) or 0
    d = JobOut.model_validate(j).model_dump(); d["candidate_count"] = n
    return d


@router.get("/skills/suggest")
def suggest(q: str = Query("", max_length=40), _: User = Depends(current_user)):
    return sk.suggest(q)


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [_out(db, j) for j in db.scalars(select(Job).order_by(Job.id.desc()))]


@router.post("/jobs", status_code=201)
def create_job(body: JobIn, request: Request, user: User = Depends(require(*WRITE)), db: Session = Depends(get_db)):
    j = Job(**{**body.model_dump(), "weights": body.weights.model_dump()}, created_by=user.id)
    db.add(j); db.flush()
    audit(db, user, "job_created", "job", j.id, {"title": j.title}, request); db.commit()
    return _out(db, j)


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return _out(db, _job(db, job_id))


@router.put("/jobs/{job_id}")
def update_job(job_id: int, body: JobIn, request: Request, user: User = Depends(require(*WRITE)), db: Session = Depends(get_db)):
    j = _job(db, job_id)
    for k, v in {**body.model_dump(), "weights": body.weights.model_dump()}.items():
        setattr(j, k, v)
    n = svc.rescore_job(db, j)          # criteria changed -> keep ranking consistent
    audit(db, user, "job_updated", "job", j.id, {"rescored": n}, request); db.commit()
    return _out(db, j)


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int, request: Request, user: User = Depends(require("admin")), db: Session = Depends(get_db)):
    import os
    j = _job(db, job_id)
    for c in j.candidates:
        if c.stored_path and os.path.exists(c.stored_path):
            os.remove(c.stored_path)
    audit(db, user, "job_deleted", "job", j.id, {"title": j.title, "candidates": len(j.candidates)}, request)
    db.delete(j); db.commit()


@router.post("/jobs/{job_id}/resumes")
def upload_resumes(job_id: int, request: Request, files: list[UploadFile] = File(...),
                   user: User = Depends(require(*WRITE)), db: Session = Depends(get_db)):
    s = get_settings()
    j = _job(db, job_id)
    if len(files) > s.max_files_per_request:
        raise HTTPException(413, f"At most {s.max_files_per_request} files per upload")
    results = []
    for f in files:
        data = f.file.read(s.max_upload_mb * 1024 * 1024 + 1)
        results.append(svc.ingest(db, j, f.filename or "resume", data, user))
    audit(db, user, "resumes_uploaded", "job", j.id, {"files": len(files), "ok": sum(r["status"] == "ok" for r in results)}, request)
    db.commit()
    return {"results": results, "ok": sum(r["status"] == "ok" for r in results)}


@router.post("/jobs/{job_id}/rescore")
def rescore(job_id: int, request: Request, user: User = Depends(require(*WRITE)), db: Session = Depends(get_db)):
    j = _job(db, job_id)
    n = svc.rescore_job(db, j)
    audit(db, user, "job_rescored", "job", j.id, {"candidates": n}, request); db.commit()
    return {"rescored": n}


@router.get("/jobs/{job_id}/candidates")
def list_candidates(job_id: int, q: str = "", min_score: float = 0, max_score: float = 100, stage: str | None = None,
                    shortlisted: bool | None = None, skill: list[str] = Query(default=[]), min_years: float = 0,
                    needs_review: bool | None = None, sort: str = "score", order: str = "desc", blind: bool = False,
                    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    _job(db, job_id)
    cands = svc.ranked(db, job_id)
    mask = svc.masked(user, blind)
    rows = []
    for rank, c in enumerate(cands, 1):          # rank is computed over ALL candidates, before filtering
        if not (min_score <= c.score <= max_score): continue
        if stage and c.stage != stage: continue
        if shortlisted is not None and c.shortlisted != shortlisted: continue
        if needs_review is not None and c.needs_review != needs_review: continue
        if (c.parsed or {}).get("total_years", 0) < min_years: continue
        have = c.parsed.get("skills", {})
        if skill:
            names = {k for k in have} | {v["name"].lower() for v in have.values()}
            if not all((sk.canonical(s) or s.lower()) in names or s.lower() in names for s in skill): continue
        if q:
            ql = q.lower()
            hay = [v["name"].lower() for v in have.values()] + [(e.get("title") or "").lower() for e in c.parsed.get("experience", [])]
            if not mask:
                hay += [(c.name or "").lower(), (c.email or "").lower(), c.original_filename.lower()]
            if not any(ql in h for h in hay): continue
        rows.append(svc.candidate_row(c, rank, user, blind))
    keyf = {"score": lambda r: r["score"], "name": lambda r: r["name"].lower(), "years": lambda r: r["total_years"] or 0,
            "created": lambda r: r["created_at"]}.get(sort, lambda r: r["score"])
    rows.sort(key=keyf, reverse=(order != "asc"))
    return {"total": len(rows), "items": rows[offset:offset + limit]}


@router.get("/jobs/{job_id}/compare")
def compare(job_id: int, ids: str = Query(..., description="comma separated candidate ids (2-4)"), blind: bool = False,
            user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = _job(db, job_id)
    try:
        want = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(422, "ids must be integers")
    if not 2 <= len(set(want)) <= 4:
        raise HTTPException(422, "Select between 2 and 4 candidates")
    order = {c.id: i for i, c in enumerate(svc.ranked(db, job_id), 1)}
    cands = [c for c in db.scalars(select(Candidate).where(Candidate.job_id == job_id, Candidate.id.in_(want)))]
    if len(cands) != len(set(want)):
        raise HTTPException(404, "One or more candidates not found for this job")
    reqs = [(s, "required") for s in j.required_skills] + [(s, "preferred") for s in j.preferred_skills]
    out = []
    for c in sorted(cands, key=lambda c: -c.score):
        a = c.analysis
        by = {m["requirement"]: m for m in a["required_matches"] + a["preferred_matches"]}
        out.append({**svc.candidate_row(c, order[c.id], user, blind), "strengths": a["strengths"], "weaknesses": a["weaknesses"],
                    "experience": a["experience"], "skills": {s: {"kind": by[s]["kind"], "credit": by[s]["credit"], "via": by[s]["via"]} for s, _ in reqs}})
    return {"job_id": j.id, "requirements": [{"skill": s, "type": t} for s, t in reqs], "candidates": out}


def _safe_cell(v):
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s     # CSV/Excel formula injection guard


@router.get("/jobs/{job_id}/export.csv")
def export_csv(job_id: int, request: Request, blind: bool = False,
               user: User = Depends(require("admin", "recruiter", "hiring_manager")), db: Session = Depends(get_db)):
    j = _job(db, job_id)
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["rank", "candidate_id", "name", "email", "score", "stage", "shortlisted", "total_years", "education", "matched_required", "missing_required", "explanation"])
    for rank, c in enumerate(svc.ranked(db, job_id), 1):
        r = svc.candidate_row(c, rank, user, blind)
        w.writerow([_safe_cell(x) for x in [rank, c.id, r["name"], r["email"], c.score, c.stage, c.shortlisted, r["total_years"], r["highest_education"],
                                             "; ".join(r["matched"]), "; ".join(r["missing_required"]), c.analysis.get("explanation", "")]])
    audit(db, user, "export_csv", "job", j.id, {"blind": blind}, request); db.commit()
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="job-{j.id}-ranking.csv"'})


@router.get("/jobs/{job_id}/report.pdf")
def export_pdf(job_id: int, request: Request, blind: bool = True, top: int = 20,
               user: User = Depends(require("admin", "recruiter", "hiring_manager")), db: Session = Depends(get_db)):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    j = _job(db, job_id)
    st = getSampleStyleSheet()
    esc = lambda s: str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    rows = [["#", "Candidate", "Score", "Stage", "Matched required skills", "Missing required"]]
    for rank, c in enumerate(svc.ranked(db, job_id)[:top], 1):
        r = svc.candidate_row(c, rank, user, blind)
        rows.append([rank, Paragraph(esc(r["name"]), st["BodyText"]), c.score, c.stage,
                     Paragraph(esc(", ".join(r["matched"])), st["BodyText"]), Paragraph(esc(", ".join(r["missing_required"]) or "-"), st["BodyText"])])
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title=f"Candidate ranking - {j.title}")
    t = Table(rows, colWidths=[24, 130, 40, 60, 260, 230], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2a44")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    doc.build([Paragraph(f"Candidate ranking: {esc(j.title)}", st["Title"]),
               Paragraph("Scores are advisory decision support. Protected attributes are excluded from scoring; hiring decisions are made by people.", st["Italic"]),
               Spacer(1, 12), t])
    audit(db, user, "export_pdf", "job", j.id, {"blind": blind}, request); db.commit()
    return Response(buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="job-{j.id}-report.pdf"'})
