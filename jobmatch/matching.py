from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Job, MatchResult


# Bilingual aliases make skill matching useful when the CV and job ad use
# different English/German wording. The list is intentionally inspectable.
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "MATLAB": ("matlab",),
    "Simulink": ("simulink",),
    "Stateflow": ("stateflow",),
    "Simscape": ("simscape",),
    "Python": ("python",),
    "C/C++": ("c++", "cpp", "c programming"),
    "Git": ("git", "github"),
    "SQL": ("sql",),
    "BMS": ("bms", "battery management system", "batteriemanagementsystem"),
    "HV batteries": (
        "high voltage battery",
        "high-voltage battery",
        "hv battery",
        "hochvoltbatterie",
        "hochvolt batterie",
    ),
    "Battery systems": ("battery systems", "batteriesystem", "batteriesysteme"),
    "BESS": (
        "bess",
        "battery energy storage system",
        "battery energy storage systems",
        "battery storage",
        "energy storage",
        "energiespeicher",
        "batteriespeicher",
        "batteriespeichersystem",
        "batteriespeichersysteme",
        "batteriespeichersystemen",
    ),
    "Thermal management": ("thermal management", "thermomanagement"),
    "Model-based development": (
        "model based development",
        "model-based development",
        "modellbasierte entwicklung",
        "funktionsentwicklung",
    ),
    "MiL": ("model in the loop", "model-in-the-loop", "mil testing", "mil test"),
    "HiL": ("hardware in the loop", "hardware-in-the-loop", "hil testing", "hil test"),
    "dSPACE": ("dspace", "micro labbox", "microlabbox"),
    "V-model": ("v-model", "v model", "v-modell"),
    "ISO 26262": ("iso 26262",),
    "Functional safety": ("functional safety", "funktionale sicherheit", "fu si", "fusi"),
    "Requirements engineering": (
        "requirements engineering",
        "requirement management",
        "requirements management",
        "anforderungsmanagement",
        "anforderungsanalyse",
    ),
    "Testing": ("testing", "validation", "verification", "validierung", "verifikation"),
    "Test automation": ("test automation", "testautomatisierung", "automated testing"),
    "Diagnostics": ("diagnostics", "diagnostic", "diagnose", "fehlerdiagnose"),
    "Root-cause analysis": (
        "root cause analysis",
        "root-cause analysis",
        "ursachenanalyse",
        "fehleranalyse",
    ),
    "Data analysis": ("data analysis", "datenanalyse", "field data", "felddaten"),
    "CAN": ("can bus", "can-bus", "canape", "canoe"),
    "Embedded systems": ("embedded systems", "embedded software", "eingebettete systeme"),
    "Electrical engineering": (
        "electrical engineering",
        "electrical engineer",
        "elektrotechnik",
        "elektroingenieur",
        "elektroingenieurin",
    ),
    "Power electronics": ("power electronics", "leistungselektronik"),
    "Power systems": ("power systems", "electrical grid", "stromnetz", "energienetze"),
    "Grid connection": ("grid connection", "grid integration", "netzanschluss", "netzintegration"),
    "PCS/inverters": ("power conversion system", "pcs", "inverter", "wechselrichter"),
    "EMS": ("energy management system", "energiemanagementsystem"),
    "SCADA": ("scada",),
    "Renewable energy": ("renewable energy", "erneuerbare energien"),
    "Project management": ("project management", "projektmanagement", "projektleitung"),
    "Machine learning": ("machine learning", "maschinelles lernen"),
}


COUNTRY_TERMS = {
    "Germany": {
        "germany", "deutschland", "munich", "muenchen", "berlin", "hamburg",
        "stuttgart", "aachen", "frankfurt", "cologne", "koeln", "duesseldorf",
        "dortmund", "essen", "leipzig", "dresden", "erlangen", "nuremberg",
        "nuernberg", "mannheim", "karlsruhe", "hanover", "hannover", "bremen",
        "freiburg", "kassel", "allendorf", "friedrichshafen", "baar-ebenhausen",
    },
    "Switzerland": {
        "switzerland", "schweiz", "suisse", "svizzera", "zurich", "zuerich",
        "basel", "bern", "geneva", "genf", "lausanne", "zug", "baar",
        "winterthur", "opfikon", "baden", "lucerne", "luzern", "st gallen",
    },
}

REMOTE_TERMS = {"remote", "home office", "homeoffice", "hybrid"}
EUROPE_TERMS = {"eu", "emea", "europe", "european union"}
EXCLUDED_REMOTE_TERMS = {
    "united states", "usa", "u s", "americas", "north america", "south america",
    "canada", "australia", "new zealand", "apac", "asia", "india", "united kingdom",
    "uk", "latin america",
}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_alias(normalized_text: str, alias: str) -> bool:
    normalized_alias = normalize_text(alias)
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])"
    return bool(re.search(pattern, normalized_text))


def extract_skills(text: str) -> set[str]:
    normalized = normalize_text(text)
    return {
        skill
        for skill, aliases in SKILL_ALIASES.items()
        if any(_contains_alias(normalized, alias) for alias in aliases)
    }


def text_similarity(cv_text: str, job_text: str) -> float:
    if not cv_text.strip() or not job_text.strip():
        return 0.0
    try:
        vectors = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=1,
            max_features=25_000,
        ).fit_transform([normalize_text(cv_text), normalize_text(job_text)])
    except ValueError:
        return 0.0
    return round(float(cosine_similarity(vectors[0], vectors[1])[0, 0]) * 100, 1)


def detect_country(location: str) -> str:
    normalized = normalize_text(location)
    matches = [
        country
        for country, terms in COUNTRY_TERMS.items()
        if any(_contains_alias(normalized, term) for term in terms)
    ]
    return matches[0] if len(matches) == 1 else "Unknown"


def is_remote(location: str) -> bool:
    normalized = normalize_text(location)
    return any(_contains_alias(normalized, term) for term in REMOTE_TERMS)


def _remote_or_european_is_in_scope(location: str) -> bool:
    normalized = normalize_text(location)
    if any(_contains_alias(normalized, term) for term in EXCLUDED_REMOTE_TERMS):
        return False
    return is_remote(location) and any(
        _contains_alias(normalized, term) for term in EUROPE_TERMS
    )


def job_is_in_scope(
    location: str,
    selected_countries: Iterable[str],
    include_remote: bool,
    include_unknown: bool,
) -> bool:
    country = detect_country(location)
    if country in set(selected_countries):
        return True
    if include_remote and _remote_or_european_is_in_scope(location):
        return True
    return include_unknown and country == "Unknown"


def extract_required_years(text: str, title: str = "") -> int | None:
    normalized = normalize_text(f"{title} {text}")
    patterns = (
        r"(?:minimum|min\.?|at least|mindestens)\s*(\d{1,2})\s*(?:\+\s*)?(?:years|year|jahre|jahren)",
        r"(\d{1,2})\s*(?:\+\s*)?(?:years|year|jahre|jahren)(?:\s+of)?\s+(?:experience|erfahrung)",
    )
    values = [
        int(match)
        for pattern in patterns
        for match in re.findall(pattern, normalized)
        if 0 <= int(match) <= 20
    ]
    if values:
        return min(values)

    if re.search(r"\b(principal|director|head of|leiter|leitung)\b", normalized):
        return 8
    if re.search(r"\b(lead|senior|sr\.)\b", normalized):
        return 5
    if re.search(r"\b(junior|graduate|entry level|berufseinsteiger)\b", normalized):
        return 0
    return None


def _experience_score(required_years: int | None, candidate_years: float) -> float:
    if required_years is None:
        return 70.0  # neutral: the ad did not provide enough evidence
    gap = max(0.0, required_years - candidate_years)
    return round(max(0.0, 100.0 - gap * 25.0), 1)


def _skill_overlap_score(candidate_skills: set[str], role_skills: set[str]) -> float:
    if not role_skills:
        return 0.0
    overlap_ratio = len(candidate_skills & role_skills) / len(role_skills)
    # One generic matched term is weak evidence. Require at least three
    # recognized role skills before full overlap can earn 100 points.
    evidence_factor = min(1.0, len(role_skills) / 3.0)
    return round(overlap_ratio * evidence_factor * 100, 1)


def _title_relevance(cv_text: str, cv_skills: set[str], title: str) -> float:
    title_skills = extract_skills(title)
    if title_skills:
        # A title is concise, so every detected title skill is strong evidence.
        return round(len(cv_skills & title_skills) / len(title_skills) * 100, 1)
    # Preserve a small signal for titles not covered by the skill vocabulary.
    return round(min(100.0, text_similarity(cv_text, title) * 2.0), 1)


def score_job(
    cv_text: str,
    job: Job,
    candidate_years: float,
    selected_countries: Iterable[str],
) -> MatchResult:
    cv_skills = extract_skills(cv_text)
    job_skills = extract_skills(f"{job.title} {job.description}")
    matched = cv_skills & job_skills
    missing = job_skills - cv_skills

    # Missing evidence earns zero rather than a neutral score. Otherwise
    # unrelated jobs can rank well merely because their company boilerplate is broad.
    skill_score = _skill_overlap_score(cv_skills, job_skills)
    role_score = _title_relevance(cv_text, cv_skills, job.title)
    lexical_score = text_similarity(cv_text, f"{job.title} {job.description}")
    required_years = extract_required_years(job.description, job.title)
    experience_score = _experience_score(required_years, candidate_years)

    country = detect_country(job.location)
    if country in set(selected_countries):
        location_score = 100.0
    elif _remote_or_european_is_in_scope(job.location):
        location_score = 85.0
    else:
        location_score = 50.0

    total = round(
        0.40 * skill_score
        + 0.20 * role_score
        + 0.15 * lexical_score
        + 0.15 * experience_score
        + 0.10 * location_score,
        1,
    )
    return MatchResult(
        job=job,
        match_score=total,
        skill_score=skill_score,
        role_score=role_score,
        text_score=lexical_score,
        experience_score=experience_score,
        location_score=location_score,
        matched_skills=tuple(sorted(matched)),
        missing_skills=tuple(sorted(missing)),
        required_years=required_years,
        detected_country=country,
    )


def rank_jobs(
    cv_text: str,
    jobs: Iterable[Job],
    candidate_years: float,
    selected_countries: Iterable[str],
) -> list[MatchResult]:
    results = [
        score_job(cv_text, job, candidate_years, selected_countries) for job in jobs
    ]
    return sorted(results, key=lambda result: result.match_score, reverse=True)
