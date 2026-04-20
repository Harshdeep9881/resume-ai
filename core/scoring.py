import re
from .embeddings import extract_skills
from .multilingual import prepare_text_for_analysis

SECTION_ORDER = ["experience", "projects", "education"]
SECTION_WEIGHTS = {
    "experience": 0.5,
    "projects": 0.3,
    "education": 0.2,
}

MUST_WEIGHT = 0.7
NICE_WEIGHT = 0.3

HEADING_MAP = {
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
    ],
    "projects": [
        "projects",
        "project experience",
        "selected projects",
        "project work",
    ],
    "education": [
        "education",
        "academics",
        "academic background",
        "education history",
    ],
    "skills": [
        "skills",
        "technical skills",
        "core skills",
        "tools",
        "technologies",
    ],
    "summary": [
        "summary",
        "professional summary",
        "profile",
        "about",
    ],
}

MUST_HEADERS = {
    "requirements",
    "qualifications",
    "what you bring",
    "what we are looking for",
    "must have",
    "must-haves",
    "required",
}

NICE_HEADERS = {
    "preferred qualifications",
    "preferred",
    "nice to have",
    "nice-to-have",
    "bonus",
    "plus",
}

MUST_KEYWORDS = [
    "must",
    "required",
    "requirement",
    "need to",
    "need",
    "you will",
]

NICE_KEYWORDS = [
    "nice to have",
    "nice-to-have",
    "preferred",
    "bonus",
    "plus",
]

ADJACENT_SKILLS = {
    "AWS": ["AWS Cloud Practitioner", "AWS Solutions Architect Associate"],
    "GCP": ["Google Cloud Digital Leader", "Associate Cloud Engineer"],
    "Azure": ["Azure Fundamentals", "Azure Administrator Associate"],
    "Kubernetes": ["CKA prep course", "Kubernetes Fundamentals"],
    "Docker": ["Docker Fundamentals", "Containerization workshops"],
    "React": ["Advanced React patterns", "TypeScript with React"],
    "Node.js": ["REST API design", "Express.js fundamentals"],
    "Python": ["Python for data pipelines", "Backend with Django"],
    "SQL": ["SQL for analytics", "Database design basics"],
    "Machine Learning": ["ML foundations", "Applied ML projects"],
}


def _clean_line(line):
    return re.sub(r"\s+", " ", line or "").strip()


def _normalize_header(line):
    return re.sub(r"[:\-]+$", "", line.strip().lower())


def _detect_heading(line):
    normalized = _normalize_header(line)
    for section, labels in HEADING_MAP.items():
        if normalized in labels:
            return section
    return None


def parse_resume_sections(text):
    sections = {key: "" for key in list(HEADING_MAP.keys()) + ["other"]}
    current = "other"
    for raw_line in (text or "").splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue
        heading = _detect_heading(line)
        if heading:
            current = heading
            continue
        sections[current] += line + "\n"
    return sections


def classify_job_requirements(job_text, selected_skills=None):
    prepared_job = prepare_text_for_analysis(job_text)
    job_text_en = prepared_job["translated_text"]

    must_skills = set(selected_skills or [])
    nice_skills = set()
    current_mode = None

    for raw_line in (job_text_en or "").splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue

        header = _normalize_header(line)
        if header in MUST_HEADERS:
            current_mode = "must"
            continue
        if header in NICE_HEADERS:
            current_mode = "nice"
            continue

        line_lower = line.lower()
        line_mode = current_mode

        if any(keyword in line_lower for keyword in MUST_KEYWORDS):
            line_mode = "must"
        if any(keyword in line_lower for keyword in NICE_KEYWORDS):
            line_mode = "nice"

        skills = set(extract_skills(line))
        if not skills:
            continue

        if line_mode == "nice":
            nice_skills |= skills
        else:
            must_skills |= skills

    if not must_skills and not nice_skills:
        must_skills = set(extract_skills(job_text_en))

    nice_skills -= must_skills
    return must_skills, nice_skills


def _section_score(section_skills, must_skills, nice_skills):
    if not must_skills and not nice_skills:
        return 0.0, set(), set()

    must_match = section_skills & must_skills
    nice_match = section_skills & nice_skills
    must_ratio = len(must_match) / len(must_skills) if must_skills else 0.0
    nice_ratio = len(nice_match) / len(nice_skills) if nice_skills else 0.0

    score = (MUST_WEIGHT * must_ratio) + (NICE_WEIGHT * nice_ratio)
    return round(score, 4), must_match, nice_match


def _normalize_section_weights(sections):
    active = [s for s in SECTION_ORDER if sections.get(s, "").strip()]
    if not active:
        return {s: 1.0 / len(SECTION_ORDER) for s in SECTION_ORDER}

    total = sum(SECTION_WEIGHTS[s] for s in active)
    return {s: (SECTION_WEIGHTS[s] / total) for s in active}


def _find_evidence_line(text, skill):
    if not text or not skill:
        return None
    pattern = re.compile(rf"\b{re.escape(skill)}\b", re.IGNORECASE)
    for raw_line in text.splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue
        if pattern.search(line):
            return line[:160]
    return None


def _fallback_evidence_lines(text, max_lines=4):
    lines = []
    for raw_line in (text or "").splitlines():
        line = _clean_line(raw_line)
        if len(line) < 20:
            continue
        lines.append(line[:160])
        if len(lines) >= max_lines:
            break
    return lines


def build_fit_summary(sections, must_skills, nice_skills):
    bullets = []
    used_lines = set()
    used_skills = set()

    for section in SECTION_ORDER:
        text = sections.get(section, "")
        section_skills = extract_skills(text)
        prioritized = [s for s in section_skills if s in must_skills] + [
            s for s in section_skills if s in nice_skills
        ]
        for skill in prioritized:
            if skill in used_skills:
                continue
            line = _find_evidence_line(text, skill)
            if not line or line in used_lines:
                continue
            bullets.append(f"{section.title()} shows {skill}: \"{line}\"")
            used_lines.add(line)
            used_skills.add(skill)
            if len(bullets) >= 6:
                return bullets

    if len(bullets) < 4:
        fallback_sections = SECTION_ORDER + ["skills", "summary", "other"]
        for section in fallback_sections:
            text = sections.get(section, "")
            for line in _fallback_evidence_lines(text):
                if line in used_lines:
                    continue
                bullets.append(f"{section.title()} evidence: \"{line}\"")
                used_lines.add(line)
                if len(bullets) >= 4:
                    return bullets

    if len(bullets) < 4:
        bullets.append('Resume evidence unavailable: "No extractable text found."')

    return bullets[:6]


def build_gap_analysis(missing_skills):
    if not missing_skills:
        return ["No major gaps found for must-have requirements."]

    gaps = []
    for skill in sorted(missing_skills)[:6]:
        suggestions = ADJACENT_SKILLS.get(
            skill, [f"{skill} fundamentals course", f"Hands-on {skill} project"]
        )
        suggestions_text = ", ".join(suggestions[:2])
        gaps.append(f"Missing {skill}. Suggested next steps: {suggestions_text}.")
    return gaps


def score_resume(job_text, resume_text, selected_skills=None, precomputed=None):
    prepared_resume = prepare_text_for_analysis(resume_text)
    resume_text_en = prepared_resume["translated_text"]

    if precomputed:
        must_skills, nice_skills = precomputed
    else:
        must_skills, nice_skills = classify_job_requirements(job_text, selected_skills)

    sections = parse_resume_sections(resume_text_en)
    section_scores = {}
    section_matches = {}
    all_resume_skills = set()

    has_primary_sections = any(sections.get(section, "").strip() for section in SECTION_ORDER)

    for section in SECTION_ORDER:
        section_text = sections.get(section, "")
        section_skills = set(extract_skills(section_text))
        all_resume_skills |= section_skills
        score, must_match, nice_match = _section_score(
            section_skills, must_skills, nice_skills
        )
        section_scores[section] = score
        section_matches[section] = {
            "skills": sorted(section_skills),
            "must_match": sorted(must_match),
            "nice_match": sorted(nice_match),
        }

    # Fallback for resumes without clear headings (common in multilingual CVs).
    if not has_primary_sections:
        fallback_text = "\n".join(filter(None, sections.values()))
        fallback_skills = set(extract_skills(fallback_text))
        all_resume_skills |= fallback_skills
        fallback_score, fallback_must, fallback_nice = _section_score(
            fallback_skills, must_skills, nice_skills
        )
        for section in SECTION_ORDER:
            section_scores[section] = fallback_score
            section_matches[section] = {
                "skills": sorted(fallback_skills),
                "must_match": sorted(fallback_must),
                "nice_match": sorted(fallback_nice),
            }

    weight_map = _normalize_section_weights(sections)
    overall_score = 0.0
    for section, weight in weight_map.items():
        overall_score += section_scores.get(section, 0.0) * weight

    matched_skills = sorted(all_resume_skills & (must_skills | nice_skills))
    missing_skills = sorted(must_skills - all_resume_skills)

    fit_summary = build_fit_summary(sections, must_skills, nice_skills)
    if len(fit_summary) < 4:
        fit_summary += ['Additional evidence not found: "Limited extractable text."'] * (
            4 - len(fit_summary)
        )

    gap_analysis = build_gap_analysis(missing_skills)

    return {
        "overall_score": round(overall_score, 4),
        "detected_language": prepared_resume["detected_language"],
        "section_scores": section_scores,
        "section_matches": section_matches,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "must_skills": sorted(must_skills),
        "nice_skills": sorted(nice_skills),
        "fit_summary": fit_summary[:6],
        "gap_analysis": gap_analysis,
    }
