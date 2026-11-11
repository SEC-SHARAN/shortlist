from collections import Counter
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user, require
from ..models import AuditLog, Candidate, Job, StageEvent, User, STAGES

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}


@router.get("/audit")
def audit_logs(action: str | None = None, user_email: str | None = None, limit: int = Query(100, le=500), offset: int = 0,
               _: User = Depends(require("admin")), db: Session = Depends(get_db)):
    q = select(AuditLog).order_by(AuditLog.id.desc())
    if action: q = q.where(AuditLog.action == action)
    if user_email: q = q.where(AuditLog.user_email == user_email)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.limit(limit).offset(offset))
    return {"total": total, "items": [{"id": r.id, "at": r.created_at.isoformat(), "user": r.user_email, "action": r.action, "entity": r.entity,
                                       "entity_id": r.entity_id, "detail": r.detail, "ip": r.ip} for r in rows]}


@router.get("/analytics/overview")
def analytics(job_id: int | None = None, _: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Candidate)
    if job_id: q = q.where(Candidate.job_id == job_id)
    cands = list(db.scalars(q))
    stages = Counter(c.stage for c in cands)
    buckets = [0] * 5
    for c in cands: buckets[min(4, int(c.score // 20))] += 1
    miss, have = Counter(), Counter()
    for c in cands:
        miss.update(c.analysis.get("missing_required", []))
        have.update(v["name"] for v in c.parsed.get("skills", {}).values())
    reached = Counter()
    ids = [c.id for c in cands]
    for cid, to in db.execute(select(StageEvent.candidate_id, StageEvent.to_stage).where(StageEvent.candidate_id.in_(ids or [0]))).all():
        reached[to] += 1
    funnel = [{"stage": s, "count": (len(cands) if s == "applied" else reached.get(s, 0))} for s in STAGES]
    scores = [c.score for c in cands]
    per_job = []
    if not job_id:
        for j in db.scalars(select(Job)):
            js = [c.score for c in cands if c.job_id == j.id]
            per_job.append({"job_id": j.id, "title": j.title, "candidates": len(js), "avg_score": round(sum(js) / len(js), 1) if js else None})
    return {"totals": {"jobs": db.scalar(select(func.count()).select_from(Job)), "candidates": len(cands), "shortlisted": sum(c.shortlisted for c in cands),
                       "avg_score": round(sum(scores) / len(scores), 1) if scores else None, "needs_review": sum(c.needs_review for c in cands)},
            "stages": {s: stages.get(s, 0) for s in STAGES}, "score_distribution": [{"range": f"{i*20}-{i*20+20 if i<4 else 100}", "count": n} for i, n in enumerate(buckets)],
            "top_missing_skills": miss.most_common(8), "top_candidate_skills": have.most_common(10), "funnel": funnel, "per_job": per_job}
