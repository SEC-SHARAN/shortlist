"""Skill taxonomy: canonical names, aliases, equivalence groups and implications.

Matching beyond keywords works in three tiers (see scoring.match_requirement):
  1. exact / alias            -> full credit        ("Postgres" == "PostgreSQL")
  2. equivalent / implied     -> partial credit     (MySQL ~ PostgreSQL 0.7, Django -> Python 0.8)
  3. semantic (embeddings)    -> scaled credit, only when a real embedding model is loaded
"""
from __future__ import annotations
import re
from functools import lru_cache

# Display|category|aliases
_RAW = """
Python|language|python3,py
JavaScript|language|js,ecmascript,es6
TypeScript|language|ts
Java|language|core java,j2ee,java 8,java 11,java 17
C++|language|cpp
C#|language|csharp,c sharp
Go|language|golang
Rust|language|
Ruby|language|
PHP|language|
Kotlin|language|
Swift|language|
Scala|language|
R|language|r programming,rstudio
SQL|data|t-sql,pl/sql,plsql
React|frontend|react.js,reactjs
Next.js|frontend|nextjs
Vue|frontend|vue.js,vuejs
Angular|frontend|angularjs,angular.js
Svelte|frontend|
HTML|frontend|html5
CSS|frontend|css3,sass,scss
Tailwind CSS|frontend|tailwind,tailwindcss
Redux|frontend|
Node.js|backend|nodejs
Express|backend|express.js,expressjs
Django|backend|
Flask|backend|
FastAPI|backend|fast api
Spring Boot|backend|springboot
Spring|backend|spring framework
.NET|backend|dotnet,asp.net,.net core,asp.net core
Laravel|backend|
Ruby on Rails|backend|rails
GraphQL|backend|
REST APIs|backend|rest api,restful,restful apis
Microservices|backend|microservice
PostgreSQL|database|postgres,psql
MySQL|database|
SQL Server|database|mssql,microsoft sql server
Oracle|database|oracle db,oracle database
SQLite|database|
MariaDB|database|
MongoDB|database|mongo
Redis|database|
Cassandra|database|
DynamoDB|database|
Elasticsearch|database|elastic search,opensearch
Snowflake|data|
BigQuery|data|
Redshift|data|
Apache Spark|data|spark,pyspark
Kafka|data|apache kafka
Airflow|data|apache airflow
dbt|data|
Hadoop|data|
ETL|data|elt,data pipelines,data pipeline
Pandas|data|
NumPy|data|
Power BI|data|powerbi
Tableau|data|
Excel|data|ms excel,microsoft excel
Machine Learning|ml|ml
Deep Learning|ml|
NLP|ml|natural language processing
Computer Vision|ml|
TensorFlow|ml|
PyTorch|ml|
scikit-learn|ml|sklearn,scikit learn
LLMs|ml|large language models,llm,generative ai,genai
Hugging Face|ml|huggingface
spaCy|ml|
Statistics|ml|statistical analysis
AWS|cloud|amazon web services,ec2,s3,aws lambda
Azure|cloud|microsoft azure
GCP|cloud|google cloud,google cloud platform
Docker|devops|containerization,containers
Kubernetes|devops|k8s
Terraform|devops|
Ansible|devops|
Jenkins|devops|
GitHub Actions|devops|
GitLab CI|devops|gitlab ci/cd
CI/CD|devops|ci cd,continuous integration,continuous delivery,continuous deployment
Linux|devops|unix
Git|tools|github,gitlab,bitbucket
Prometheus|devops|
Grafana|devops|
Agile|process|scrum,kanban
JIRA|tools|
Unit Testing|qa|pytest,junit,jest,unit tests
Selenium|qa|
Cypress|qa|
Test Automation|qa|automation testing
Cybersecurity|security|information security,infosec
OAuth|security|oauth2,oauth 2.0
Android|mobile|
iOS|mobile|
React Native|mobile|
Flutter|mobile|
Figma|design|
UX Design|design|ui/ux,user experience
Project Management|management|
Product Management|management|
Leadership|management|team lead,team leadership,led a team,mentoring
Salesforce|business|
SAP|business|
Recruiting|business|talent acquisition
"""

# Canonical names whose own spelling is too ambiguous to match as a bare word.
NO_SELF_ALIAS = {"go", "r", "express", "spring", "rest apis", "swift"}

# Groups of broadly interchangeable skills -> credit when candidate has a *different* member.
EQUIVALENT_GROUPS = [
    (["PostgreSQL", "MySQL", "SQL Server", "Oracle", "SQLite", "MariaDB", "SQL"], 0.70),
    (["MongoDB", "DynamoDB", "Cassandra"], 0.60),
    (["AWS", "Azure", "GCP"], 0.65),
    (["React", "Vue", "Angular", "Svelte", "Next.js"], 0.60),
    (["Django", "Flask", "FastAPI"], 0.70),
    (["TensorFlow", "PyTorch"], 0.80),
    (["Jenkins", "GitHub Actions", "GitLab CI"], 0.75),
    (["Terraform", "Ansible"], 0.50),
    (["Power BI", "Tableau"], 0.75),
    (["Snowflake", "BigQuery", "Redshift"], 0.70),
    (["React Native", "Flutter"], 0.60),
    (["Spring Boot", "Spring"], 0.85),
    (["Java", "C#", "Kotlin"], 0.50),
    (["Selenium", "Cypress", "Test Automation"], 0.70),
]

# Having A implies (partial) knowledge of B.
IMPLIES = {
    "React": {"JavaScript": 0.8}, "Next.js": {"React": 0.9, "JavaScript": 0.8},
    "Vue": {"JavaScript": 0.8}, "Angular": {"TypeScript": 0.8, "JavaScript": 0.8},
    "TypeScript": {"JavaScript": 0.9}, "Node.js": {"JavaScript": 0.8}, "Express": {"Node.js": 0.8},
    "Django": {"Python": 0.8, "REST APIs": 0.4}, "Flask": {"Python": 0.8}, "FastAPI": {"Python": 0.8, "REST APIs": 0.6},
    "Pandas": {"Python": 0.7}, "NumPy": {"Python": 0.7},
    "scikit-learn": {"Machine Learning": 0.85, "Python": 0.6},
    "TensorFlow": {"Machine Learning": 0.85, "Deep Learning": 0.9},
    "PyTorch": {"Machine Learning": 0.85, "Deep Learning": 0.9},
    "Deep Learning": {"Machine Learning": 0.9}, "NLP": {"Machine Learning": 0.7},
    "spaCy": {"NLP": 0.85}, "Hugging Face": {"NLP": 0.8, "Deep Learning": 0.6}, "LLMs": {"NLP": 0.7},
    "Spring Boot": {"Java": 0.8}, "Spring": {"Java": 0.8},
    "Kubernetes": {"Docker": 0.6},
    "GitHub Actions": {"CI/CD": 0.9}, "Jenkins": {"CI/CD": 0.9}, "GitLab CI": {"CI/CD": 0.9},
    "Airflow": {"ETL": 0.8}, "dbt": {"ETL": 0.7},
    "Kotlin": {"Android": 0.6}, "Swift": {"iOS": 0.6}, "Tailwind CSS": {"CSS": 0.8},
    "PostgreSQL": {"SQL": 0.9}, "MySQL": {"SQL": 0.9}, "SQL Server": {"SQL": 0.9},
    "Oracle": {"SQL": 0.9}, "SQLite": {"SQL": 0.9}, "MariaDB": {"SQL": 0.9},
}

CERT_PATTERNS = [
    r"aws certified [a-z\- ]+", r"aws (?:solutions architect|developer|sysops|devops)[a-z\- ]*(?:associate|professional)",
    r"azure (?:fundamentals|administrator|developer|data engineer)[a-z\- ]*", r"\baz-\d{3}\b", r"\bdp-\d{3}\b",
    r"google (?:cloud )?(?:professional|associate)[a-z\- ]+", r"\bpmp\b", r"\bcka\b", r"\bckad\b", r"\bcissp\b",
    r"comptia [a-z\+\- ]+", r"certified scrum ?master", r"\bcsm\b", r"professional scrum master", r"\bccna\b", r"\bitil\b",
    r"six sigma[a-z\- ]*", r"tensorflow developer certificate", r"oracle certified [a-z\- ]+", r"hashicorp certified[a-z\- ]*",
]


def _slug(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


@lru_cache(maxsize=1)
def taxonomy() -> dict:
    skills: dict[str, dict] = {}
    alias_to_canon: dict[str, str] = {}
    for line in _RAW.strip().splitlines():
        display, cat, aliases = (line.split("|") + ["", ""])[:3]
        key = _slug(display)
        names = [a for a in (x.strip().lower() for x in aliases.split(",")) if a]
        if key not in NO_SELF_ALIAS:
            names.append(key)
        skills[key] = {"name": display, "category": cat, "aliases": sorted(set(names))}
        for n in names:
            alias_to_canon.setdefault(n, key)
    # one big alternation, longest alias first so "spring boot" beats "spring"
    alts = sorted(alias_to_canon, key=len, reverse=True)
    pattern = re.compile(
        r"(?<![A-Za-z0-9+#.])(" + "|".join(re.escape(a) for a in alts) + r")(?![A-Za-z0-9+#]|\.[A-Za-z0-9])", re.I)
    equiv: dict[str, dict[str, float]] = {}
    for members, w in EQUIVALENT_GROUPS:
        keys = [_slug(m) for m in members]
        for a in keys:
            for b in keys:
                if a != b:
                    equiv.setdefault(a, {})[b] = max(w, equiv.get(a, {}).get(b, 0))
    implies = {_slug(a): {_slug(b): w for b, w in d.items()} for a, d in IMPLIES.items()}
    return {"skills": skills, "alias": alias_to_canon, "pattern": pattern, "equiv": equiv, "implies": implies}


def canonical(name: str) -> str | None:
    """Map free text ('Postgres', 'reactjs') to a canonical key, or None if unknown."""
    return taxonomy()["alias"].get(_slug(name))


def display(key: str) -> str:
    t = taxonomy()["skills"]
    return t[key]["name"] if key in t else key


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip(" \t•-–*·▪") for p in parts if p.strip()]


def find_skills(text: str) -> dict[str, list[str]]:
    """Return {canonical_key: [evidence sentences]} found in text."""
    t = taxonomy()
    found: dict[str, list[str]] = {}
    for sent in split_sentences(text):
        for m in t["pattern"].finditer(sent):
            key = t["alias"][m.group(1).lower()]
            ev = found.setdefault(key, [])
            if len(ev) < 3 and sent[:240] not in ev:
                ev.append(sent[:240])
    return found


def find_certifications(text: str) -> list[str]:
    out, seen = [], set()
    for pat in CERT_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            c = re.sub(r"\s+", " ", m.group(0)).strip(" -")
            if c.lower() not in seen and len(c) > 2:
                seen.add(c.lower()); out.append(c)
    return out


def suggest(prefix: str, limit: int = 8) -> list[str]:
    p = _slug(prefix)
    names = [v["name"] for v in taxonomy()["skills"].values()]
    return [n for n in names if p in n.lower()][:limit]
