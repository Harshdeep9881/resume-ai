import re
from functools import lru_cache
from sentence_transformers import SentenceTransformer, util
from .skills import SKILL_LIST

# Similarity threshold for skill detection (0..1). Tune based on your data.
SKILL_SIM_THRESHOLD = 0.35


@lru_cache(maxsize=1)
def _get_model():
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def _get_skill_embeddings():
    model = _get_model()
    return model.encode(SKILL_LIST, normalize_embeddings=True)


def compute_similarity(job_text, resume_text):
    """
    Compute cosine similarity between job and resume text using BERT embeddings.
    Returns a value in [0, 1].
    """
    if not job_text or not resume_text:
        return 0.0

    model = _get_model()
    embeddings = model.encode([job_text, resume_text], normalize_embeddings=True)
    score = util.cos_sim(embeddings[0], embeddings[1]).item()
    return round(float(score), 4)


_ALIAS_MAP = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python": "Python",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "AI",
    "artificial intelligence": "AI",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "cv": "Computer Vision",
    "sql": "SQL",
    "aws": "AWS",
    "gcp": "GCP",
    "node": "Node.js",
    "nodejs": "Node.js",
    "reactjs": "React",
    "html": "HTML",
    "css": "CSS",
}


def _keyword_match_skills(text):
    if not text:
        return []

    text_lower = text.lower()
    matched = set()

    # Alias matching first for common abbreviations.
    for alias, canonical in _ALIAS_MAP.items():
        if re.search(rf"\b{re.escape(alias)}\b", text_lower):
            matched.add(canonical)

    # Direct skill matching.
    for skill in SKILL_LIST:
        if skill in matched:
            continue
        skill_lower = skill.lower()
        if re.search(rf"\b{re.escape(skill_lower)}\b", text_lower):
            matched.add(skill)
        elif any(ch in skill for ch in [".", "+", "#", "/"]):
            if re.search(re.escape(skill_lower), text_lower):
                matched.add(skill)

    return list(matched)


def extract_skills(text):
    """
    Detect skills by matching text embedding to predefined skill embeddings.
    """
    if not text or not text.strip():
        return []

    try:
        keyword_matches = _keyword_match_skills(text)
        if keyword_matches:
            return sorted(set(keyword_matches))

        model = _get_model()
        skill_embeddings = _get_skill_embeddings()
        text_embedding = model.encode(text, normalize_embeddings=True)

        scores = util.cos_sim(skill_embeddings, text_embedding).tolist()
        matched = [
            skill for skill, score in zip(SKILL_LIST, scores) if score[0] >= SKILL_SIM_THRESHOLD
        ]
        return matched
    except Exception as e:
        print("⚠️ Embedding skill extraction failed:", e)
        return []
