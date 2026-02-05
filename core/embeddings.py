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
