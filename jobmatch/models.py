from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Job:
    company: str
    title: str
    location: str
    description: str
    job_url: str
    apply_url: str = ""
    source_name: str = ""
    provider: str = ""
    published_at: str = ""


@dataclass(frozen=True)
class SearchProfile:
    """User-controlled constraints and preferences for one search."""

    countries: tuple[str, ...]
    preferred_cities: tuple[str, ...] = field(default_factory=tuple)
    work_modes: tuple[str, ...] = field(default_factory=tuple)
    relocation_willing: bool = True
    seniorities: tuple[str, ...] = field(default_factory=tuple)
    job_types: tuple[str, ...] = field(default_factory=tuple)
    excluded_keywords: tuple[str, ...] = field(default_factory=tuple)
    include_unknown_locations: bool = False


@dataclass(frozen=True)
class SourceStatus:
    """Observable result of querying one official company source."""

    company: str
    provider: str
    status: str
    jobs_found: int = 0
    message: str = ""


@dataclass(frozen=True)
class MatchResult:
    job: Job
    match_score: float
    skill_score: float
    role_score: float
    text_score: float
    experience_score: float
    location_score: float
    matched_skills: tuple[str, ...] = field(default_factory=tuple)
    missing_skills: tuple[str, ...] = field(default_factory=tuple)
    required_years: int | None = None
    detected_country: str = "Unknown"
    transferable_skills: tuple[str, ...] = field(default_factory=tuple)
    language_requirements: tuple[str, ...] = field(default_factory=tuple)
    work_mode: str = "Unknown"
    seniority: str = "Unknown"
    job_type: str = "Unknown"
    reasons: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
