"""Engine tests (stdlib unittest; also collected by pytest). No web framework or DB needed."""
import os, sys, unittest, tempfile, pathlib
from datetime import date
os.environ.setdefault("DISABLE_ST", "1")  # deterministic lexical fallback in CI
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from app.engine import extract, parser, scoring, privacy, skills, llm
from app.engine.embeddings import Embedder
import generate_samples as gs

TODAY = date(2026, 10, 30)
JOB = {
    "title": "Senior Backend Engineer",
    "description": "Design and build scalable Python APIs on AWS using FastAPI and PostgreSQL. Containerise services with Docker and run them on Kubernetes with CI/CD.",
    "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Kubernetes"],
    "preferred_skills": ["Redis", "CI/CD", "Terraform"],
    "min_years": 4, "min_education": "bachelor", "certifications": ["AWS Certified Solutions Architect"],
}
EMB = Embedder()


def run(text, job=JOB):
    p = parser.parse_resume(text, TODAY)
    return p, scoring.score_candidate(p, job, EMB, TODAY)


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp()); gs.main(self.d)

    def test_pdf_and_docx_roundtrip(self):
        pdf_text = extract.extract_text((self.d / "priya_raman.pdf").read_bytes())
        self.assertIn("FastAPI", pdf_text)
        docx_text = extract.extract_text((self.d / "arjun_mehta.docx").read_bytes())
        self.assertIn("Django", docx_text)

    def test_rejects_disguised_and_empty_files(self):
        with self.assertRaises(extract.ExtractionError):
            extract.extract_text(b"MZ\x90\x00 fake executable renamed to resume.pdf")
        with self.assertRaises(extract.ExtractionError):
            extract.extract_text(b"%PDF-1.4 garbage")


class ParserTests(unittest.TestCase):
    def test_fields(self):
        p = parser.parse_resume(gs.RESUMES["priya_raman"], TODAY)
        self.assertEqual(p["name"], "Priya Raman")
        self.assertEqual(p["email"], "priya.raman@example.com")
        self.assertEqual(p["highest_education"], "bachelor")
        self.assertEqual(len(p["experience"]), 2)
        self.assertGreater(p["total_years"], 10)
        self.assertTrue(any(c.startswith("AWS Certified Solutions Architect") for c in p["certifications"]))
        self.assertTrue(any("35%" in a for a in p["achievements"]))
        self.assertTrue(p["skills"]["kubernetes"]["demonstrated"])

    def test_overlapping_jobs_not_double_counted(self):
        txt = "A B\nEXPERIENCE\nDev at X\nJan 2020 - Dec 2021\n- did things with python\nDev at Y\nJun 2021 - Dec 2022\n- more python\n"
        p = parser.parse_resume(txt, TODAY)
        self.assertEqual(round(p["total_years"]), 3)   # Jan2020-Dec2022 = 36 months, not 48

    def test_missing_fields_are_none_not_invented(self):
        p = parser.parse_resume("Skills\nPython and Docker are great tools I like a lot, many words here to pass length.", TODAY)
        self.assertIsNone(p["name"]); self.assertIsNone(p["email"]); self.assertEqual(p["experience"], [])


class ScoringTests(unittest.TestCase):
    def test_ranking_order(self):
        s = {k: run(v)[1]["score"] for k, v in gs.RESUMES.items()}
        self.assertGreater(s["priya_raman"], s["arjun_mehta"])
        self.assertGreater(s["arjun_mehta"], s["meera_iyer"])
        self.assertGreater(s["priya_raman"], 80)
        self.assertLess(s["meera_iyer"], 40)

    def test_equivalent_skills_get_partial_credit_with_evidence(self):
        _, r = run(gs.RESUMES["arjun_mehta"])
        m = {x["requirement"]: x for x in r["required_matches"]}
        self.assertEqual(m["PostgreSQL"]["kind"], "equivalent"); self.assertEqual(m["PostgreSQL"]["via"], "MySQL")
        self.assertAlmostEqual(m["PostgreSQL"]["credit"], 0.7, places=2)
        self.assertEqual(m["AWS"]["via"], "Azure")
        self.assertEqual(m["FastAPI"]["via"], "Django")          # same-family framework
        self.assertEqual(m["Kubernetes"]["kind"], "missing")
        self.assertIn("Kubernetes", r["missing_required"])
        self.assertTrue(m["PostgreSQL"]["evidence"])

    def test_alias_matching(self):
        txt = "Jo Smith\nEXPERIENCE\nEngineer at Z\nJan 2020 - Present\n- Ran Postgres and k8s clusters with docker compose on amazon web services\n"
        _, r = run(txt)
        kinds = {m["requirement"]: m["kind"] for m in r["required_matches"]}
        self.assertEqual((kinds["PostgreSQL"], kinds["Kubernetes"], kinds["AWS"]), ("exact", "exact", "exact"))

    def test_no_fabricated_evidence(self):
        for text in gs.RESUMES.values():
            _, r = run(text)
            norm = lambda s: " ".join(s.split()).lower().lstrip("-• ")
            src = norm(text.replace("\n- ", "\n"))
            for m in r["required_matches"] + r["preferred_matches"] + r["certification_matches"]:
                if m["kind"] == "missing":
                    self.assertIsNone(m["evidence"])
                elif m["evidence"]:
                    self.assertIn(norm(m["evidence"]), src)
            for item in r["strengths"]:
                if item["evidence"]:
                    self.assertIn(norm(item["evidence"]), src)

    def test_protected_attributes_do_not_change_score(self):
        base = gs.RESUMES["priya_raman"]
        variants = [
            base.replace("Priya Raman", "James Walker").replace("Female", "Male").replace("14 March 1994", "02 May 1968"),
            base.replace("Gender: Female | Date of Birth: 14 March 1994", "Age: 58\nMarital Status: Married\nNationality: Other\nAddress: 12 Some Street"),
            base.replace("2016\nSKILLS", "1989\nSKILLS"),  # graduation year (age proxy)
        ]
        ref = run(base)[1]
        for v in variants:
            res = run(v)[1]
            self.assertEqual(res["score"], ref["score"])
            self.assertEqual({k: c["points"] for k, c in res["components"].items()}, {k: c["points"] for k, c in ref["components"].items()})

    def test_configurable_weights(self):
        text = gs.RESUMES["arjun_mehta"]
        p = parser.parse_resume(text, TODAY)
        a = scoring.score_candidate(p, {**JOB, "weights": {"required_skills": 90, "preferred_skills": 0, "experience": 0, "education": 0, "certifications": 0, "semantic": 10}}, EMB, TODAY)
        b = scoring.score_candidate(p, {**JOB, "weights": {"required_skills": 5, "experience": 80, "education": 5, "certifications": 5, "preferred_skills": 0, "semantic": 5}}, EMB, TODAY)
        self.assertNotEqual(a["score"], b["score"])
        self.assertAlmostEqual(sum(scoring.normalize_weights({"required_skills": 3, "experience": 1}).values()), 100.0, places=5)
        self.assertLessEqual(a["score"], 100)

    def test_listed_only_skill_gets_slightly_less_credit(self):
        txt = "Sam Lee\nEXPERIENCE\nDev at Q\nJan 2020 - Present\n- Wrote code\nSKILLS\nPython, Docker\n"
        _, r = run(txt, {**JOB, "required_skills": ["Python"], "preferred_skills": []})
        self.assertAlmostEqual(r["required_matches"][0]["credit"], 0.9)
        self.assertTrue(any("skills list" in w["text"] for w in r["weaknesses"]))

    def test_empty_requirements_do_not_crash_and_stay_in_range(self):
        _, r = run(gs.RESUMES["meera_iyer"], {"title": "x", "description": "", "required_skills": []})
        self.assertTrue(0 <= r["score"] <= 100)

    def test_unscannable_resume_flagged_for_manual_review(self):
        p = parser.parse_resume("Short resume text that has no structure at all but is long enough to pass the extraction check.", TODAY)
        self.assertTrue(scoring.score_candidate(p, JOB, EMB, TODAY)["needs_manual_review"])


class PrivacyAndLLMTests(unittest.TestCase):
    def test_redact(self):
        out = privacy.redact("Priya Raman\npriya@x.com +91 98765 43210 linkedin.com/in/p\nGender: Female\nBuilt APIs in Python", "Priya Raman")
        for bad in ("priya", "@", "98765", "Female", "linkedin", "Raman"):
            self.assertNotIn(bad.lower(), out.lower())
        self.assertIn("Built APIs in Python", out)

    def test_scoring_view_excludes_identity(self):
        p = parser.parse_resume(gs.RESUMES["priya_raman"], TODAY)
        v = privacy.scoring_view(p)
        self.assertNotIn("name", v); self.assertNotIn("email", v); self.assertNotIn("phone", v)
        self.assertTrue(all("year" not in e for e in v["education"]))
        self.assertNotIn("priya", p["scoring_text"].lower())

    def test_llm_output_must_be_grounded(self):
        src = "Built FastAPI microservices on AWS serving 2M requests per day"
        self.assertTrue(llm.validate_grounded({"summary": "ok", "quotes": ["FastAPI microservices on AWS"]}, src))
        self.assertFalse(llm.validate_grounded({"summary": "ok", "quotes": ["Led a team of 50 engineers at Google"]}, src))
        self.assertFalse(llm.validate_grounded({"summary": "ok", "quotes": []}, src))
        self.assertIsNone(llm.summarise(src, {}))   # provider none -> disabled


class TaxonomyTests(unittest.TestCase):
    def test_ambiguous_words_not_matched(self):
        self.assertEqual(skills.find_skills("We go to market and I am the express lane, rest assured"), {})
        self.assertIn("go", skills.find_skills("Services written in Golang"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
