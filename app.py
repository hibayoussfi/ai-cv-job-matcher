from __future__ import annotations

from pathlib import Path

import streamlit as st

from jobmatch.cv_parser import CVParseError, extract_cv_text
from jobmatch.export import build_excel, results_to_dataframe
from jobmatch.matching import job_is_in_scope, rank_jobs
from jobmatch.sources import fetch_many, load_sources


ROOT = Path(__file__).resolve().parent
SOURCE_CONFIG = ROOT / "config" / "sources.yaml"

st.set_page_config(page_title="AI CV Job Matcher", page_icon="🎯", layout="wide")
st.title("🎯 AI CV Job Matcher")
st.caption("CV-to-job matching from selected official company career feeds")

with st.expander("How the score works", expanded=False):
    st.markdown(
        """
        The score is a ranking aid, **not the probability of being hired**.

        - 40% bilingual skill overlap
        - 20% role-title relevance
        - 15% CV/job text similarity
        - 15% experience fit
        - 10% location fit

        Open the exported workbook to see every component and the matched and
        missing skills. Human review is still required.
        """
    )

sources = load_sources(SOURCE_CONFIG)
source_by_name = {source["name"]: source for source in sources}

with st.sidebar:
    st.header("Search settings")
    countries = st.multiselect(
        "Countries", ["Germany", "Switzerland"], default=["Germany", "Switzerland"]
    )
    candidate_years = st.number_input(
        "Relevant experience (years)", min_value=0.0, max_value=30.0, value=3.0, step=0.5
    )
    minimum_score = st.slider("Minimum match score", 0, 100, 35)
    include_remote = st.checkbox("Include remote/European roles", value=True)
    include_unknown = st.checkbox(
        "Include unclear locations",
        value=False,
        help="Enable this if a feed omits country information; inspect those results manually.",
    )
    selected_names = st.multiselect(
        "Official sources",
        options=list(source_by_name),
        default=list(source_by_name),
    )

uploaded_cv = st.file_uploader(
    "Upload your CV",
    type=["pdf", "docx", "txt"],
    help="The file is processed in memory and is not added to the project repository.",
)

st.info(
    "Privacy: do not commit your CV, API keys, employer code, or confidential project "
    "information to a public GitHub repository."
)

scan = st.button("Find and rank jobs", type="primary", use_container_width=True)

if scan:
    if uploaded_cv is None:
        st.error("Upload a CV first.")
        st.stop()
    if not countries:
        st.error("Select at least one country.")
        st.stop()
    if not selected_names:
        st.error("Select at least one official source.")
        st.stop()

    try:
        cv_text = extract_cv_text(uploaded_cv.name, uploaded_cv.getvalue())
    except CVParseError as exc:
        st.error(str(exc))
        st.stop()

    selected_sources = [source_by_name[name] for name in selected_names]
    with st.spinner("Reading official feeds and calculating matches…"):
        jobs, errors = fetch_many(selected_sources)
        scoped_jobs = [
            job
            for job in jobs
            if job_is_in_scope(
                job.location,
                countries,
                include_remote=include_remote,
                include_unknown=include_unknown,
            )
        ]
        ranked = rank_jobs(cv_text, scoped_jobs, candidate_years, countries)
        results = [result for result in ranked if result.match_score >= minimum_score]

    st.session_state["results"] = results
    st.session_state["scan_counts"] = (len(jobs), len(scoped_jobs))
    st.session_state["source_errors"] = errors

if "results" in st.session_state:
    results = st.session_state["results"]
    total_jobs, scoped_jobs = st.session_state["scan_counts"]
    errors = st.session_state["source_errors"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Jobs retrieved", total_jobs)
    col2.metric("Jobs in scope", scoped_jobs)
    col3.metric("Matches shown", len(results))

    for error in errors:
        st.warning(f"One source was skipped: {error}")

    if not results:
        st.warning(
            "No jobs passed the current filters. Lower the minimum score or include "
            "unclear locations, then scan again."
        )
    else:
        dataframe = results_to_dataframe(results)
        display_columns = [
            "Match score",
            "Job title",
            "Company",
            "Location",
            "Matched skills",
            "Missing skills",
            "Official job URL",
        ]
        st.subheader("Ranked matches")
        st.dataframe(
            dataframe[display_columns],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Match score": st.column_config.ProgressColumn(
                    "Match score", min_value=0, max_value=100, format="%.1f"
                ),
                "Official job URL": st.column_config.LinkColumn("Official job URL"),
            },
        )
        st.download_button(
            "Download Excel report",
            data=build_excel(results),
            file_name="job_matches.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
