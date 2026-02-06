# TEMPORARY DUMMY FUNCTION — replace later with OpenAI embeddings

def compute_similarity(job_text, resume_text):
    """
    For now, we return a simple score based on word overlap.
    Later you will replace this with OpenAI embeddings.
    """
    job_words = set(job_text.lower().split())
    resume_words = set(resume_text.lower().split())

    common = job_words.intersection(resume_words)

    if len(job_words) == 0:
        return 0

    score = (len(common) / len(job_words)) * 100
    return round(score, 2)

from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def extract_skills(text):
    try:
        prompt = f"""
        Extract only technical skills from the following text.
        Return them as a comma-separated list only.

        Text:
        {text}
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        skills = response.choices[0].message.content
        return [s.strip() for s in skills.split(",") if s.strip()]

    except Exception as e:
        print("⚠️ OpenAI failed:", e)
        return []   # <-- IMPORTANT: fallback instead of crashing


