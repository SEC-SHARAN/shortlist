import os, sys, pathlib, tempfile
_tmp = tempfile.mkdtemp()
os.environ.update({"DATABASE_URL": f"sqlite:///{_tmp}/test.db", "STORAGE_DIR": f"{_tmp}/files", "DISABLE_ST": "1",
                   "SECRET_KEY": "x" * 40, "ADMIN_EMAIL": "admin@test.io", "ADMIN_PASSWORD": "AdminPass123"})
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _login(client, email, pw):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin@test.io", "AdminPass123")


@pytest.fixture(scope="session")
def users(client, admin):
    out = {}
    for role in ("recruiter", "hiring_manager", "viewer"):
        r = client.post("/api/users", headers=admin, json={"email": f"{role}@test.io", "name": role, "role": role, "password": "Passw0rdPass1"})
        assert r.status_code == 201, r.text
        out[role] = _login(client, f"{role}@test.io", "Passw0rdPass1")
    return out


@pytest.fixture(scope="session")
def samples():
    import generate_samples as gs
    d = pathlib.Path(tempfile.mkdtemp()); gs.main(d)
    return d


JOB = {"title": "Senior Backend Engineer", "description": "Build Python APIs on AWS with FastAPI and PostgreSQL, Docker, Kubernetes, CI/CD.",
       "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Kubernetes"], "preferred_skills": ["Redis", "CI/CD", "Terraform"],
       "certifications": ["AWS Certified Solutions Architect"], "min_years": 4, "min_education": "bachelor"}


@pytest.fixture(scope="session")
def job_with_candidates(client, users, samples):
    h = users["recruiter"]
    job = client.post("/api/jobs", headers=h, json=JOB).json()
    files = [("files", (p.name, p.read_bytes(), "application/octet-stream")) for p in sorted(samples.iterdir())]
    files.append(("files", ("evil.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")))
    r = client.post(f"/api/jobs/{job['id']}/resumes", headers=h, files=files)
    assert r.status_code == 200, r.text
    return job, r.json()
