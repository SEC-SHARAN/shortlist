"""Optional LLM layer. OFF by default (LLM_PROVIDER=none).

Safety design (anti-fabrication):
  * The model only receives *redacted* text + the deterministic evidence (never name/contact/etc.).
  * It must return JSON {"summary": str, "quotes": [str,...]}; every quote must appear verbatim in the redacted
    resume text, otherwise the whole LLM output is discarded and the deterministic explanation is used.
  * The LLM can never change the numeric score or a candidate's stage.
"""
from __future__ import annotations
import json, os, re


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def validate_grounded(output: dict, source_text: str) -> bool:
    src = _norm(source_text)
    quotes = output.get("quotes")
    if not isinstance(output.get("summary"), str) or not isinstance(quotes, list) or not quotes:
        return False
    return all(isinstance(q, str) and len(q) > 8 and _norm(q) in src for q in quotes)


def summarise(redacted_text: str, evidence: dict) -> dict | None:
    provider = os.getenv("LLM_PROVIDER", "none").lower()
    if provider == "none":
        return None
    try:
        import httpx
        prompt = (
            "You are assisting a recruiter. Using ONLY the resume text below, write a neutral 3-sentence summary of the "
            "candidate's fit for the job. Do not infer or mention age, gender, ethnicity, nationality, health, family status or "
            "any protected characteristic. Do not invent facts. Return JSON only: {\"summary\": str, \"quotes\": [verbatim "
            "snippets from the resume that support the summary]}.\n\nEVIDENCE:\n" + json.dumps(evidence)[:3000] +
            "\n\nRESUME:\n" + redacted_text[:6000])
        if provider == "anthropic":
            r = httpx.post("https://api.anthropic.com/v1/messages", timeout=40,
                           headers={"x-api-key": os.environ["LLM_API_KEY"], "anthropic-version": "2023-06-01"},
                           json={"model": os.getenv("LLM_MODEL", "claude-sonnet-4-6"), "max_tokens": 500,
                                 "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            raw = "".join(b.get("text", "") for b in r.json()["content"])
        else:  # any OpenAI-compatible endpoint (OpenAI, vLLM, Ollama, ...)
            r = httpx.post(os.getenv("LLM_BASE_URL", "https://api.openai.com/v1") + "/chat/completions", timeout=40,
                           headers={"Authorization": f"Bearer {os.getenv('LLM_API_KEY', '')}"},
                           json={"model": os.getenv("LLM_MODEL", "gpt-4o-mini"), "temperature": 0,
                                 "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"]
        out = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip())
        return out if validate_grounded(out, redacted_text) else None
    except Exception:
        return None
