"""API integration tests (SQLite in-memory-file DB; run with `pytest`)."""
from conftest import JOB


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_auth_required_and_login(client, admin):
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/auth/me", headers=admin).json()["role"] == "admin"
    assert client.post("/api/auth/login", json={"email": "admin@test.io", "password": "wrong"}).status_code == 401


def test_lockout_after_repeated_failures(client, users, admin):
    client.post("/api/users", headers=admin, json={"email": "lock@test.io", "name": "L", "role": "viewer", "password": "Passw0rdPass1"})
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "lock@test.io", "password": "bad"})
    assert client.post("/api/auth/login", json={"email": "lock@test.io", "password": "Passw0rdPass1"}).status_code == 429


def test_password_policy(client, admin):
    r = client.post("/api/users", headers=admin, json={"email": "weak@test.io", "name": "W", "role": "viewer", "password": "short"})
    assert r.status_code == 422


def test_rbac_matrix(client, users, admin):
    assert client.post("/api/jobs", headers=users["viewer"], json=JOB).status_code == 403
    assert client.post("/api/jobs", headers=users["hiring_manager"], json=JOB).status_code == 403
    assert client.get("/api/users", headers=users["recruiter"]).status_code == 403
    assert client.get("/api/audit", headers=users["recruiter"]).status_code == 403
    assert client.get("/api/audit", headers=admin).status_code == 200


def test_job_validation(client, users):
    r = client.post("/api/jobs", headers=users["recruiter"], json={"title": "x"})
    assert r.status_code == 422
    r = client.post("/api/jobs", headers=users["recruiter"], json={**JOB, "min_education": "wizard"})
    assert r.status_code == 422
    assert client.get("/api/jobs/99999", headers=users["recruiter"]).status_code == 404


def test_upload_results_and_ranking(client, users, job_with_candidates):
    job, up = job_with_candidates
    statuses = {r["filename"]: r["status"] for r in up["results"]}
    assert statuses["evil.pdf"] == "error"
    assert up["ok"] == 3
    items = client.get(f"/api/jobs/{job['id']}/candidates", headers=users["recruiter"]).json()["items"]
    assert [i["name"] for i in items] == ["Priya Raman", "Arjun Mehta", "Meera Iyer"]
    assert [i["rank"] for i in items] == [1, 2, 3]
    assert items[0]["score"] > items[1]["score"] > items[2]["score"]


def test_duplicate_upload_detected(client, users, job_with_candidates, samples):
    job, _ = job_with_candidates
    p = samples / "priya_raman.pdf"
    r = client.post(f"/api/jobs/{job['id']}/resumes", headers=users["recruiter"], files=[("files", (p.name, p.read_bytes()))])
    assert r.json()["results"][0]["status"] == "duplicate"


def test_filters_and_search(client, users, job_with_candidates):
    jid, h = job_with_candidates[0]["id"], users["recruiter"]
    g = lambda **p: client.get(f"/api/jobs/{jid}/candidates", headers=h, params=p).json()
    assert g(min_score=80)["total"] == 1
    assert g(skill=["Kubernetes"])["total"] == 1 and g(skill=["reactjs"])["items"][0]["name"] == "Meera Iyer"
    assert g(q="priya")["total"] == 1
    assert g(sort="name", order="asc")["items"][0]["name"] == "Arjun Mehta"
    assert g(min_score=80)["items"][0]["rank"] == 1       # rank is global, not filtered position


def test_candidate_detail_explainability(client, users, job_with_candidates):
    jid = job_with_candidates[0]["id"]
    cid = client.get(f"/api/jobs/{jid}/candidates", headers=users["recruiter"]).json()["items"][1]["id"]   # Arjun
    d = client.get(f"/api/candidates/{cid}", headers=users["recruiter"]).json()
    pg = {m["requirement"]: m for m in d["analysis"]["required_matches"]}
    assert pg["PostgreSQL"]["kind"] == "equivalent" and pg["PostgreSQL"]["evidence"]
    assert "Kubernetes" in d["analysis"]["missing_required"]
    assert "scoring_text" not in d["parsed"]
    assert "Advisory" in d["analysis"]["explanation"]


def test_privacy_masking_for_viewer_and_blind_mode(client, users, job_with_candidates):
    jid = job_with_candidates[0]["id"]
    v = client.get(f"/api/jobs/{jid}/candidates", headers=users["viewer"]).json()["items"]
    assert all(i["name"].startswith("Candidate #") and i["email"] is None for i in v)
    cid = v[0]["id"]
    d = client.get(f"/api/candidates/{cid}", headers=users["viewer"]).json()
    assert d["email"] is None and d["phone"] is None and d["parsed"]["links"] == [] and d["filename"].startswith("resume-")
    assert client.get(f"/api/candidates/{cid}/file", headers=users["viewer"]).status_code == 403
    b = client.get(f"/api/jobs/{jid}/candidates", headers=users["recruiter"], params={"blind": True}).json()["items"]
    assert all(i["name"].startswith("Candidate #") for i in b)
    assert client.get(f"/api/jobs/{jid}/candidates", headers=users["viewer"], params={"q": "priya"}).json()["total"] == 0   # can't search hidden names


def test_stage_changes_require_reason_and_are_human_only(client, users, job_with_candidates):
    jid = job_with_candidates[0]["id"]
    cid = client.get(f"/api/jobs/{jid}/candidates", headers=users["recruiter"]).json()["items"][2]["id"]
    assert client.patch(f"/api/candidates/{cid}/stage", headers=users["recruiter"], json={"stage": "interview"}).status_code == 200
    assert client.patch(f"/api/candidates/{cid}/stage", headers=users["recruiter"], json={"stage": "rejected"}).status_code == 422
    assert client.patch(f"/api/candidates/{cid}/stage", headers=users["hiring_manager"], json={"stage": "interview"}).status_code == 403
    r = client.patch(f"/api/candidates/{cid}/stage", headers=users["recruiter"], json={"stage": "rejected", "reason": "Missing all core backend skills"})
    assert r.status_code == 200 and r.json()["stage"] == "rejected" and len(r.json()["events"]) == 2


def test_shortlist_and_notes(client, users, job_with_candidates):
    jid = job_with_candidates[0]["id"]
    cid = client.get(f"/api/jobs/{jid}/candidates", headers=users["hiring_manager"]).json()["items"][0]["id"]
    assert client.patch(f"/api/candidates/{cid}/shortlist", headers=users["hiring_manager"], json={"shortlisted": True}).status_code == 200
    assert client.post(f"/api/candidates/{cid}/notes", headers=users["hiring_manager"], json={"text": "Strong systems background"}).status_code == 201
    assert client.patch(f"/api/candidates/{cid}/shortlist", headers=users["viewer"], json={"shortlisted": False}).status_code == 403
    assert client.get(f"/api/jobs/{jid}/candidates", headers=users["recruiter"], params={"shortlisted": True}).json()["total"] == 1


def test_compare(client, users, job_with_candidates):
    jid = job_with_candidates[0]["id"]
    ids = ",".join(str(i["id"]) for i in client.get(f"/api/jobs/{jid}/candidates", headers=users["recruiter"]).json()["items"][:2])
    r = client.get(f"/api/jobs/{jid}/compare", headers=users["recruiter"], params={"ids": ids}).json()
    assert len(r["candidates"]) == 2 and r["candidates"][0]["skills"]["Kubernetes"]["kind"] == "exact"
    assert client.get(f"/api/jobs/{jid}/compare", headers=users["recruiter"], params={"ids": "1"}).status_code == 422


def test_weights_update_rescores(client, users, job_with_candidates):
    j = job_with_candidates[0]; h = users["recruiter"]
    before = client.get(f"/api/jobs/{j['id']}/candidates", headers=h).json()["items"][1]["score"]
    body = {**JOB, "weights": {"required_skills": 5, "preferred_skills": 0, "experience": 90, "education": 5, "certifications": 0, "semantic": 0}}
    assert client.put(f"/api/jobs/{j['id']}", headers=h, json=body).status_code == 200
    after = client.get(f"/api/jobs/{j['id']}/candidates", headers=h).json()["items"]
    assert any(i["score"] != before for i in after)


def test_exports(client, users, job_with_candidates):
    jid, h = job_with_candidates[0]["id"], users["recruiter"]
    csv_r = client.get(f"/api/jobs/{jid}/export.csv", headers=h)
    assert csv_r.status_code == 200 and "Priya Raman" in csv_r.text
    assert "Priya" not in client.get(f"/api/jobs/{jid}/export.csv", headers=h, params={"blind": True}).text
    assert client.get(f"/api/jobs/{jid}/report.pdf", headers=h).content[:5] == b"%PDF-"
    assert client.get(f"/api/jobs/{jid}/export.csv", headers=users["viewer"]).status_code == 403


def test_analytics(client, users, job_with_candidates):
    r = client.get("/api/analytics/overview", headers=users["recruiter"], params={"job_id": job_with_candidates[0]["id"]}).json()
    assert r["totals"]["candidates"] == 3 and sum(b["count"] for b in r["score_distribution"]) == 3
    assert r["top_missing_skills"]


def test_erasure_removes_file_and_is_audited(client, users, admin, job_with_candidates):
    import os
    jid = job_with_candidates[0]["id"]
    cid = client.get(f"/api/jobs/{jid}/candidates", headers=users["recruiter"]).json()["items"][-1]["id"]
    from app.db import SessionLocal
    from app.models import Candidate
    with SessionLocal() as db:
        path = db.get(Candidate, cid).stored_path
    assert os.path.exists(path)
    assert client.delete(f"/api/candidates/{cid}", headers=users["recruiter"]).status_code == 204
    assert not os.path.exists(path) and client.get(f"/api/candidates/{cid}", headers=users["recruiter"]).status_code == 404
    log = client.get("/api/audit", headers=admin, params={"action": "candidate_erased"}).json()
    assert log["total"] >= 1


def test_audit_trail_records_key_actions(client, admin, job_with_candidates):
    actions = {i["action"] for i in client.get("/api/audit", headers=admin, params={"limit": 500}).json()["items"]}
    assert {"login", "login_failed", "job_created", "resumes_uploaded", "user_created"} <= actions
