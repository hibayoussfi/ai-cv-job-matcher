from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from jobmatch.cv_parser import CVParseError, anonymize_cv_text, extract_cv_text
from jobmatch.export import build_excel, results_to_dataframe
from jobmatch.matching import (
    COUNTRY_CITIES,
    job_matches_profile,
    rank_jobs,
)
from jobmatch.models import SearchProfile
from jobmatch.sources import fetch_many_with_status, load_sources


ROOT = Path(__file__).resolve().parent
SOURCE_CONFIG = ROOT / "config" / "sources.yaml"
WORK_MODES = ("On-site", "Hybrid", "Remote")
SENIORITIES = ("Entry", "Mid-level", "Senior", "Lead")
JOB_TYPES = ("Full-time", "Part-time", "Contract", "Internship", "Working student")

st.set_page_config(page_title="JobMatch AI", page_icon="🎯", layout="wide")
st.title("🎯 JobMatch AI")
st.caption("CV-to-job matching from verified official company career feeds")

with st.expander("How the score works", expanded=False):
    st.markdown(
        """
        The score is a ranking aid, **not the probability of being hired**.

        - 40% skill overlap, with transferable engineering skills scored separately
        - 20% role-title relevance
        - 15% CV/job text similarity
        - 15% experience fit
        - 10% location fit

        Hard filters run before scoring. Unknown work mode, seniority, or job type is
        retained and flagged instead of being silently rejected.
        """
    )

sources = load_sources(SOURCE_CONFIG)
source_by_name = {source["name"]: source for source in sources}


@st.cache_data(ttl=1800, show_spinner=False)
def _fetch_selected(source_names: tuple[str, ...]):
    selected = [source_by_name[name] for name in source_names]
    return fetch_many_with_status(selected)


if "application_records" not in st.session_state:
    st.session_state["application_records"] = {}
if "cv_upload_version" not in st.session_state:
    st.session_state["cv_upload_version"] = 0

with st.sidebar:
    st.header("Search profile")
    countries = st.multiselect(
        "Preferred countries",
        list(COUNTRY_CITIES),
        default=["Germany", "Switzerland"],
    )
    city_options = sorted(
        city for country in countries for city in COUNTRY_CITIES.get(country, ())
    )
    preferred_cities = st.multiselect(
        "Preferred cities",
        city_options,
        help=(
            "With relocation enabled, cities improve ranking. Without relocation, "
            "they become strict filters for non-remote jobs."
        ),
    )
    relocation_willing = st.checkbox("Willing to relocate", value=True)
    work_modes = st.multiselect(
        "Work mode",
        WORK_MODES,
        default=list(WORK_MODES),
    )
    seniorities = st.multiselect(
        "Seniority",
        SENIORITIES,
        default=list(SENIORITIES),
    )
    job_types = st.multiselect(
        "Job type",
        JOB_TYPES,
        default=["Full-time"],
    )
    excluded_text = st.text_input(
        "Excluded keywords",
        placeholder="sales, internship, working student",
        help="Comma-separated terms. Matching jobs are removed before scoring.",
    )
    candidate_years = st.number_input(
        "Relevant experience (years)",
        min_value=0.0,
        max_value=30.0,
        value=3.0,
        step=0.5,
    )
    minimum_score = st.slider("Minimum match score", 0, 100, 35)
    include_unknown = st.checkbox(
        "Include unclear locations",
        value=False,
        help="Keep jobs whose country cannot be determined; they will carry a warning.",
    )
    selected_names = st.multiselect(
        "Verified official sources",
        options=list(source_by_name),
        default=list(source_by_name),
    )
    st.caption(
        "Coverage is limited to the verified feeds listed here. The app cannot "
        "guarantee every company in a country or city."
    )

uploaded_cv = st.file_uploader(
    "Upload your CV (maximum 5 MB)",
    type=["pdf", "docx", "txt"],
    key=f"cv_upload_{st.session_state['cv_upload_version']}",
    help="The app processes the file in memory and does not save it to the repository.",
)

privacy_col, clear_col = st.columns([3, 1])
with privacy_col:
    anonymize = st.checkbox(
        "Remove common personal identifiers before matching",
        value=True,
        help="Redacts email addresses, phone numbers, URLs, and names you provide below.",
    )
    names_to_remove = st.text_input(
        "Names to remove (optional)",
        placeholder="First name, last name",
        disabled=not anonymize,
    )
with clear_col:
    st.write("")
    st.write("")
    if st.button("Remove uploaded CV", use_container_width=True):
        st.session_state["cv_upload_version"] += 1
        st.rerun()

st.info(
    "Privacy boundary: the app does not intentionally save CV text or include it in "
    "logs. Uploaded data still passes through the Streamlit server for this session. "
    "Use an anonymized CV until you have reviewed your deployment settings."
)

scan = st.button("Find and rank jobs", type="primary", use_container_width=True)

if scan:
    if uploaded_cv is None:
        st.error("Upload a CV first.")
        st.stop()
    if not countries:
        st.error("Select at least one country.")
        st.stop()
    if not relocation_willing and not preferred_cities:
        st.error("Select at least one preferred city or enable relocation.")
        st.stop()
    if not work_modes:
        st.error("Select at least one work mode.")
        st.stop()
    if not selected_names:
        st.error("Select at least one verified source.")
        st.stop()

    cv_bytes = uploaded_cv.getvalue()
    try:
        cv_text = extract_cv_text(
            uploaded_cv.name,
            cv_bytes,
            mime_type=uploaded_cv.type or None,
        )
    except CVParseError as exc:
        st.error(str(exc))
        st.stop()

    if anonymize:
        names = tuple(part.strip() for part in names_to_remove.split(",") if part.strip())
        cv_text = anonymize_cv_text(cv_text, names=names)

    excluded_keywords = tuple(
        keyword.strip() for keyword in excluded_text.split(",") if keyword.strip()
    )
    profile = SearchProfile(
        countries=tuple(countries),
        preferred_cities=tuple(preferred_cities),
        work_modes=tuple(work_modes),
        relocation_willing=relocation_willing,
        seniorities=tuple(seniorities),
        job_types=tuple(job_types),
        excluded_keywords=excluded_keywords,
        include_unknown_locations=include_unknown,
    )

    with st.spinner("Reading verified feeds and calculating matches…"):
        jobs, errors, source_statuses = _fetch_selected(tuple(selected_names))
        scoped_jobs = [job for job in jobs if job_matches_profile(job, profile)]
        ranked = rank_jobs(
            cv_text,
            scoped_jobs,
            candidate_years,
            countries,
            profile=profile,
        )
        results = [result for result in ranked if result.match_score >= minimum_score]

    st.session_state["results"] = results
    st.session_state["all_ranked_results"] = ranked
    st.session_state["scan_counts"] = (len(jobs), len(scoped_jobs))
    st.session_state["source_errors"] = errors
    st.session_state["source_statuses"] = source_statuses
    del cv_bytes, cv_text

if "results" in st.session_state:
    results = st.session_state["results"]
    all_ranked = st.session_state["all_ranked_results"]
    total_jobs, scoped_jobs = st.session_state["scan_counts"]
    errors = st.session_state["source_errors"]
    source_statuses = st.session_state["source_statuses"]
    records = st.session_state["application_records"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Jobs retrieved", total_jobs)
    col2.metric("Jobs after hard filters", scoped_jobs)
    col3.metric("Matches shown", len(results))
    col4.metric("Sources searched", len(source_statuses))

    for error in errors:
        st.warning(f"One source was skipped: {error}")

    with st.expander("Source coverage for this search", expanded=bool(errors)):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Company": status.company,
                        "Provider": status.provider,
                        "Status": status.status,
                        "Jobs found": status.jobs_found,
                        "Message": status.message,
                    }
                    for status in source_statuses
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )

    if not results:
        st.warning(
            "No jobs passed the current filters. Inspect source coverage, then relax "
            "the city, job-type, or score filters deliberately."
        )
    else:
        dataframe = results_to_dataframe(results, records)
        display_columns = [
            "Match score",
            "Job title",
            "Company",
            "Location",
            "Work mode",
            "Transferable matches",
            "Application status",
            "Official job URL",
        ]
        st.subheader("Ranked matches")
        st.dataframe(
            dataframe[display_columns],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Match score": st.column_config.ProgressColumn(
                    "Match score",
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                ),
                "Official job URL": st.column_config.LinkColumn("Official job URL"),
            },
        )

        st.subheader("Review individual jobs")
        for index, result in enumerate(results, start=1):
            record_key = (
                result.job.apply_url
                or result.job.job_url
                or f"{result.job.company}|{result.job.title}|{result.job.location}"
            )
            job_key = hashlib.sha256(
                record_key.encode("utf-8")
            ).hexdigest()[:12]
            record = records.setdefault(record_key, {"status": "Not reviewed"})
            label = (
                f"{index}. {result.match_score:.1f}% — {result.job.title} "
                f"at {result.job.company}"
            )
            with st.expander(label):
                detail1, detail2, detail3, detail4 = st.columns(4)
                detail1.metric("Overall", f"{result.match_score:.1f}%")
                detail2.metric("Skills", f"{result.skill_score:.1f}%")
                detail3.metric("Experience", f"{result.experience_score:.1f}%")
                detail4.metric("Location", f"{result.location_score:.1f}%")
                st.write(
                    f"**Location:** {result.job.location or 'Not provided'} · "
                    f"**Work mode:** {result.work_mode} · "
                    f"**Seniority:** {result.seniority} · "
                    f"**Job type:** {result.job_type}"
                )
                if result.reasons:
                    st.success("Why it matches\n\n- " + "\n- ".join(result.reasons))
                if result.missing_skills:
                    st.write("**Important missing skills:** " + ", ".join(result.missing_skills))
                if result.warnings:
                    st.warning("Needs manual review\n\n- " + "\n- ".join(result.warnings))
                if result.language_requirements:
                    st.write(
                        "**Language requirements detected:** "
                        + ", ".join(result.language_requirements)
                    )
                if result.required_years is not None:
                    st.write(f"**Required experience detected:** {result.required_years} years")

                action1, action2, action3, action4 = st.columns(4)
                if action1.button("Save", key=f"save_{job_key}", use_container_width=True):
                    record["status"] = "Saved"
                    st.rerun()
                if action2.button(
                    "Applied",
                    key=f"applied_{job_key}",
                    use_container_width=True,
                ):
                    record["status"] = "Applied"
                    record.setdefault("application_date", date.today().isoformat())
                    st.rerun()
                if action3.button(
                    "Reject",
                    key=f"reject_{job_key}",
                    use_container_width=True,
                ):
                    record["status"] = "Rejected"
                    st.rerun()
                apply_url = result.job.apply_url or result.job.job_url
                if apply_url:
                    action4.link_button(
                        "Apply directly",
                        apply_url,
                        use_container_width=True,
                    )
                else:
                    action4.button(
                        "No application link",
                        disabled=True,
                        key=f"no_link_{job_key}",
                        use_container_width=True,
                    )
                st.caption(
                    f"Current status: {record.get('status', 'Not reviewed')} — "
                    "saved in this browser session and included in Excel."
                )
                note = st.text_input(
                    "Notes",
                    value=record.get("notes", ""),
                    key=f"note_{job_key}",
                )
                if st.button("Save note", key=f"save_note_{job_key}"):
                    record["notes"] = note
                    st.rerun()

    st.download_button(
        "Download complete Excel report",
        data=build_excel(
            results,
            all_results=all_ranked,
            source_statuses=source_statuses,
            application_records=records,
        ),
        file_name="jobmatch_ai_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

st.caption(
    "Session statuses are not permanent cloud history. Download the Excel tracker "
    "before closing the app. Persistent history requires a separate database release."
)
