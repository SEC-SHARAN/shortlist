"""Create a demo job and upload sample resumes through the running API.
   python scripts/seed_demo.py --url http://localhost:8000 --email admin@example.com --password '...'"""
import argparse, pathlib, tempfile, httpx, generate_samples as gs

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://localhost:8000"); ap.add_argument("--email", required=True); ap.add_argument("--password", required=True)
a = ap.parse_args()
with httpx.Client(base_url=a.url, timeout=60) as c:
    tok = c.post("/api/auth/login", json={"email": a.email, "password": a.password}).raise_for_status().json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    job = c.post("/api/jobs", headers=h, json={
        "title": "Senior Backend Engineer", "department": "Platform",
        "description": "Build scalable Python APIs on AWS using FastAPI and PostgreSQL. Containerise services with Docker and run on Kubernetes with CI/CD.",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Kubernetes"], "preferred_skills": ["Redis", "CI/CD", "Terraform"],
        "certifications": ["AWS Certified Solutions Architect"], "min_years": 4, "min_education": "bachelor"}).raise_for_status().json()
    d = pathlib.Path(tempfile.mkdtemp()); gs.main(d)
    files = [("files", (p.name, p.read_bytes())) for p in sorted(d.iterdir())]
    r = c.post(f"/api/jobs/{job['id']}/resumes", headers=h, files=files).raise_for_status().json()
    print("Created job", job["id"], "->", r["ok"], "resumes analysed. Open the UI and look at the ranking.")
