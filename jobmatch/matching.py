from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Job, MatchResult, SearchProfile


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
        "model based",
        "model based development",
        "model-based development",
        "function development",
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
    "Control systems": (
        "control systems",
        "control engineering",
        "controls engineering",
        "regelungstechnik",
        "regelungsentwicklung",
    ),
    "Systems engineering": (
        "systems engineering",
        "system engineering",
        "systementwicklung",
    ),
    "Software development": (
        "software development",
        "software engineering",
        "softwareentwicklung",
    ),
    "AUTOSAR": ("autosar",),
    "Calibration": ("calibration", "calibrating", "applikation", "kalibrierung"),
    "Linux": ("linux",),
    "CI/CD": ("ci/cd", "continuous integration", "continuous delivery"),
    "Agile/Scrum": ("agile", "scrum"),
    "Jira": ("jira",),
    "PLC": ("plc", "sps", "speicherprogrammierbare steuerung"),
}


# These skills remain valuable when the target role is outside the candidate's
# original domain. They are scored separately so, for example, automotive BMS
# experience can support a controls or model-based role in another industry.
TRANSFERABLE_SKILLS = {
    "MATLAB",
    "Simulink",
    "Stateflow",
    "Simscape",
    "Python",
    "C/C++",
    "Git",
    "SQL",
    "Model-based development",
    "MiL",
    "HiL",
    "dSPACE",
    "V-model",
    "ISO 26262",
    "Functional safety",
    "Requirements engineering",
    "Testing",
    "Test automation",
    "Diagnostics",
    "Root-cause analysis",
    "Data analysis",
    "CAN",
    "Embedded systems",
    "Electrical engineering",
    "Project management",
    "Machine learning",
    "Control systems",
    "Systems engineering",
    "Software development",
    "AUTOSAR",
    "Calibration",
    "Linux",
    "CI/CD",
    "Agile/Scrum",
    "Jira",
    "PLC",
}


COUNTRY_TERMS = {
    "Germany": {
        "germany", "deutschland", "munich", "muenchen", "berlin", "hamburg",
        "stuttgart", "aachen", "frankfurt", "cologne", "koeln", "koln",
        "duesseldorf", "dusseldorf", "munchen",
        "dortmund", "essen", "leipzig", "dresden", "erlangen", "nuremberg",
        "nuernberg", "nurnberg", "mannheim", "karlsruhe", "hanover", "hannover", "bremen",
        "freiburg", "kassel", "allendorf", "friedrichshafen", "baar-ebenhausen",
    },
    "Switzerland": {
        "switzerland", "schweiz", "suisse", "svizzera", "zurich", "zuerich",
        "basel", "bern", "geneva", "genf", "lausanne", "zug", "baar",
        "winterthur", "opfikon", "baden", "lucerne", "luzern", "st gallen",
    },
}

COUNTRY_CITIES = {
    "Germany": (
        "Aachen",
        "Allendorf",
        "Berlin",
        "Bremen",
        "Cologne",
        "Dortmund",
        "Dresden",
        "Düsseldorf",
        "Erlangen",
        "Essen",
        "Frankfurt",
        "Freiburg",
        "Friedrichshafen",
        "Hamburg",
        "Hanover",
        "Karlsruhe",
        "Kassel",
        "Leipzig",
        "Mannheim",
        "Munich",
        "Nuremberg",
        "Stuttgart",
    ),
    "Switzerland": (
        "Baar",
        "Baden",
        "Basel",
        "Bern",
        "Geneva",
        "Lausanne",
        "Lucerne",
        "Opfikon",
        "St Gallen",
        "Winterthur",
        "Zug",
        "Zurich",
    ),
}

REMOTE_TERMS = {"remote", "home office", "homeoffice", "hybrid"}
EUROPE_TERMS = {"eu", "emea", "europe", "european union"}
EXCLUDED_REMOTE_TERMS = {
    "united states", "usa", "u s", "americas", "north america", "south america",
    "canada", "australia", "new zealand", "apac", "asia", "india", "united kingdom",
    "uk", "latin america",
}

WORK_MODE_TERMS = {
    "Hybrid": ("hybrid", "home office", "homeoffice", "mobiles arbeiten"),
    "Remote": ("remote", "fully remote", "work from home"),
    "On-site": ("on site", "on-site", "onsite", "vor ort"),
}

JOB_TYPE_TERMS = {
    "Internship": ("internship", "intern ", "praktikum", "praktikant"),
    "Working student": ("working student", "werkstudent"),
    "Part-time": ("part time", "part-time", "teilzeit"),
    "Contract": ("contractor", "freelance", "befristet", "temporary"),
    "Full-time": ("full time", "full-time", "vollzeit"),
}

LANGUAGE_PATTERNS = {
    "German": (
        r"\b(?:fluent|professional|proficient|good)\s+(?:in\s+)?german\b",
        r"\bgerman\s+(?:language|skills|proficiency)\b",
        r"\bdeutschkenntnisse\b",
        r"\b(?:fließende|fliessende|sehr gute|gute)\s+deutschkenntnisse\b",
    ),
    "English": (
        r"\b(?:fluent|professional|proficient|good)\s+(?:in\s+)?english\b",
        r"\benglish\s+(?:language|skills|proficiency)\b",
        r"\benglischkenntnisse\b",
        r"\b(?:fließende|fliessende|sehr gute|gute)\s+englischkenntnisse\b",
    ),
    "French": (
        r"\b(?:fluent|professional|proficient|good)\s+(?:in\s+)?french\b",
        r"\bfrench\s+(?:language|skills|proficiency)\b",
        r"\bfranzosischkenntnisse\b",
    ),
    "Italian": (
        r"\b(?:fluent|professional|proficient|good)\s+(?:in\s+)?italian\b",
        r"\bitalian\s+(?:language|skills|proficiency)\b",
        r"\bitalienischkenntnisse\b",
    ),
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


def detect_work_mode(text: str) -> str:
    normalized = normalize_text(text)
    # Hybrid descriptions often contain both "remote" and an office cadence.
    # Prefer the more specific hybrid classification in that case.
    for mode in ("Hybrid", "Remote", "On-site"):
        if any(_contains_alias(normalized, term) for term in WORK_MODE_TERMS[mode]):
            return mode
    return "Unknown"


def detect_job_type(text: str) -> str:
    normalized = normalize_text(text)
    for job_type, terms in JOB_TYPE_TERMS.items():
        if any(_contains_alias(normalized, term) for term in terms):
            return job_type
    return "Unknown"


def detect_seniority(title: str, description: str = "") -> str:
    normalized_title = normalize_text(title)
    normalized_all = normalize_text(f"{title} {description}")
    if re.search(r"\b(principal|director|head of|leiter|leitung|manager)\b", normalized_title):
        return "Lead"
    if re.search(r"\b(lead|senior|sr\.)\b", normalized_title):
        return "Senior"
    if re.search(
        r"\b(junior|graduate|entry level|berufseinsteiger|trainee)\b",
        normalized_title,
    ):
        return "Entry"
    required_years = extract_required_years(normalized_all)
    if required_years is not None:
        if required_years >= 7:
            return "Lead"
        if required_years >= 4:
            return "Senior"
        if required_years <= 1:
            return "Entry"
        return "Mid-level"
    return "Unknown"


def detect_language_requirements(text: str) -> tuple[str, ...]:
    normalized = normalize_text(text)
    languages = [
        language
        for language, patterns in LANGUAGE_PATTERNS.items()
        if any(re.search(pattern, normalized) for pattern in patterns)
    ]
    return tuple(languages)


def city_is_preferred(location: str, preferred_cities: Iterable[str]) -> bool:
    normalized = normalize_text(location)
    return any(_contains_alias(normalized, city) for city in preferred_cities)


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


def job_matches_profile(job: Job, profile: SearchProfile) -> bool:
    """Apply conservative hard filters without discarding unknown metadata."""

    text = f"{job.title} {job.location} {job.description}"
    normalized = normalize_text(text)
    if any(
        _contains_alias(normalized, keyword)
        for keyword in profile.excluded_keywords
        if normalize_text(keyword)
    ):
        return False

    work_mode = detect_work_mode(text)
    include_remote = "Remote" in profile.work_modes
    if not job_is_in_scope(
        job.location,
        profile.countries,
        include_remote=include_remote,
        include_unknown=profile.include_unknown_locations,
    ):
        return False

    if profile.work_modes and work_mode != "Unknown" and work_mode not in profile.work_modes:
        return False

    seniority = detect_seniority(job.title, job.description)
    if (
        profile.seniorities
        and seniority != "Unknown"
        and seniority not in profile.seniorities
    ):
        return False

    job_type = detect_job_type(text)
    if profile.job_types and job_type != "Unknown" and job_type not in profile.job_types:
        return False

    if (
        not profile.relocation_willing
        and profile.preferred_cities
        and work_mode != "Remote"
        and not city_is_preferred(job.location, profile.preferred_cities)
    ):
        return False
    return True


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


def _group_overlap_score(candidate_skills: set[str], role_skills: set[str]) -> float:
    if not role_skills:
        return 0.0
    overlap_ratio = len(candidate_skills & role_skills) / len(role_skills)
    return overlap_ratio * 100


def _skill_overlap_score(candidate_skills: set[str], role_skills: set[str]) -> float:
    if not role_skills:
        return 0.0

    transferable_role = role_skills & TRANSFERABLE_SKILLS
    domain_role = role_skills - TRANSFERABLE_SKILLS
    group_scores: list[tuple[float, float]] = []
    if transferable_role:
        group_scores.append((0.65, _group_overlap_score(candidate_skills, transferable_role)))
    if domain_role:
        group_scores.append((0.35, _group_overlap_score(candidate_skills, domain_role)))

    # Re-normalize if the vacancy contains evidence from only one skill group.
    weighted = sum(weight * score for weight, score in group_scores)
    weight_total = sum(weight for weight, _ in group_scores)
    score = weighted / weight_total if weight_total else 0.0

    # One recognized term is weak evidence. Three or more terms can earn the
    # full score, while cross-domain transferable evidence remains visible.
    evidence_factor = min(1.0, len(role_skills) / 3.0)
    return round(score * evidence_factor, 1)


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
    profile: SearchProfile | None = None,
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
    work_mode = detect_work_mode(f"{job.location} {job.description}")
    seniority = detect_seniority(job.title, job.description)
    job_type = detect_job_type(f"{job.title} {job.description}")
    languages = detect_language_requirements(job.description)
    preferred_city = bool(
        profile and city_is_preferred(job.location, profile.preferred_cities)
    )

    if preferred_city:
        location_score = 100.0
    elif country in set(selected_countries):
        location_score = 90.0 if profile and profile.relocation_willing else 80.0
    elif _remote_or_european_is_in_scope(job.location):
        location_score = 95.0 if not profile or "Remote" in profile.work_modes else 70.0
    else:
        location_score = 50.0

    transferable_matches = matched & TRANSFERABLE_SKILLS
    reasons: list[str] = []
    warnings: list[str] = []
    if transferable_matches:
        reasons.append(
            "Transferable technical match: " + ", ".join(sorted(transferable_matches)[:6])
        )
    domain_matches = matched - TRANSFERABLE_SKILLS
    if domain_matches:
        reasons.append("Domain match: " + ", ".join(sorted(domain_matches)[:6]))
    if required_years is None:
        warnings.append("Required experience was not stated clearly.")
    elif required_years > candidate_years:
        warnings.append(
            f"The vacancy indicates {required_years} years; the profile contains "
            f"{candidate_years:g} years."
        )
    else:
        reasons.append(f"Experience meets the detected {required_years}-year requirement.")
    if country == "Unknown":
        warnings.append("The country could not be determined reliably.")
    elif preferred_city:
        reasons.append("The vacancy is in a preferred city.")
    elif country in set(selected_countries):
        reasons.append(f"The vacancy is in selected country: {country}.")
    if work_mode == "Unknown":
        warnings.append("Remote, hybrid, or on-site mode was not stated clearly.")
    elif not profile or work_mode in profile.work_modes:
        reasons.append(f"Work mode matches the profile: {work_mode}.")
    if languages:
        reasons.append("Detected language requirements: " + ", ".join(languages))

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
        transferable_skills=tuple(sorted(transferable_matches)),
        language_requirements=languages,
        work_mode=work_mode,
        seniority=seniority,
        job_type=job_type,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
    )


def rank_jobs(
    cv_text: str,
    jobs: Iterable[Job],
    candidate_years: float,
    selected_countries: Iterable[str],
    profile: SearchProfile | None = None,
) -> list[MatchResult]:
    results = [
        score_job(cv_text, job, candidate_years, selected_countries, profile=profile)
        for job in jobs
    ]
    return sorted(results, key=lambda result: result.match_score, reverse=True)
