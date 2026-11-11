"""Generate sample resumes (PDF + DOCX) for demos and tests:  python scripts/generate_samples.py [outdir]"""
import sys, pathlib
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import docx

RESUMES = {
"priya_raman": """Priya Raman
priya.raman@example.com | +91 98765 43210 | linkedin.com/in/priyaraman
Gender: Female | Date of Birth: 14 March 1994
SUMMARY
Backend engineer who designs high-throughput APIs and cloud infrastructure.
EXPERIENCE
Senior Software Engineer at Acme Cloud
Jan 2019 - Present
- Built FastAPI microservices on AWS serving 2M requests/day, reduced p95 latency by 35%
- Managed PostgreSQL and Redis clusters; wrote Terraform modules for infrastructure
- Containerised services with Docker and deployed to Kubernetes via GitHub Actions CI/CD
Software Engineer at Beta Systems
Jun 2016 - Dec 2018
- Developed Python REST APIs with PostgreSQL and unit tests in pytest
EDUCATION
B.Tech in Computer Science, Anna University, 2016
SKILLS
Python, FastAPI, PostgreSQL, Docker, Kubernetes, AWS, Redis, Terraform, Git
CERTIFICATIONS
AWS Certified Solutions Architect - Associate
PROJECTS
Resume Ranker
- NLP pipeline using spaCy and sentence embeddings
""",
"arjun_mehta": """Arjun Mehta
arjun.mehta@example.com | +91 91234 56780
EXPERIENCE
Backend Developer, Nimbus Tech
Mar 2018 - Present
- Built Django REST APIs backed by MySQL for a logistics platform
- Deployed containers with Docker on Azure and set up Jenkins pipelines
- Improved query performance by 40% through indexing
EDUCATION
B.E. Information Technology, 2017
SKILLS
Python, Django, MySQL, Docker, Azure, Jenkins, Linux
""",
"meera_iyer": """Meera Iyer
meera.iyer@example.com
Marital Status: Married
EXPERIENCE
Frontend Developer at PixelWorks
Aug 2023 - Present
- Built responsive interfaces in React and Tailwind CSS
- Wrote Jest unit tests
EDUCATION
B.Sc Computer Science, 2023
SKILLS
JavaScript, React, HTML, CSS, Git
""",
}

def pdf(path, text):
    c = canvas.Canvas(str(path), pagesize=A4); y = 800
    for line in text.splitlines():
        c.setFont("Helvetica-Bold" if line.isupper() else "Helvetica", 10); c.drawString(40, y, line); y -= 14
        if y < 40: c.showPage(); y = 800
    c.save()

def word(path, text):
    d = docx.Document()
    for line in text.splitlines():
        d.add_paragraph(line)
    d.save(str(path))

def main(out="samples"):
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    for i, (k, t) in enumerate(RESUMES.items()):
        (word if i == 1 else pdf)(out / f"{k}.{'docx' if i == 1 else 'pdf'}", t)
    print("wrote", len(RESUMES), "resumes to", out)

if __name__ == "__main__":
    main(*(sys.argv[1:2]))
