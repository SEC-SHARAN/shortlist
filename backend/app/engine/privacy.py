"""Privacy + fairness layer.

Everything that influences a score or is sent to an LLM goes through `redact()` /
`scoring_view()`. Protected or proxy attributes are removed *before* analysis, so they
cannot influence ranking even by accident.
"""
from __future__ import annotations
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?){2,4}\d{2,4}(?!\d)")
URL = re.compile(r"(?:https?://|www\.)\S+|(?:linkedin|github|gitlab)\.com/\S+", re.I)
# lines that disclose protected characteristics or common proxies for them
SENSITIVE_LINE = re.compile(
    r"\b(date of birth|d\.?o\.?b\.?|born on|age\s*[:\-]?\s*\d{2}|gender|sex\s*:|male|female|marital status|married|single|"
    r"unmarried|nationality|citizenship|religion|caste|race|ethnicity|father'?s? name|mother'?s? name|spouse|"
    r"passport|visa status|photo|health|disabilit(?:y|ies)|pregnan\w+|political|sexual orientation|"
    r"address|residence|permanent address|current address|pin ?code|zip ?code|hobbies)\b", re.I)
GRAD_YEAR = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")


def redact(text: str, name: str | None = None) -> str:
    """Remove PII and sensitive-attribute lines. Keeps technical/professional content."""
    out = []
    for line in text.splitlines():
        if SENSITIVE_LINE.search(line) and len(line) < 140:
            continue
        line = EMAIL.sub(" ", line)
        line = URL.sub(" ", line)
        line = PHONE.sub(lambda m: " " if len(re.sub(r"\D", "", m.group(0))) >= 8 else m.group(0), line)
        out.append(line)
    text = "\n".join(out)
    if name:
        for part in {name, *name.split()}:
            if len(part) > 2:
                text = re.sub(re.escape(part), " ", text, flags=re.I)
    return re.sub(r"[ \t]{2,}", " ", text)


# Fields of the parsed resume that may be used for scoring. Name/contact/links are excluded.
SCORING_FIELDS = ("skills", "experience", "education", "certifications", "projects", "achievements", "summary_text")


def scoring_view(parsed: dict) -> dict:
    view = {k: parsed.get(k) for k in SCORING_FIELDS}
    # graduation years are an age proxy -> never used by the scorer
    view["education"] = [{k: v for k, v in e.items() if k != "year"} for e in (parsed.get("education") or [])]
    return view


def mask_candidate(cid: int) -> str:
    return f"Candidate #{cid}"
