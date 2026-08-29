from jobmatch.matching import (
    detect_country,
    detect_language_requirements,
    extract_required_years,
    extract_skills,
    job_matches_profile,
    job_is_in_scope,
    rank_jobs,
)
from jobmatch.models import Job, SearchProfile


CV_TEXT = """
Electrical engineer with 3 years of experience in BMS function development.
Developed thermal-management functions using MATLAB, Simulink and Stateflow.
Planned MiL and HiL validation, performed root-cause analysis, and worked
according to ISO 26262 and the V-model. Experience with HV battery systems.
"""


def test_bilingual_skill_aliases_are_canonicalized():
    skills = extract_skills(
        "Modellbasierte Funktionsentwicklung und Thermomanagement für eine "
        "Hochvoltbatterie; Validierung in Simulink."
    )
    assert "Model-based development" in skills
    assert "Thermal management" in skills
    assert "HV batteries" in skills
    assert "Simulink" in skills
    assert "BESS" in extract_skills("Planung von Batteriespeichersystemen")
    assert "BESS" in extract_skills("Battery energy storage systems")


def test_country_detection_and_scope():
    assert detect_country("Munich, Bavaria, Germany") == "Germany"
    assert detect_country("München") == "Germany"
    assert detect_country("Düsseldorf") == "Germany"
    assert detect_country("Opfikon, Zürich") == "Switzerland"
    assert job_is_in_scope("Remote - Europe", ["Germany"], True, False)
    assert not job_is_in_scope("Remote - Americas", ["Germany"], True, False)
    assert not job_is_in_scope("Australia (Remote)", ["Germany"], True, False)
    assert not job_is_in_scope("London, UK", ["Germany"], False, False)


def test_experience_extraction():
    assert extract_required_years("Minimum 3 years of experience") == 3
    assert extract_required_years("Mindestens 5 Jahre Erfahrung") == 5
    assert extract_required_years("", "Senior Controls Engineer") == 5


def test_relevant_job_ranks_above_unrelated_job():
    relevant = Job(
        company="Battery Co",
        title="BMS Function Developer",
        location="Munich, Germany",
        description=(
            "Develop thermal management functions in MATLAB/Simulink. "
            "Validate battery software using MiL and HiL. Minimum 3 years of experience."
        ),
        job_url="https://example.test/relevant",
    )
    unrelated = Job(
        company="Retail Co",
        title="Fashion Store Manager",
        location="Munich, Germany",
        description="Manage retail inventory, merchandising, and store sales.",
        job_url="https://example.test/unrelated",
    )
    ranked = rank_jobs(CV_TEXT, [unrelated, relevant], 3, ["Germany"])
    assert ranked[0].job.title == "BMS Function Developer"
    assert ranked[0].match_score > ranked[1].match_score
    assert "Simulink" in ranked[0].matched_skills
    assert ranked[1].skill_score == 0


def test_transferable_model_based_skills_match_outside_battery_domain():
    aerospace_job = Job(
        company="Aerospace Co",
        title="Model-Based Controls Engineer",
        location="Munich, Germany (Hybrid)",
        description=(
            "Develop control systems with MATLAB, Simulink and Stateflow. "
            "Perform MiL and HiL validation for aerospace actuation systems. "
            "Minimum 3 years of experience. Fluent English required."
        ),
        job_url="https://example.test/aerospace",
    )
    profile = SearchProfile(
        countries=("Germany",),
        preferred_cities=("Munich",),
        work_modes=("Hybrid",),
        relocation_willing=False,
        seniorities=("Mid-level",),
        job_types=("Full-time",),
    )
    assert job_matches_profile(aerospace_job, profile)
    result = rank_jobs(
        CV_TEXT,
        [aerospace_job],
        3,
        ["Germany"],
        profile=profile,
    )[0]
    assert "Model-based development" in result.transferable_skills
    assert "Simulink" in result.transferable_skills
    assert result.skill_score >= 60
    assert result.detected_country == "Germany"
    assert result.work_mode == "Hybrid"
    assert result.language_requirements == ("English",)


def test_profile_hard_filters_city_and_excluded_keywords():
    profile = SearchProfile(
        countries=("Germany",),
        preferred_cities=("Munich",),
        work_modes=("Hybrid", "On-site"),
        relocation_willing=False,
        excluded_keywords=("sales",),
    )
    berlin_job = Job(
        company="Example",
        title="Controls Engineer",
        location="Berlin, Germany",
        description="Simulink development",
        job_url="https://example.test/berlin",
    )
    sales_job = Job(
        company="Example",
        title="Technical Sales Engineer",
        location="Munich, Germany",
        description="Simulink products",
        job_url="https://example.test/sales",
    )
    assert not job_matches_profile(berlin_job, profile)
    assert not job_matches_profile(sales_job, profile)


def test_language_detection_requires_requirement_context():
    assert detect_language_requirements("Fluent German and professional English required") == (
        "German",
        "English",
    )
    assert detect_language_requirements("The office is in Germany") == ()
