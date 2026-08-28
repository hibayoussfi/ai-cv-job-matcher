from jobmatch.matching import (
    detect_country,
    extract_required_years,
    extract_skills,
    job_is_in_scope,
    rank_jobs,
)
from jobmatch.models import Job


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
