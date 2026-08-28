from io import BytesIO

from openpyxl import load_workbook

from jobmatch.export import build_excel
from jobmatch.models import Job, MatchResult


def test_excel_contains_ranked_job_and_clickable_link():
    job = Job(
        company="Example Energy",
        title="Battery Engineer",
        location="Berlin, Germany",
        description="BMS and Simulink",
        job_url="https://example.test/job",
        apply_url="https://example.test/job/apply",
        provider="Test",
    )
    result = MatchResult(
        job=job,
        match_score=82.5,
        skill_score=90,
        role_score=80,
        text_score=60,
        experience_score=100,
        location_score=100,
        matched_skills=("BMS", "Simulink"),
        missing_skills=("CAN",),
        required_years=3,
        detected_country="Germany",
    )
    workbook = load_workbook(BytesIO(build_excel([result])))
    sheet = workbook["Job matches"]
    assert sheet["B2"].value == 82.5
    assert sheet["O2"].hyperlink.target == "https://example.test/job"
    assert workbook["Method"]["B9"].value.startswith("Scores support review")
