"""Embedding backend. Uses sentence-transformers when installed (semantic), otherwise a deterministic
hashed bag-of-words fallback (lexical only; never counted as 'semantic' evidence for skills)."""
from __future__ import annotations
import hashlib, math, os, re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9+#.]{2,}")
_STOP = set("the and for with from that this are was were have has had will you our your their they them into over under "
            "such than then also can able using used use work working team years year experience strong good great".split())


class Embedder:
    def __init__(self, model_name: str | None = None):
        self.model = None
        self.name = "lexical-hash-v1"
        self.semantic = False
        wanted = model_name or os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        if os.getenv("DISABLE_ST", "0") != "1":
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(wanted)
                self.name, self.semantic = wanted, True
            except Exception:
                self.model = None

    # ---- vectors
    def _hash_vec(self, text: str, dim: int = 2048) -> dict[int, float]:
        toks = [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]
        grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        c = Counter(int(hashlib.md5(g.encode()).hexdigest()[:8], 16) % dim for g in grams)
        v = {k: 1 + math.log(n) for k, n in c.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {k: x / norm for k, x in v.items()}

    def embed(self, texts: list[str]):
        if self.model is not None:
            return self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [self._hash_vec(t) for t in texts]

    @staticmethod
    def cos(a, b) -> float:
        if isinstance(a, dict):
            return sum(x * b.get(k, 0.0) for k, x in a.items())
        return float((a * b).sum())

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.embed([a, b])
        return self.cos(va, vb)

    def best_sentence(self, query: str, sentences: list[str]) -> tuple[float, str | None]:
        if not sentences:
            return 0.0, None
        vecs = self.embed([query] + sentences)
        q, rest = vecs[0], vecs[1:]
        sims = [self.cos(q, r) for r in rest]
        i = max(range(len(sims)), key=sims.__getitem__)
        return sims[i], sentences[i]

    def calibrate(self, sim: float) -> float:
        """Map raw cosine similarity (JD vs resume) to 0..1."""
        lo, hi = (0.20, 0.70) if self.semantic else (0.05, 0.45)
        return max(0.0, min(1.0, (sim - lo) / (hi - lo)))


_shared: Embedder | None = None
def get_embedder() -> Embedder:
    global _shared
    if _shared is None:
        _shared = Embedder()
    return _shared
