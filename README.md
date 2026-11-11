# Shortlist: AI Applicant Tracking System

Upload many PDF/DOCX resumes against a job, get a ranked, **explainable** shortlist, and manage the pipeline. The AI is advisory: every score is traceable to quotes from the resume, protected attributes never reach the scorer, and no candidate is ever advanced or rejected without a human action and recorded reason.

| Layer | Tech |
|---|---|
| Frontend | React 18, TypeScript, Tailwind CSS, Vite, React Router |
| API | Python 3.12, FastAPI, SQLAlchemy 2, JWT auth, RBAC, audit log |
| Database | PostgreSQL 16 (SQLite for local dev/tests) |
| NLP / AI | Rule-based parser + skill taxonomy, **Sentence Transformers** (optional) for semantic matching, **spaCy** (optional) NER fallback, **LLM** (optional, grounded) summaries |

## Architecture

```
 Browser (React SPA) ──HTTPS──▶ nginx ──/api──▶ FastAPI ─────▶ PostgreSQL
                                                  │  └──▶ resume files (0600, uuid names, outside web root)
                                                  ▼
                              app/engine  (pure Python, no web/DB imports)
        extract ─▶ parser ─▶ privacy.scoring_view ─▶ scoring ─▶ (optional) llm
        PDF/DOCX   sections,   drops name/contact/    taxonomy +   grounded summary,
        magic-byte dates,      age proxies            embeddings   quotes verified
        validation skills                             weights      verbatim
```

```
ats/
├── docker-compose.yml  .env.example
├── backend/
│   ├── app/
│   │   ├── main.py config.py db.py models.py schemas.py security.py deps.py services.py
│   │   ├── routers/  auth.py (login, users)  jobs.py (jobs, upload, list, compare, exports)
│   │   │             candidates.py (profile, stage, notes, erase)  admin.py (audit, analytics, health)
│   │   └── engine/   extract.py parser.py skills.py privacy.py embeddings.py scoring.py llm.py
│   ├── tests/        test_engine.py (18 tests, no framework needed)  test_api.py + conftest.py (pytest)
│   ├── scripts/      generate_samples.py  seed_demo.py
│   └── Dockerfile  requirements*.txt
└── frontend/         Vite + React + TS + Tailwind (pages: Login, Jobs, JobForm, JobDetail, Candidate, Compare, Pipeline, Analytics, Admin)
```

## Run locally

**Prerequisites:** Python 3.11+, Node 20+. (Docker optional.)

### 1. Backend (SQLite, zero setup)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
# optional, enables real semantic matching + NER (large download):
# pip install -r requirements-ml.txt && python -m spacy download en_core_web_sm
export ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='ChangeMe-Now-12345'
uvicorn app.main:app --reload            # http://localhost:8000/api/docs
```
Use PostgreSQL locally by setting `DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/ats`.

### 2. Frontend
```bash
cd frontend && npm install && npm run dev   # http://localhost:5173 (proxies /api to :8000)
```
Sign in with the admin credentials, create a job, drop resumes in. For a demo with data:
```bash
cd backend && python scripts/seed_demo.py --email admin@example.com --password 'ChangeMe-Now-12345'
```

### 3. Everything via Docker (PostgreSQL + API + nginx)
```bash
cp .env.example .env     # set POSTGRES_PASSWORD, SECRET_KEY, ADMIN_PASSWORD
docker compose up --build        # UI on http://localhost:8080   (WITH_ML=1 for semantic models)
```

## Tests
```bash
cd backend
python -m unittest tests.test_engine -v   # engine: parsing, matching, fairness, grounding (needs only pdfplumber, python-docx, reportlab)
pytest                                     # engine + full API integration suite (needs requirements-dev.txt)
cd ../frontend && npm run typecheck
```

## How scoring works
Default weights (configurable per job, normalised to 100; criteria a job doesn't use are redistributed):
required skills 40 · preferred skills 15 · experience 20 · education 10 · certifications 5 · overall relevance 10.

* **Beyond keywords:** exact/alias (`Postgres`=`PostgreSQL`, `k8s`=`Kubernetes`) → 100%; related/implied skills get partial credit (`MySQL`→`PostgreSQL` 70%, `Django`→`Python` 80%, `Azure`→`AWS` 65%); with Sentence Transformers installed, unknown requirements are matched to resume sentences by embedding similarity. Skills used in a role/project get full credit; skills only listed get 90%.
* **Experience:** dated roles are merged (overlaps not double-counted); 60% years vs. requirement, 40% share of experience that used job-relevant skills. Employment gaps are not penalised.
* **Explainability:** each requirement shows its match kind, credit, the *via* skill and the evidence sentence; strengths and weaknesses carry quotes; the explanation text is generated deterministically from those facts.

## Responsible-AI controls
* **No protected attributes in scoring:** name, contact, links, gender, DOB/age, marital status, nationality, address, photo, hobbies and graduation/employment years are removed before scoring (`engine/privacy.py`). A counterfactual test changes name/gender/age/graduation year and asserts the score is identical.
* **No fabrication:** the parser only copies text found in the document; missing fields stay empty. Tests assert every evidence string appears in the resume. Optional LLM output is discarded unless all its quotes appear verbatim in the redacted resume, and it can never change a score.
* **Human control:** uploads never change stage; moves are manual; *hired/rejected* require a written reason; low-text/unparseable resumes are flagged "needs manual review".
* **Privacy:** viewers and *blind mode* hide names/contacts/filenames; PII views, downloads and exports are audit-logged; per-candidate erasure deletes the file and data; files are stored with random names, mode 0600, validated by magic bytes, size-limited, zip-bomb-checked, served only through authenticated endpoints.
* **Access:** admin (all) · recruiter (jobs, uploads, pipeline, exports) · hiring_manager (review, shortlist, notes, exports) · viewer (read-only, masked). Passwords use scrypt; 5 failed logins lock an account for 15 min; CSV exports neutralise spreadsheet-formula injection.

## Known limitations & hardening checklist
* Scanned/image-only PDFs are rejected with a clear message; OCR is not included (add Tesseract in `extract.py`).
* The parser is heuristic: unusual layouts can mis-split sections. Always review flagged resumes; the original file is one click away.
* Tables are created with `create_all`; add **Alembic** migrations before changing the schema in production.
* Resume processing is synchronous per request (fine for tens of files). For large batches move `ingest` to a task queue (RQ/Celery).
* Put the app behind HTTPS (reverse proxy/ingress), rotate `SECRET_KEY`, back up the DB and `resumes` volume, and set a data-retention policy appropriate to your jurisdiction (GDPR/DPDP). Move the JWT from `sessionStorage` to an HttpOnly cookie if your threat model requires it.
* Scoring is decision support, not a validated selection instrument. Run an adverse-impact review on your own data before relying on it.
