"""Rule-based resume parser. Every extracted value is copied from the document (no generation).
Fields that cannot be found are left None/empty rather than guessed. spaCy NER is used only as an
optional fallback for the candidate name."""
from __future__ import annotations
import re
from datetime import date

from . import skills as sk
from .privacy import EMAIL, URL, PHONE, SENSITIVE_LINE, redact

SECTIONS = {
    "summary": ["summary", "profile", "professional summary", "objective", "career objective", "about me", "about"],
    "experience": ["experience", "work experience", "professional experience", "employment", "employment history",
                   "work history", "internships", "internship experience", "career history"],
    "education": ["education", "academic background", "academics", "qualifications", "education & training",
                  "educational qualifications"],
    "skills": ["skills", "technical skills", "core competencies", "key skills", "technologies", "tech stack",
               "skills & tools", "tools & technologies", "competencies"],
    "projects": ["projects", "personal projects", "academic projects", "key projects", "selected projects"],
    "certifications": ["certifications", "certificates", "licenses", "certifications & training", "courses"],
    "achievements": ["achievements", "awards", "accomplishments", "honors", "awards & achievements", "publications"],
}
_HEAD = {a: sec for sec, al in SECTIONS.items() for a in al}

MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
DATE = rf"(?:(?:{MONTHS})[a-z]*\.?,?\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
RANGE = re.compile(rf"({DATE})\s*(?:-|–|—|to|until)\s*({DATE}|present|current|now|till date|ongoing)", re.I)
BULLET = re.compile(r"^\s*[•\-–*·▪●◦]\s*")

EDU_LEVELS = {"high_school": 1, "diploma": 2, "bachelor": 3, "master": 4, "phd": 5}
_EDU_PATTERNS = [  # (level, case-sensitive abbreviations, case-insensitive words)
    ("phd", r"\b(Ph\.?D|D\.?Phil)\b", r"\b(doctorate|doctoral)\b"),
    ("master", r"\b(M\.?Tech|M\.?Sc|M\.?S|M\.?E|M\.?A|MBA|M\.?Eng|M\.?Com|MCA)\b", r"\b(master'?s?|postgraduate)\b"),
    ("bachelor", r"\b(B\.?Tech|B\.?E|B\.?Sc|B\.?A|B\.?Com|B\.?S|BCA|BBA|B\.?Eng)\b", r"\b(bachelor'?s?|undergraduate|b\.?\s?tech)\b"),
    ("diploma", r"\b(Diploma|Associate)\b", r"\b(diploma|associate degree|polytechnic)\b"),
    ("high_school", r"\b(HSC|SSC|XII|X)\b", r"\b(high school|12th|10th|secondary school|higher secondary)\b"),
]


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    cur = "header"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        key = re.sub(r"[^a-z& ]", "", line.lower()).strip()
        if key in _HEAD and len(line) < 45:
            cur = _HEAD[key]
            sections.setdefault(cur, [])
            continue
        sections.setdefault(cur, []).append(line)
    return sections


def _ym(s: str, today: date, end: bool) -> tuple[int, int]:
    s = s.strip().lower()
    if s in ("present", "current", "now", "till date", "ongoing"):
        return today.year, today.month
    m = re.match(rf"({MONTHS})[a-z]*\.?,?\s+(\d{{4}})", s)
    if m:
        return int(m.group(2)), ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].index(m.group(1)[:3]) + 1
    m = re.match(r"(\d{1,2})/(\d{4})", s)
    if m:
        return int(m.group(2)), min(max(int(m.group(1)), 1), 12)
    return int(s[:4]), (12 if end else 1)


def _months(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, (b[0] - a[0]) * 12 + (b[1] - a[1]) + 1)


def total_months(entries: list[dict]) -> int:
    """Union of date intervals (overlapping jobs are not double-counted)."""
    iv = sorted((e["start_idx"], e["end_idx"]) for e in entries if e.get("start_idx") is not None)
    total, cur_s, cur_e = 0, None, None
    for s, e in iv:
        if cur_e is None or s > cur_e + 1:
            if cur_e is not None:
                total += cur_e - cur_s + 1
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s + 1
    return total


def parse_experience(lines: list[str], today: date) -> list[dict]:
    starts = []
    for i, ln in enumerate(lines):
        if RANGE.search(ln) and not BULLET.match(ln):
            rest = RANGE.sub("", ln).strip(" ,|-–—()")
            starts.append(i - 1 if (len(rest) < 4 and i > 0 and not BULLET.match(lines[i - 1])) else i)
    entries = []
    for n, s in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        block = lines[s:end]
        rm = next((RANGE.search(l) for l in block[:3] if RANGE.search(l)), None)
        a, b = _ym(rm.group(1), today, False), _ym(rm.group(2), today, True)
        head = " ".join(RANGE.sub("", l).strip(" ,|-–—()") for l in block[:2] if not BULLET.match(l)).strip()
        title, company = _split_heading(head)
        desc = [BULLET.sub("", l) for l in block[1:] if l] if len(block) > 1 else []
        entries.append({
            "title": title, "company": company, "heading": head[:200],
            "start": f"{a[0]}-{a[1]:02d}", "end": f"{b[0]}-{b[1]:02d}",
            "start_idx": a[0] * 12 + a[1], "end_idx": b[0] * 12 + b[1],
            "months": _months(a, b), "description": desc[:12],
            "present": rm.group(2).lower() in ("present", "current", "now", "till date", "ongoing"),
        })
    return entries


def _split_heading(head: str) -> tuple[str | None, str | None]:
    for sep in (" at ", " @ ", " | ", " - ", " – ", " — ", ", "):
        if sep in head:
            a, b = head.split(sep, 1)
            return a.strip() or None, b.strip() or None
    return (head or None), None


def parse_education(lines: list[str]) -> list[dict]:
    out = []
    for ln in lines:
        level = None
        for lv, abbr, words in _EDU_PATTERNS:
            if re.search(abbr, ln) or re.search(words, ln, re.I):
                level = lv
                break
        if level:
            years = re.findall(r"\b(?:19|20)\d{2}\b", ln)
            out.append({"degree": ln[:200], "level": level, "year": int(years[-1]) if years else None})
    return out


def parse_entries_by_heading(lines: list[str]) -> list[dict]:
    items, cur = [], None
    for ln in lines:
        if BULLET.match(ln):
            if cur is not None:
                cur["description"].append(BULLET.sub("", ln))
        else:
            cur = {"name": ln[:160], "description": []}
            items.append(cur)
    for it in items:
        it["description"] = it["description"][:8]
    return items[:12]


def extract_name(header: list[str], text: str, nlp=None) -> str | None:
    for ln in header[:5]:
        if "@" in ln or re.search(r"\d", ln) or SENSITIVE_LINE.search(ln) or len(ln) > 45:
            continue
        words = ln.replace(",", " ").split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Za-z.'\-]+", w) for w in words) and ln.lower() not in _HEAD:
            return " ".join(w.capitalize() if w.isupper() else w for w in words)
    if nlp is not None:
        for ent in nlp(text[:600]).ents:
            if ent.label_ == "PERSON" and 2 <= len(ent.text.split()) <= 4:
                return ent.text.strip()
    return None


_NLP = None
def _load_spacy():
    global _NLP
    if _NLP is None:
        try:
            import spacy
            _NLP = spacy.load("en_core_web_sm", disable=["lemmatizer"])
        except Exception:
            _NLP = False
    return _NLP or None


METRIC = re.compile(r"(\d+(?:\.\d+)?\s?%|\$\s?\d|₹\s?\d|\b\d+[kKmM]\+?\b|\b\d{2,}\+?\s+(?:users|customers|clients|requests|engineers|people|members)|reduced|increased|improved|"
                    r"decreased|saved|won|awarded|ranked|top \d+|first place|led|launched)", re.I)


def parse_resume(text: str, today: date | None = None, use_spacy: bool = False) -> dict:
    today = today or date.today()
    sec = split_sections(text)
    exp = parse_experience(sec.get("experience", []), today)
    edu = parse_education(sec.get("education", []) or [l for l in text.splitlines() if len(l) < 160])
    # an education line must not be mistaken for something else when no education section exists
    if not sec.get("education"):
        edu = edu[:3]

    # skills: record WHERE each was seen. 'demonstrated' = used in experience/projects/etc.
    skill_map: dict[str, dict] = {}
    for section, lines in sec.items():
        if section in ("header",) and not lines:
            continue
        for key, ev in sk.find_skills("\n".join(lines)).items():
            d = skill_map.setdefault(key, {"name": sk.display(key), "sections": [], "evidence": []})
            if section not in d["sections"]:
                d["sections"].append(section)
            for e in ev:
                if e not in d["evidence"] and len(d["evidence"]) < 3:
                    d["evidence"].append(e)
    for d in skill_map.values():
        d["demonstrated"] = any(s in ("experience", "projects", "achievements", "summary", "certifications") for s in d["sections"])

    certs = sk.find_certifications("\n".join(sec.get("certifications", [])) + "\n" + text)
    cert_lines = [BULLET.sub("", l) for l in sec.get("certifications", [])][:15]

    achievements = [BULLET.sub("", l) for l in sec.get("achievements", [])][:10]
    for e in exp:
        for d in e["description"]:
            if METRIC.search(d) and d not in achievements and len(achievements) < 15:
                achievements.append(d)

    contact_blob = "\n".join(sec.get("header", [])[:8])
    email = (EMAIL.search(text) or [None])[0] if EMAIL.search(text) else None
    phone = None
    for m in PHONE.finditer(contact_blob):
        if len(re.sub(r"\D", "", m.group(0))) >= 8:
            phone = m.group(0).strip(); break
    links = list(dict.fromkeys(URL.findall(text)))[:5]
    name = extract_name(sec.get("header", []), text, _load_spacy() if use_spacy else None)

    months = total_months(exp)
    summary_text = " ".join(sec.get("summary", []))[:1200]
    body = redact("\n".join(l for s, ls in sec.items() if s != "header" for l in ls), name)
    # dates/years are age proxies and noise for semantic matching -> removed from the scoring text
    body = re.sub(r"\b(?:19|20)\d{2}\b", " ", RANGE.sub(" ", body))

    return {
        "name": name, "email": email, "phone": phone, "links": links,
        "summary_text": summary_text,
        "experience": exp, "total_years": round(months / 12, 1),
        "education": edu, "highest_education": max((e["level"] for e in edu), key=lambda l: EDU_LEVELS[l], default=None),
        "skills": skill_map, "certifications": certs, "certification_lines": cert_lines,
        "projects": parse_entries_by_heading(sec.get("projects", [])),
        "achievements": achievements,
        "sections_found": [k for k, v in sec.items() if v and k != "header"],
        "scoring_text": body[:8000],       # redacted text used for semantic matching / LLM
        "text_length": len(text),
        "warnings": _warnings(text, exp, name, email),
    }


def _warnings(text, exp, name, email) -> list[str]:
    w = []
    if len(text) < 300: w.append("Very little text extracted; review the original file manually.")
    if not exp: w.append("No dated work experience detected; experience score may be understated.")
    if not name: w.append("Candidate name not detected.")
    if not email: w.append("No email address detected.")
    return w
