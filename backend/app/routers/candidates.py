import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import current_user, require, audit
from ..models import Candidate, Note, StageEvent, User
from ..schemas import StageChange, ShortlistIn, NoteIn
from .. import services as svc

router = APIRouter(prefix="/api/candidates", tags=["candidates"])
NEEDS_REASON = {"hired", "rejected"}


def _cand(db: Session, cid: int) -> Candidate:
    c = db.get(Candidate, cid)
    if not c:
        raise HTTPException(404, "Candidate not found")
    return c


def _rank(db: Session, c: Candidate) -> int:
    return next(i for i, x in enumerate(svc.ranked(db, c.job_id), 1) if x.id == c.id)


@router.get("/{cid}")
def get_candidate(cid: int, request: Request, blind: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _cand(db, cid)
    if not svc.masked(user, blind):
        audit(db, user, "candidate_viewed", "candidate", c.id, request=request); db.commit()   # PII access is logged
    return svc.candidate_detail(c, _rank(db, c), user, blind)


@router.patch("/{cid}/stage")
def change_stage(cid: int, body: StageChange, request: Request, user: User = Depends(require("admin", "recruiter")), db: Session = Depends(get_db)):
    """Human-in-the-loop: the system never moves candidates itself; final decisions need a recorded reason."""
    c = _cand(db, cid)
    if body.stage in NEEDS_REASON and len((body.reason or "").strip()) < 10:
        raise HTTPException(422, "A written reason (min 10 characters) is required to mark a candidate hired or rejected")
    if body.stage == c.stage:
        return svc.candidate_detail(c, _rank(db, c), user)
    db.add(StageEvent(candidate_id=c.id, from_stage=c.stage, to_stage=body.stage, reason=body.reason, user_id=user.id))
    prev, c.stage = c.stage, body.stage
    if body.stage in NEEDS_REASON:
        c.decision_reason, c.decided_by = body.reason, user.id
    audit(db, user, "stage_changed", "candidate", c.id, {"from": prev, "to": body.stage}, request); db.commit()
    db.refresh(c)
    return svc.candidate_detail(c, _rank(db, c), user)


@router.patch("/{cid}/shortlist")
def shortlist(cid: int, body: ShortlistIn, request: Request, user: User = Depends(require("admin", "recruiter", "hiring_manager")), db: Session = Depends(get_db)):
    c = _cand(db, cid)
    c.shortlisted = body.shortlisted
    audit(db, user, "shortlisted" if body.shortlisted else "unshortlisted", "candidate", c.id, request=request); db.commit()
    return {"id": c.id, "shortlisted": c.shortlisted}


@router.post("/{cid}/notes", status_code=201)
def add_note(cid: int, body: NoteIn, request: Request, user: User = Depends(require("admin", "recruiter", "hiring_manager")), db: Session = Depends(get_db)):
    c = _cand(db, cid)
    n = Note(candidate_id=c.id, user_id=user.id, text=body.text.strip())
    db.add(n); db.flush(); audit(db, user, "note_added", "candidate", c.id, request=request); db.commit()
    return {"id": n.id, "text": n.text, "user_id": user.id, "created_at": n.created_at.isoformat()}


@router.get("/{cid}/file")
def download(cid: int, request: Request, user: User = Depends(require("admin", "recruiter", "hiring_manager")), db: Session = Depends(get_db)):
    c = _cand(db, cid)
    if not c.stored_path or not os.path.exists(c.stored_path):
        raise HTTPException(404, "Original file no longer available")
    audit(db, user, "resume_downloaded", "candidate", c.id, request=request); db.commit()
    return FileResponse(c.stored_path, filename=c.original_filename, headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/{cid}", status_code=204)
def erase(cid: int, request: Request, user: User = Depends(require("admin", "recruiter")), db: Session = Depends(get_db)):
    """Right-to-erasure: removes the file and all personal data; the audit entry keeps only the id."""
    c = _cand(db, cid)
    if c.stored_path and os.path.exists(c.stored_path):
        os.remove(c.stored_path)
    audit(db, user, "candidate_erased", "candidate", c.id, {"job_id": c.job_id}, request)
    db.delete(c); db.commit()
