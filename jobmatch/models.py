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
