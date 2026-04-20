import re

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None


SUPPORTED_LANGUAGES = {"English", "Hindi", "Marathi", "German", "Russian", "Chinese", "Mixed"}


_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_HAN_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF]")
_LATIN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")

_HINDI_MARKERS = {
    "है",
    "और",
    "में",
    "की",
    "का",
    "के",
    "वर्ष",
    "अनुभव",
    "कौशल",
    "शिक्षा",
}

_MARATHI_MARKERS = {
    "आहे",
    "आणि",
    "मध्ये",
    "अनुभव",
    "कौशल्ये",
    "शिक्षण",
    "प्रकल्प",
    "वर्षे",
}

_GERMAN_MARKERS = {
    " und ",
    " mit ",
    " erfahrung ",
    " kenntnisse ",
    " ausbildung ",
    " projekt ",
    " fähigkeiten ",
    " straße ",
    " über ",
}


def _safe_text(text):
    return (text or "").strip()


def _script_ratios(text):
    letters = [ch for ch in text if ch.isalpha()]
    total = len(letters)
    if total == 0:
        return {"devanagari": 0.0, "cyrillic": 0.0, "han": 0.0, "latin": 0.0}

    return {
        "devanagari": len(_DEVANAGARI_RE.findall(text)) / total,
        "cyrillic": len(_CYRILLIC_RE.findall(text)) / total,
        "han": len(_HAN_RE.findall(text)) / total,
        "latin": len(_LATIN_RE.findall(text)) / total,
    }


def _count_markers(text, markers):
    text_low = f" {text.lower()} "
    return sum(1 for token in markers if token in text_low)


def detect_resume_language(text):
    text = _safe_text(text)
    if not text:
        return "English"

    ratios = _script_ratios(text)

    # If one non-Latin script is clearly dominant, prefer it even when a few
    # English tokens (for skills/tools) are present.
    if ratios["han"] >= 0.45 and ratios["han"] > ratios["latin"]:
        return "Chinese"
    if ratios["cyrillic"] >= 0.45 and ratios["cyrillic"] > ratios["latin"]:
        return "Russian"
    if ratios["devanagari"] >= 0.45 and ratios["devanagari"] > ratios["latin"]:
        hindi_score = _count_markers(text, _HINDI_MARKERS)
        marathi_score = _count_markers(text, _MARATHI_MARKERS)
        return "Marathi" if marathi_score > hindi_score else "Hindi"

    major_scripts = [name for name, value in ratios.items() if value >= 0.2]
    if len(major_scripts) >= 2:
        return "Mixed"

    if ratios["han"] >= 0.2:
        return "Chinese"
    if ratios["cyrillic"] >= 0.2:
        return "Russian"

    if ratios["devanagari"] >= 0.2:
        hindi_score = _count_markers(text, _HINDI_MARKERS)
        marathi_score = _count_markers(text, _MARATHI_MARKERS)
        if abs(hindi_score - marathi_score) <= 1 and ratios["latin"] >= 0.2:
            return "Mixed"
        return "Marathi" if marathi_score > hindi_score else "Hindi"

    if ratios["latin"] >= 0.2:
        text_low = f" {text.lower()} "
        has_umlaut = any(char in text_low for char in ["ä", "ö", "ü", "ß"])
        german_score = _count_markers(text, _GERMAN_MARKERS)
        if has_umlaut or german_score >= 2:
            return "German"
        return "English"

    return "English"


def _chunk_text(text, max_chars=3000):
    lines = text.splitlines()
    if not lines:
        return [text]

    chunks = []
    current = []
    size = 0

    for line in lines:
        line_with_newline = line + "\n"
        if size + len(line_with_newline) > max_chars and current:
            chunks.append("".join(current))
            current = [line_with_newline]
            size = len(line_with_newline)
        else:
            current.append(line_with_newline)
            size += len(line_with_newline)

    if current:
        chunks.append("".join(current))

    return chunks


def translate_to_english(text, detected_language=None):
    text = _safe_text(text)
    if not text:
        return ""

    language = detected_language or detect_resume_language(text)
    if language == "English":
        return text

    if GoogleTranslator is None:
        return text

    translator = GoogleTranslator(source="auto", target="en")
    translated_chunks = []

    for chunk in _chunk_text(text):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            translated_chunks.append(translator.translate(chunk))
        except Exception:
            translated_chunks.append(chunk)

    translated_text = "\n".join(translated_chunks).strip()
    return translated_text or text


def prepare_text_for_analysis(text):
    detected_language = detect_resume_language(text)
    translated_text = translate_to_english(text, detected_language=detected_language)

    if detected_language not in SUPPORTED_LANGUAGES:
        detected_language = "Mixed"

    return {
        "detected_language": detected_language,
        "translated_text": translated_text,
    }
