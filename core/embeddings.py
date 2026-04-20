import re
import os
from functools import lru_cache
from sentence_transformers import SentenceTransformer, util
from .skills import SKILL_LIST

# Similarity threshold for skill detection (0..1). Tune based on your data.
SKILL_SIM_THRESHOLD = 0.35
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=4)
def _get_model(model_name):
    return SentenceTransformer(model_name)


@lru_cache(maxsize=4)
def _get_skill_embeddings(model_name):
    model = _get_model(model_name)
    return model.encode(SKILL_LIST, normalize_embeddings=True)


def _resolve_model_name():
    return os.getenv("RESUME_AI_EMBEDDING_MODEL", DEFAULT_MODEL_NAME)


def compute_similarity(job_text, resume_text):
    """
    Compute cosine similarity between job and resume text using BERT embeddings.
    Returns a value in [0, 1].
    """
    if not job_text or not resume_text:
        return 0.0

    model = _get_model(_resolve_model_name())
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
    "emr": "EMR/EHR",
    "ehr": "EMR/EHR",
    "electronic medical record": "EMR/EHR",
    "electronic health record": "EMR/EHR",
    "crm": "CRM",
    "customer relationship management": "CRM",
    "gaap": "GAAP",
    "generally accepted accounting principles": "GAAP",
    "ifrs": "IFRS",
    "hris": "HRIS",
    "human resource information system": "HRIS",
    "plc": "PLC Programming",
    "cnc": "CNC Machining",
    "osha": "OSHA Compliance",
    "leed": "LEED Certification",
    "cad": "CAD",
    "autocad": "AutoCAD",
    "solidworks": "SolidWorks",
    "okr": "OKR",
    "kpi": "KPI Management",
    "erp": "ERP Systems",
    "sap": "SAP",
    "pmp": "PMP Certification",
    "hvac": "HVAC",
    "gmp": "GMP Compliance",
    "cpr": "CPR Certification",
    "bls": "BLS Certification",
    "acls": "ACLS Certification",
    "roi": "Financial Analysis",
    "seo": "SEO",
    "ppc": "PPC Advertising",
    "जावा": "Java",
    "पायथन": "Python",
    "मशीन लर्निंग": "Machine Learning",
    "मशिन लर्निंग": "Machine Learning",
    "कृत्रिम बुद्धिमत्ता": "AI",
    "प्रोग्रामिंग": "Programming",
    "डेटा साइंस": "Data Science",
    "数据科学": "Data Science",
    "机器学习": "Machine Learning",
    "深度学习": "Deep Learning",
    "人工智能": "AI",
    "编程": "Programming",
    "программирование": "Programming",
    "машинное обучение": "Machine Learning",
    "глубокое обучение": "Deep Learning",
    "искусственный интеллект": "AI",
    "алгоритмы": "Algorithms",
    "datenanalyse": "Data Analysis",
    "maschinenlernen": "Machine Learning",
    "künstliche intelligenz": "AI",
    "programmierung": "Programming",
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
        model_name = _resolve_model_name()
        keyword_matches = _keyword_match_skills(text)
        if keyword_matches:
            return sorted(set(keyword_matches))

        model = _get_model(model_name)
        skill_embeddings = _get_skill_embeddings(model_name)
        text_embedding = model.encode(text, normalize_embeddings=True)

        scores = util.cos_sim(skill_embeddings, text_embedding).tolist()
        matched = [
            skill for skill, score in zip(SKILL_LIST, scores) if score[0] >= SKILL_SIM_THRESHOLD
        ]
        return matched
    except Exception as e:
        print("⚠️ Embedding skill extraction failed:", e)
        return []
