"""
AI assistant for job description generation, skill suggestion,
and screening question recommendation.

Primary backend: Ollama (local, free, no quota)
Fallback backend: Google Gemini (requires GEMINI_API_KEY)

To use Ollama:
  1. Install: curl -fsSL https://ollama.com/install.sh | sh
  2. Pull a model: ollama pull llama3.2   (or gemma3:4b, mistral, etc.)
  3. Start service: ollama serve
  4. Set OLLAMA_MODEL=llama3.2 in .env (optional, defaults to llama3.2)
"""

import json
import os
import re
import urllib.request
import urllib.error

# ── Ollama config ──────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"


def _get_ollama_model():
    return os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()


def _ollama_available():
    """Check if the Ollama server is running."""
    try:
        req = urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return req.status == 200
    except Exception:
        return False


def _call_ollama(prompt):
    """Call Ollama's HTTP API. Returns response text or raises on failure."""
    model = _get_ollama_model()
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("response", "")


# ── Gemini fallback ────────────────────────────────────────────────────────
_GEMINI_MODELS = [
    "gemini-2.5-flash-preview-04-17",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
]


def _get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except ImportError:
        return None


def _call_gemini(prompt):
    """Try each Gemini model until one succeeds."""
    import time
    try:
        from google.genai import errors as genai_errors
    except ImportError:
        return None

    client = _get_gemini_client()
    if not client:
        return None

    last_error = None
    for model in _GEMINI_MODELS:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                return response.text
            except genai_errors.ClientError as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    last_error = e
                    if attempt == 0:
                        match = re.search(r"retry in ([\d.]+)s", error_str)
                        delay = min(float(match.group(1)) + 2, 45) if match else 30
                        print(f"⚠️ Gemini {model} rate-limited, waiting {delay:.0f}s...")
                        time.sleep(delay)
                        continue
                    break
                print(f"⚠️ Gemini {model} error: {e}")
                return None
            except Exception as e:
                print(f"⚠️ Gemini {model} error: {e}")
                return None
    print(f"⚠️ All Gemini models exhausted: {last_error}")
    return None


# ── Unified call ───────────────────────────────────────────────────────────

def _call_ai(prompt):
    """Try Ollama first, fall back to Gemini."""
    # Try Ollama
    if _ollama_available():
        try:
            text = _call_ollama(prompt)
            if text:
                print(f"✅ AI response via Ollama ({_get_ollama_model()})")
                return text
        except Exception as e:
            print(f"⚠️ Ollama call failed: {e}, falling back to Gemini...")

    # Fallback to Gemini
    text = _call_gemini(prompt)
    if text:
        print("✅ AI response via Gemini")
        return text

    return None


# ── JSON extraction ────────────────────────────────────────────────────────

def _extract_json(text):
    """Extract the first JSON array or object from text."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = cleaned.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == start_char:
                depth += 1
            elif cleaned[i] == end_char:
                depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start: i + 1])
                except json.JSONDecodeError:
                    break
    return None


# ── Public API ─────────────────────────────────────────────────────────────

def generate_job_description(title, industry_hint=""):
    """
    Generate a professional job description from a job title.
    Returns dict: {"description": "...", "industry": "..."} or None.
    """
    industry_context = f" in the {industry_hint} industry" if industry_hint else ""
    prompt = f"""You are an expert HR consultant. Generate a professional job description for the role: "{title}"{industry_context}.

Include these sections:
- About the Role (2-3 sentences)
- Key Responsibilities (5-7 bullet points)
- Must-Have Requirements (4-6 bullet points)
- Nice-to-Have (3-4 bullet points)

Use clear, inclusive language. Avoid gendered terms.
Format with bullet points using "- ".
Do NOT include salary or company name.

Also detect the most likely industry for this role.

Return ONLY valid JSON in this exact format:
{{"description": "the full job description text here", "industry": "detected industry name"}}"""

    try:
        text = _call_ai(prompt)
        if not text:
            return None
        result = _extract_json(text)
        if result and isinstance(result, dict) and "description" in result:
            return result
        return {"description": text.strip(), "industry": industry_hint or "General"}
    except Exception as e:
        print(f"⚠️ generate_job_description failed: {e}")
        return None


def suggest_skills(title, description=""):
    """
    Suggest relevant skills for a job.
    Returns list of skill strings, or [] on failure.
    """
    desc_context = f"\n\nJob Description:\n{description[:1000]}" if description else ""
    prompt = f"""You are an expert HR consultant.

For the job role: "{title}"{desc_context}

Suggest 15-20 specific, relevant skills that a strong candidate should have.
Include technical skills, tools, soft skills, and industry-specific knowledge.

Return ONLY a valid JSON array of skill strings, no explanations, no markdown.
Example format: ["Skill One", "Skill Two", "Skill Three"]"""

    try:
        text = _call_ai(prompt)
        if not text:
            return []
        result = _extract_json(text)
        if isinstance(result, list):
            return [str(s).strip() for s in result if s]
        return []
    except Exception as e:
        print(f"⚠️ suggest_skills failed: {e}")
        return []


def suggest_screening_questions(title, description=""):
    """
    Suggest screening questions for a job.
    Returns list of question dicts, or [] on failure.
    """
    desc_context = f"\n\nJob Description:\n{description[:1000]}" if description else ""
    prompt = f"""You are an expert HR consultant designing candidate screening questions.

For the job role: "{title}"{desc_context}

Suggest 5 screening questions. For each provide:
- "prompt": the question text
- "question_type": one of "short_text", "long_text", "number", "url", "knockout_bool"
- "bucket": one of "skills_evidence", "problem_solving", "role_fit", "work_style"
- "is_required": true or false
- "is_knockout": true or false (max 1 knockout)
- "knockout_value": if is_knockout is true, expected answer like "yes"

Return ONLY a valid JSON array of objects, no markdown, no explanations."""

    try:
        text = _call_ai(prompt)
        if not text:
            return []
        result = _extract_json(text)
        if isinstance(result, list):
            valid = []
            for item in result:
                if isinstance(item, dict) and "prompt" in item:
                    valid.append({
                        "prompt": str(item.get("prompt", "")),
                        "question_type": str(item.get("question_type", "short_text")),
                        "bucket": str(item.get("bucket", "")),
                        "is_required": bool(item.get("is_required", True)),
                        "is_knockout": bool(item.get("is_knockout", False)),
                        "knockout_value": str(item.get("knockout_value", "")),
                    })
            return valid
        return []
    except Exception as e:
        print(f"⚠️ suggest_screening_questions failed: {e}")
        return []


def chat_with_assistant(message, history=None, context=None):
    """
    General recruiting assistant chat.
    Returns response text or None on failure.
    """
    history = history or []
    context = context or {}

    safe_history = []
    for item in history[-8:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            safe_history.append({"role": role, "content": content[:1200]})

    title = str(context.get("title", "")).strip()
    description = str(context.get("description", "")).strip()
    skills = context.get("skills") or []
    questions = context.get("questions") or []

    context_lines = []
    if title:
        context_lines.append(f"Job title: {title}")
    if description:
        context_lines.append(f"Job description: {description[:1800]}")
    if skills:
        context_lines.append("Selected skills: " + ", ".join(str(skill) for skill in skills[:30]))
    if questions:
        question_prompts = []
        for question in questions[:8]:
            if isinstance(question, dict):
                prompt = str(question.get("prompt", "")).strip()
                if prompt:
                    question_prompts.append(prompt)
        if question_prompts:
            context_lines.append("Current screening questions: " + " | ".join(question_prompts))

    conversation = "\n".join(
        f"{item['role'].title()}: {item['content']}" for item in safe_history
    )
    job_context = "\n".join(context_lines) or "No job context has been entered yet."

    prompt = f"""You are a practical recruiting assistant inside a resume screening app.

Help the user create job descriptions, choose skills, improve screening questions, understand candidate evaluation, and troubleshoot the hiring workflow.
Use the current job context when it is relevant.
Be concise, concrete, and action-oriented.
Do not claim you changed the app unless the user asks for content they can paste or add.
If the user asks for legal, medical, or employment compliance advice, give general guidance and recommend checking local policy or counsel.

Current job context:
{job_context}

Recent conversation:
{conversation or "No previous messages."}

User: {str(message).strip()[:2000]}
Assistant:"""

    try:
        text = _call_ai(prompt)
        if not text:
            return None
        return text.strip()
    except Exception as e:
        print(f"⚠️ chat_with_assistant failed: {e}")
        return None
