from __future__ import annotations

import hashlib
import html
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from jobmatch.cv_parser import CVParseError, anonymize_cv_text, extract_cv_text
from jobmatch.export import build_excel, results_to_dataframe
from jobmatch.matching import COUNTRY_CITIES, job_matches_profile, rank_jobs
from jobmatch.models import MatchResult, SearchProfile
from jobmatch.sources import fetch_many_with_status, load_sources


ROOT = Path(__file__).resolve().parent
SOURCE_CONFIG = ROOT / "config" / "sources.yaml"
WORK_MODES = ("On-site", "Hybrid", "Remote")
SENIORITIES = ("Entry", "Mid-level", "Senior", "Lead")
JOB_TYPES = ("Full-time", "Part-time", "Contract", "Internship", "Working student")
APPLICATION_STATUSES = ("Not reviewed", "Saved", "Applied", "Rejected")

st.set_page_config(
    page_title="JobMatch AI — Explainable job matching",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        :root {
            --jm-ink: #172033;
            --jm-muted: #62708a;
            --jm-blue: #2563eb;
            --jm-blue-dark: #173ea5;
            --jm-blue-soft: #eaf1ff;
            --jm-teal: #0f766e;
            --jm-border: #dfe5ef;
            --jm-surface: #ffffff;
            --jm-shadow: 0 10px 30px rgba(23, 32, 51, 0.07);
        }

        .stApp {
            background:
                radial-gradient(circle at 8% 0%, rgba(37, 99, 235, 0.08), transparent 24rem),
                #f7f9fc;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 2rem;
            padding-bottom: 5rem;
        }

        .jm-hero {
            position: relative;
            overflow: hidden;
            padding: 2.5rem 2.75rem;
            border: 1px solid #cfdaf0;
            border-radius: 24px;
            background: linear-gradient(135deg, #0f2454 0%, #173ea5 60%, #2563eb 100%);
            box-shadow: 0 18px 45px rgba(23, 62, 165, 0.18);
            color: white;
            margin-bottom: 1.6rem;
        }

        .jm-hero::after {
            content: "";
            position: absolute;
            width: 22rem;
            height: 22rem;
            right: -8rem;
            top: -10rem;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.09);
        }

        .jm-eyebrow {
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.13em;
            text-transform: uppercase;
            color: #cfe0ff;
            margin-bottom: 0.7rem;
        }

        .jm-hero h1 {
            color: white;
            font-size: clamp(2rem, 5vw, 3.35rem);
            line-height: 1.05;
            letter-spacing: -0.045em;
            max-width: 800px;
            margin: 0;
        }

        .jm-hero p {
            max-width: 760px;
            margin: 1rem 0 0;
            color: #e4edff;
            font-size: 1.05rem;
            line-height: 1.6;
        }

        .jm-trust-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1.35rem;
        }

        .jm-trust-pill,
        .jm-tag {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 650;
            line-height: 1;
        }

        .jm-trust-pill {
            padding: 0.58rem 0.8rem;
            color: white;
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.18);
        }

        .jm-section-head {
            display: flex;
            gap: 0.9rem;
            align-items: flex-start;
            margin: 2.2rem 0 0.85rem;
        }

        .jm-step {
            flex: 0 0 auto;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 2rem;
            height: 2rem;
            border-radius: 10px;
            background: var(--jm-blue-soft);
            color: var(--jm-blue-dark);
            font-weight: 800;
            font-size: 0.86rem;
        }

        .jm-section-head h2 {
            color: var(--jm-ink);
            font-size: 1.35rem;
            line-height: 1.25;
            letter-spacing: -0.02em;
            margin: 0;
        }

        .jm-section-head p {
            color: var(--jm-muted);
            margin: 0.2rem 0 0;
            font-size: 0.92rem;
        }

        .jm-inline-note {
            padding: 0.85rem 1rem;
            border-radius: 12px;
            border: 1px solid #d7e2f6;
            background: #f5f8ff;
            color: #40506d;
            font-size: 0.86rem;
            line-height: 1.5;
        }

        .jm-tag-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin: 0.25rem 0 0.8rem;
        }

        .jm-tag {
            padding: 0.42rem 0.62rem;
            color: #34425c;
            background: #f1f4f9;
            border: 1px solid #e0e6ef;
        }

        .jm-tag--high {
            color: #146c43;
            background: #eaf8f0;
            border-color: #bde7ce;
        }

        .jm-tag--medium {
            color: #8a5a12;
            background: #fff7e5;
            border-color: #f4d99a;
        }

        .jm-tag--low {
            color: #6b4f32;
            background: #f8f1e9;
            border-color: #e9d6c0;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--jm-border);
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.94);
            box-shadow: var(--jm-shadow);
        }

        div[data-testid="stMetric"] {
            min-height: 112px;
            padding: 1rem 1.05rem;
            border: 1px solid var(--jm-border);
            border-radius: 14px;
            background: var(--jm-surface);
            box-shadow: 0 6px 18px rgba(23, 32, 51, 0.045);
        }

        div[data-testid="stMetricLabel"] {
            color: var(--jm-muted);
        }

        div[data-testid="stFileUploaderDropzone"] {
            min-height: 150px;
            border: 1.5px dashed #9eb4dc;
            border-radius: 14px;
            background: #f7faff;
        }

        .stButton > button,
        .stDownloadButton > button,
        .stLinkButton > a {
            min-height: 44px;
            border-radius: 10px;
            font-weight: 650;
        }

        .stButton > button[kind="primary"] {
            min-height: 50px;
            background: linear-gradient(135deg, var(--jm-blue-dark), var(--jm-blue));
            border: 0;
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.22);
        }

        div[data-testid="stTabs"] button {
            font-weight: 650;
        }

        section[data-testid="stSidebar"] {
            border-right: 1px solid var(--jm-border);
            background: #ffffff;
        }

        .jm-sidebar-brand {
            padding: 0.2rem 0 0.9rem;
        }

        .jm-sidebar-brand strong {
            display: block;
            color: var(--jm-ink);
            font-size: 1.1rem;
        }

        .jm-sidebar-brand span {
            color: var(--jm-muted);
            font-size: 0.82rem;
        }

        @media (max-width: 700px) {
            .block-container {
                padding-top: 1rem;
            }
            .jm-hero {
                padding: 1.6rem 1.35rem;
                border-radius: 18px;
            }
            .jm-hero h1 {
                font-size: 2rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def _section_header(step: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="jm-section-head">
            <span class="jm-step">{html.escape(step)}</span>
            <div>
                <h2>{html.escape(title)}</h2>
                <p>{html.escape(description)}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _score_band(score: float) -> tuple[str, str]:
    if score >= 70:
        return "High match", "high"
    if score >= 50:
        return "Moderate match", "medium"
    return "Exploratory match", "low"


def _record_key(result: MatchResult) -> str:
    return (
        result.job.apply_url
        or result.job.job_url
        or f"{result.job.company}|{result.job.title}|{result.job.location}"
    )


def _render_tags(result: MatchResult) -> None:
    band_label, band_class = _score_band(result.match_score)
    tags = [
        (band_label, f"jm-tag--{band_class}"),
        (result.work_mode, ""),
        (result.seniority, ""),
        (result.job_type, ""),
    ]
    if result.detected_country != "Unknown":
        tags.append((result.detected_country, ""))
    rendered = "".join(
        f'<span class="jm-tag {css_class}">{html.escape(label)}</span>'
        for label, css_class in tags
    )
    st.markdown(f'<div class="jm-tag-row">{rendered}</div>', unsafe_allow_html=True)


def _render_job_card(
    result: MatchResult,
    index: int,
    records: dict[str, dict[str, str]],
) -> None:
    record_key = _record_key(result)
    job_key = hashlib.sha256(record_key.encode("utf-8")).hexdigest()[:12]
    record = records.setdefault(record_key, {"status": "Not reviewed"})

    with st.container(border=True):
        title_col, score_col = st.columns([5, 1.1], vertical_alignment="top")
        with title_col:
            st.caption(f"MATCH {index:02d} · {result.job.company}")
            st.subheader(result.job.title)
            st.caption(result.job.location or "Location not provided")
            _render_tags(result)
        with score_col:
            st.metric("Match", f"{result.match_score:.1f}%")

        st.progress(
            max(0.0, min(1.0, result.match_score / 100)),
            text=f"Current status: {record.get('status', 'Not reviewed')}",
        )

        save_col, applied_col, reject_col, apply_col = st.columns(4)
        if save_col.button("Save", key=f"save_{job_key}", use_container_width=True):
            record["status"] = "Saved"
            st.rerun()
        if applied_col.button(
            "Mark applied",
            key=f"applied_{job_key}",
            use_container_width=True,
        ):
            record["status"] = "Applied"
            record.setdefault("application_date", date.today().isoformat())
            st.rerun()
        if reject_col.button(
            "Dismiss",
            key=f"reject_{job_key}",
            use_container_width=True,
        ):
            record["status"] = "Rejected"
            st.rerun()

        apply_url = result.job.apply_url or result.job.job_url
        if apply_url:
            apply_col.link_button("Open official role", apply_url, use_container_width=True)
        else:
            apply_col.button(
                "Link unavailable",
                disabled=True,
                key=f"no_link_{job_key}",
                use_container_width=True,
            )

        with st.expander("View match evidence and notes"):
            score1, score2, score3, score4 = st.columns(4)
            score1.metric("Skills", f"{result.skill_score:.1f}%")
            score2.metric("Role title", f"{result.role_score:.1f}%")
            score3.metric("Experience", f"{result.experience_score:.1f}%")
            score4.metric("Location", f"{result.location_score:.1f}%")

            evidence_col, review_col = st.columns(2)
            with evidence_col:
                st.markdown("##### Why it matches")
                if result.reasons:
                    for reason in result.reasons:
                        st.markdown(f"- {reason}")
                else:
                    st.caption("No strong structured evidence was detected.")

                if result.transferable_skills:
                    st.markdown("##### Transferable skills")
                    st.write(", ".join(result.transferable_skills))

            with review_col:
                st.markdown("##### Check before applying")
                if result.warnings:
                    for warning in result.warnings:
                        st.markdown(f"- {warning}")
                else:
                    st.caption("No uncertainty warnings were generated.")

                if result.missing_skills:
                    st.markdown("##### Missing skills detected")
                    st.write(", ".join(result.missing_skills))

            requirement_bits: list[str] = []
            if result.required_years is not None:
                requirement_bits.append(f"{result.required_years} years experience")
            if result.language_requirements:
                requirement_bits.append(
                    "Languages: " + ", ".join(result.language_requirements)
                )
            if requirement_bits:
                st.info(" · ".join(requirement_bits))

            note = st.text_input(
                "Private note for this application",
                value=record.get("notes", ""),
                key=f"note_{job_key}",
                placeholder="Why this role is interesting, contact person, next step…",
            )
            if st.button("Save note", key=f"save_note_{job_key}"):
                record["notes"] = note
                st.rerun()


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

st.markdown(
    """
    <div class="jm-hero">
        <div class="jm-eyebrow">Explainable CV-to-job matching</div>
        <h1>Find roles that fit your real technical strengths.</h1>
        <p>
            Search verified company career feeds, compare requirements with your CV,
            and turn the best opportunities into an application-ready Excel tracker.
        </p>
        <div class="jm-trust-row">
            <span class="jm-trust-pill">Official career feeds</span>
            <span class="jm-trust-pill">Transparent scoring</span>
            <span class="jm-trust-pill">Privacy-aware processing</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        """
        <div class="jm-sidebar-brand">
            <strong>JobMatch AI</strong>
            <span>Professional search workspace</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("#### Search coverage")
    st.write(f"{len(sources)} verified company feeds")
    st.caption(
        "This is transparent partial coverage, not every employer in Germany or "
        "Switzerland."
    )
    st.divider()
    st.markdown("#### Privacy")
    st.caption(
        "CV text is processed for the active session and is not intentionally saved "
        "or written to application logs."
    )

    if "results" in st.session_state:
        st.divider()
        total_jobs, scoped_jobs = st.session_state["scan_counts"]
        records = st.session_state["application_records"]
        st.markdown("#### Current search")
        st.metric("Retrieved", total_jobs)
        st.metric("After filters", scoped_jobs)
        status_counts = {
            status: sum(1 for record in records.values() if record.get("status") == status)
            for status in APPLICATION_STATUSES[1:]
        }
        st.caption(
            f"Saved {status_counts['Saved']} · Applied {status_counts['Applied']} · "
            f"Dismissed {status_counts['Rejected']}"
        )

_section_header(
    "01",
    "Upload your CV",
    "Use a text-based PDF, DOCX, or TXT file up to 5 MB.",
)

with st.container(border=True):
    upload_col, privacy_col = st.columns([1.45, 1], gap="large")
    with upload_col:
        uploaded_cv = st.file_uploader(
            "CV file",
            type=["pdf", "docx", "txt"],
            key=f"cv_upload_{st.session_state['cv_upload_version']}",
            help="The file is processed in memory and is never added to GitHub.",
        )
        if uploaded_cv is not None:
            file_size_mb = len(uploaded_cv.getvalue()) / (1024 * 1024)
            st.success(f"{uploaded_cv.name} is ready · {file_size_mb:.2f} MB")
            if st.button("Remove CV", use_container_width=False):
                st.session_state["cv_upload_version"] += 1
                st.rerun()

    with privacy_col:
        st.markdown("##### Privacy controls")
        anonymize = st.checkbox(
            "Remove common personal identifiers",
            value=True,
            help="Redacts emails, phone numbers, URLs, and names entered below.",
        )
        names_to_remove = st.text_input(
            "Names to redact (optional)",
            placeholder="First name, last name",
            disabled=not anonymize,
        )
        st.markdown(
            """
            <div class="jm-inline-note">
                For a public deployment, start with an anonymized CV. Processing in
                memory reduces exposure, but does not make a public server private.
            </div>
            """,
            unsafe_allow_html=True,
        )

_section_header(
    "02",
    "Define your search",
    "Start broad, then use advanced filters only when they reflect a real constraint.",
)

with st.container(border=True):
    st.markdown("##### Location and working model")
    country_col, city_col = st.columns(2, gap="large")
    with country_col:
        countries = st.multiselect(
            "Preferred countries",
            list(COUNTRY_CITIES),
            default=["Germany", "Switzerland"],
            key="preferred_countries",
        )
    city_options = sorted(
        city for country in countries for city in COUNTRY_CITIES.get(country, ())
    )
    existing_cities = st.session_state.get("preferred_cities", [])
    valid_cities = [city for city in existing_cities if city in city_options]
    if existing_cities != valid_cities:
        st.session_state["preferred_cities"] = valid_cities
    with city_col:
        preferred_cities = st.multiselect(
            "Preferred cities",
            city_options,
            key="preferred_cities",
            help=(
                "With relocation enabled, cities improve ranking. Otherwise they "
                "become strict filters for non-remote jobs."
            ),
        )

    preference_col, relocation_col = st.columns([1.5, 1], gap="large")
    with preference_col:
        work_modes = st.multiselect(
            "Work mode",
            WORK_MODES,
            default=list(WORK_MODES),
            key="work_modes",
        )
    with relocation_col:
        relocation_willing = st.checkbox(
            "I am willing to relocate",
            value=True,
            key="relocation_willing",
        )

    with st.expander("Advanced filters", expanded=False):
        advanced1, advanced2, advanced3 = st.columns(3, gap="large")
        with advanced1:
            candidate_years = st.number_input(
                "Relevant experience",
                min_value=0.0,
                max_value=30.0,
                value=3.0,
                step=0.5,
                help="Years relevant to the roles you want, not total employment.",
            )
            minimum_score = st.slider("Minimum match score", 0, 100, 35)
        with advanced2:
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
        with advanced3:
            excluded_text = st.text_input(
                "Excluded keywords",
                placeholder="sales, internship",
                help="Comma-separated terms removed before scoring.",
            )
            include_unknown = st.checkbox(
                "Include unclear locations",
                value=False,
                help="Keep them with a warning instead of rejecting them.",
            )

        selected_names = st.multiselect(
            "Official company sources",
            options=list(source_by_name),
            default=list(source_by_name),
        )
        st.caption(
            "Every selected feed is reported in Source coverage after the search, "
            "including failures and zero-result sources."
        )

    selected_city_text = ", ".join(preferred_cities) or "any city"
    selected_mode_text = ", ".join(work_modes) or "no mode selected"
    st.markdown(
        f"""
        <div class="jm-inline-note">
            <strong>Search summary:</strong> {html.escape(', '.join(countries) or 'no country')}
            · {html.escape(selected_city_text)} · {html.escape(selected_mode_text)}
        </div>
        """,
        unsafe_allow_html=True,
    )
    scan = st.button(
        "Search and rank official jobs",
        type="primary",
        use_container_width=True,
    )

if scan:
    if uploaded_cv is None:
        st.error("Upload a CV before starting the search.")
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
        st.error("Select at least one official company source.")
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

    with st.status("Searching verified company feeds…", expanded=True) as search_status:
        st.write("Reading official vacancy feeds")
        jobs, errors, source_statuses = _fetch_selected(tuple(selected_names))
        st.write("Applying your location and role constraints")
        scoped_jobs = [job for job in jobs if job_matches_profile(job, profile)]
        st.write("Calculating explainable match scores")
        ranked = rank_jobs(
            cv_text,
            scoped_jobs,
            candidate_years,
            countries,
            profile=profile,
        )
        results = [result for result in ranked if result.match_score >= minimum_score]
        search_status.update(
            label=f"Search complete — {len(results)} matches ready",
            state="complete",
            expanded=False,
        )

    st.session_state["results"] = results
    st.session_state["all_ranked_results"] = ranked
    st.session_state["scan_counts"] = (len(jobs), len(scoped_jobs))
    st.session_state["source_errors"] = errors
    st.session_state["source_statuses"] = source_statuses
    del cv_bytes, cv_text

if "results" not in st.session_state:
    st.markdown(
        """
        <div class="jm-inline-note" style="margin-top: 1.2rem;">
            <strong>What happens next:</strong> the app retrieves fresh vacancies,
            applies your hard filters, ranks the remaining roles, and explains every
            score. It never applies on your behalf.
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    results = st.session_state["results"]
    all_ranked = st.session_state["all_ranked_results"]
    total_jobs, scoped_jobs = st.session_state["scan_counts"]
    errors = st.session_state["source_errors"]
    source_statuses = st.session_state["source_statuses"]
    records = st.session_state["application_records"]

    _section_header(
        "03",
        "Review your matches",
        "Use the cards for decisions, the table for comparison, and Excel for tracking.",
    )

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Jobs retrieved", total_jobs)
    metric2.metric("After hard filters", scoped_jobs)
    metric3.metric("Above score threshold", len(results))
    metric4.metric(
        "Sources healthy",
        f"{sum(status.status != 'Failed' for status in source_statuses)}/{len(source_statuses)}",
    )

    if errors:
        st.warning(
            f"{len(errors)} source{' was' if len(errors) == 1 else 's were'} unavailable. "
            "Review Source coverage before treating the results as complete."
        )

    results_tab, table_tab, coverage_tab = st.tabs(
        ["Job cards", "Comparison table", "Source coverage"]
    )

    with results_tab:
        toolbar1, toolbar2, toolbar3, toolbar4 = st.columns([1.3, 1.4, 1.2, 0.8])
        with toolbar1:
            result_scope = st.radio(
                "Result set",
                ["Top matches", "All filtered jobs"],
                horizontal=True,
            )
        base_results = results if result_scope == "Top matches" else all_ranked
        company_options = sorted({result.job.company for result in base_results})
        with toolbar2:
            result_query = st.text_input(
                "Search results",
                placeholder="Title, company, location or skill",
            )
        with toolbar3:
            status_filter = st.selectbox(
                "Application status",
                ["All statuses", *APPLICATION_STATUSES],
            )
        with toolbar4:
            card_limit = st.selectbox("Show", [10, 25, 50, "All"])

        selected_companies = st.multiselect(
            "Filter companies",
            company_options,
            placeholder="All companies",
        )
        query = result_query.strip().lower()
        filtered_results: list[MatchResult] = []
        for result in base_results:
            searchable = " ".join(
                [
                    result.job.title,
                    result.job.company,
                    result.job.location,
                    " ".join(result.matched_skills),
                    " ".join(result.transferable_skills),
                ]
            ).lower()
            record_status = records.get(_record_key(result), {}).get(
                "status",
                "Not reviewed",
            )
            if query and query not in searchable:
                continue
            if selected_companies and result.job.company not in selected_companies:
                continue
            if status_filter != "All statuses" and record_status != status_filter:
                continue
            filtered_results.append(result)

        visible_results = (
            filtered_results
            if card_limit == "All"
            else filtered_results[: int(card_limit)]
        )
        st.caption(
            f"Showing {len(visible_results)} of {len(filtered_results)} matching the "
            "current view filters."
        )

        if not filtered_results:
            with st.container(border=True):
                st.subheader("No jobs match this view")
                st.write(
                    "Clear the result search or status filter. If the full search is "
                    "empty, return to Step 2 and relax only the constraints that are "
                    "genuinely flexible."
                )
        else:
            for index, result in enumerate(visible_results, start=1):
                _render_job_card(result, index, records)

    with table_tab:
        table_scope = st.radio(
            "Table data",
            ["Top matches", "All filtered jobs"],
            horizontal=True,
            key="table_scope",
        )
        table_results = results if table_scope == "Top matches" else all_ranked
        dataframe = results_to_dataframe(table_results, records)
        display_columns = [
            "Match score",
            "Job title",
            "Company",
            "Location",
            "Work mode",
            "Seniority",
            "Transferable matches",
            "Missing skills",
            "Application status",
            "Official job URL",
        ]
        st.dataframe(
            dataframe[display_columns],
            hide_index=True,
            use_container_width=True,
            height=520,
            column_config={
                "Match score": st.column_config.ProgressColumn(
                    "Match score",
                    min_value=0,
                    max_value=100,
                    format="%.1f",
                ),
                "Official job URL": st.column_config.LinkColumn("Official role"),
            },
        )

    with coverage_tab:
        healthy = sum(status.status != "Failed" for status in source_statuses)
        st.markdown(
            f"**{healthy} of {len(source_statuses)} selected sources responded.** "
            "A healthy source can still return zero roles."
        )
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
        type="primary",
        use_container_width=True,
    )

st.divider()
st.caption(
    "JobMatch AI ranks evidence; it does not predict hiring decisions. Session statuses "
    "are not permanent—download Excel before closing the app."
)
