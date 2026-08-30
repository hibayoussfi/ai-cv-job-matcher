from __future__ import annotations

import base64
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import requests
import yaml
from bs4 import BeautifulSoup

from .models import Job, SourceStatus


USER_AGENT = "JobMatchAI/0.1 (personal portfolio project; public job feeds only)"
TIMEOUT_SECONDS = 20
GERMAN_SEARCH_LOCATIONS = {
    "Cologne": "Köln",
    "Düsseldorf": "Düsseldorf",
    "Hanover": "Hannover",
    "Munich": "München",
    "Nuremberg": "Nürnberg",
}


class SourceFetchError(RuntimeError):
    """Raised when one configured job source cannot be read."""


def load_sources(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("config/sources.yaml must contain a 'sources' list.")
    return sources


def _clean_html(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(BeautifulSoup(str(value), "html.parser").get_text(" ").split())


def _dict_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        preferred = ["name", "city", "country", "state", "text"]
        parts = [str(value[key]) for key in preferred if value.get(key)]
        if parts:
            return ", ".join(dict.fromkeys(parts))
    return ""


def _get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    request_headers.update(headers or {})
    response = requests.get(
        url,
        params=params,
        timeout=TIMEOUT_SECONDS,
        headers=request_headers,
    )
    response.raise_for_status()
    return response.json()


def sources_for_countries(
    sources: list[dict[str, Any]], countries: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Keep configured feeds for the requested market; retain legacy untagged feeds."""

    selected = set(countries)
    return [
        source
        for source in sources
        if not source.get("country") or source.get("country") in selected
    ]


def _timestamp_date(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value), timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def _fetch_arbeitnow(max_pages: int = 2) -> list[Job]:
    """Read a broad ATS-backed European index without requiring an API key."""

    jobs: list[Job] = []
    for page in range(1, max_pages + 1):
        payload = _get_json(
            "https://www.arbeitnow.com/api/job-board-api",
            params={"page": page},
        )
        for item in payload.get("data", []):
            listing_url = item.get("url", "")
            tags = " ".join(item.get("tags") or [])
            job_types = " ".join(item.get("job_types") or [])
            remote = "Remote" if item.get("remote") else ""
            jobs.append(
                Job(
                    company=item.get("company_name", "Unknown employer"),
                    title=item.get("title", "Untitled role"),
                    location=" ".join(
                        part for part in [item.get("location", ""), remote] if part
                    ),
                    description=" ".join(
                        part
                        for part in [
                            _clean_html(item.get("description")),
                            tags,
                            job_types,
                        ]
                        if part
                    ),
                    job_url=listing_url,
                    apply_url=listing_url,
                    source_name="Arbeitnow ATS index",
                    provider="Arbeitnow",
                    source_type="Regional ATS index",
                    published_at=_timestamp_date(item.get("created_at")),
                )
            )
        if not (payload.get("links") or {}).get("next"):
            break
    return jobs


def _location_text(locations: Any) -> str:
    parts: list[str] = []
    for location in locations or []:
        address = location.get("adresse") or location
        city = address.get("ort", "")
        region = str(address.get("region", "")).replace("_", " ").title()
        country = address.get("land", "")
        if str(country).upper() == "DEUTSCHLAND":
            country = "Germany"
        rendered = ", ".join(part for part in [city, region, country] if part)
        if rendered and rendered not in parts:
            parts.append(rendered)
    return " · ".join(parts)


def _fetch_arbeitsagentur(
    search_terms: tuple[str, ...],
    locations: tuple[str, ...],
    *,
    max_jobs: int = 60,
) -> list[Job]:
    """Search the German public employment index and hydrate vacancy details."""

    search_url = (
        "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
    )
    detail_url = (
        "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/"
    )
    headers = {"X-API-Key": "jobboerse-jobsuche"}
    localized_locations = tuple(
        GERMAN_SEARCH_LOCATIONS.get(location, location) for location in locations
    )
    queries = [
        (term, location)
        for term in search_terms[:3]
        for location in (localized_locations[:4] or ("Deutschland",))
    ]
    summaries: dict[str, dict[str, Any]] = {}
    search_errors: list[Exception] = []

    def search(query: tuple[str, str]) -> dict[str, Any]:
        term, location = query
        return _get_json(
            search_url,
            params={
                "was": term,
                "wo": location,
                "angebotsart": 1,
                "page": 1,
                "size": 25,
                "veroeffentlichtseit": 60,
                "zeitarbeit": "false",
                "pav": "false",
            },
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=min(6, max(1, len(queries)))) as executor:
        futures = [executor.submit(search, query) for query in queries]
        for future in as_completed(futures):
            try:
                payload = future.result()
            except Exception as exc:  # one city/term must not erase other results
                search_errors.append(exc)
                continue
            for item in payload.get("ergebnisliste", payload.get("stellenangebote", [])):
                reference = item.get("referenznummer") or item.get("refnr")
                if reference and reference not in summaries:
                    summaries[reference] = item
                if len(summaries) >= max_jobs:
                    break

    if not summaries and search_errors:
        raise SourceFetchError(f"Federal Employment Agency index: {search_errors[0]}")

    def hydrate(entry: tuple[str, dict[str, Any]]) -> Job:
        reference, summary = entry
        encoded = base64.b64encode(reference.encode("utf-8")).decode("ascii")
        try:
            detail = _get_json(detail_url + encoded, headers=headers)
        except Exception:
            detail = summary
        external_url = (
            detail.get("externeURL")
            or detail.get("externeUrl")
            or summary.get("externeURL")
            or summary.get("externeUrl")
        )
        public_url = (
            external_url
            or f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{reference}"
        )
        locations_value = detail.get("stellenlokationen") or summary.get(
            "stellenlokationen"
        )
        return Job(
            company=detail.get("firma") or detail.get("arbeitgeber") or summary.get(
                "firma", "Unknown employer"
            ),
            title=detail.get("stellenangebotsTitel")
            or detail.get("titel")
            or summary.get("stellenangebotsTitel", "Untitled role"),
            location=_location_text(locations_value),
            description=detail.get("stellenangebotsBeschreibung")
            or detail.get("stellenbeschreibung")
            or "",
            job_url=public_url,
            apply_url=public_url,
            source_name="Federal Employment Agency index",
            provider="Bundesagentur für Arbeit",
            source_type="Public employment index",
            published_at=detail.get("datumErsteVeroeffentlichung")
            or summary.get("datumErsteVeroeffentlichung", ""),
        )

    jobs: list[Job] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(hydrate, item) for item in list(summaries.items())]
        for future in as_completed(futures):
            jobs.append(future.result())
    return jobs


def _fetch_greenhouse(source: dict[str, Any]) -> list[Job]:
    slug = source["slug"]
    api_host = source.get("api_host", "https://boards-api.greenhouse.io")
    payload = _get_json(f"{api_host}/v1/boards/{slug}/jobs?content=true")
    return [
        Job(
            company=source["name"],
            title=item.get("title", "Untitled role"),
            location=_dict_text(item.get("location")),
            description=_clean_html(item.get("content")),
            job_url=item.get("absolute_url", ""),
            apply_url=item.get("absolute_url", ""),
            source_name=source["name"],
            provider="Greenhouse",
            published_at=item.get("updated_at", ""),
        )
        for item in payload.get("jobs", [])
    ]


def _fetch_lever(source: dict[str, Any]) -> list[Job]:
    slug = source["slug"]
    api_host = source.get("api_host", "https://api.lever.co")
    payload = _get_json(f"{api_host}/v0/postings/{slug}?mode=json")
    jobs: list[Job] = []
    for item in payload:
        categories = item.get("categories") or {}
        list_text = " ".join(
            f"{entry.get('text', '')} {_clean_html(entry.get('content'))}"
            for entry in item.get("lists", [])
        )
        description = " ".join(
            part
            for part in [
                item.get("descriptionPlain", ""),
                _clean_html(item.get("description")),
                list_text,
                _clean_html(item.get("additional")),
            ]
            if part
        )
        jobs.append(
            Job(
                company=source["name"],
                title=item.get("text", "Untitled role"),
                location=categories.get("location", ""),
                description=description,
                job_url=item.get("hostedUrl", ""),
                apply_url=item.get("applyUrl", ""),
                source_name=source["name"],
                provider="Lever",
                published_at=str(item.get("createdAt", "")),
            )
        )
    return jobs


def _fetch_ashby(source: dict[str, Any]) -> list[Job]:
    slug = source["slug"]
    payload = _get_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    )
    return [
        Job(
            company=source["name"],
            title=item.get("title", "Untitled role"),
            location=item.get("location", ""),
            description=(
                item.get("descriptionPlain")
                or _clean_html(item.get("descriptionHtml"))
            ),
            job_url=item.get("jobUrl", ""),
            apply_url=item.get("applyUrl", ""),
            source_name=source["name"],
            provider="Ashby",
            published_at=item.get("publishedAt", ""),
        )
        for item in payload.get("jobs", [])
        if item.get("isListed", True)
    ]


def _fetch_recruitee(source: dict[str, Any]) -> list[Job]:
    slug = source["slug"]
    payload = _get_json(f"https://{slug}.recruitee.com/api/offers/")
    items = payload.get("offers", payload if isinstance(payload, list) else [])
    jobs: list[Job] = []
    for item in items:
        location = item.get("location") or item.get("locations") or ""
        if isinstance(location, list):
            location = ", ".join(filter(None, (_dict_text(value) for value in location)))
        description = " ".join(
            _clean_html(item.get(key))
            for key in ("description", "requirements", "description_text")
            if item.get(key)
        )
        jobs.append(
            Job(
                company=source["name"],
                title=item.get("title", "Untitled role"),
                location=_dict_text(location) or str(location),
                description=description,
                job_url=item.get("careers_url") or item.get("url", ""),
                apply_url=item.get("careers_apply_url") or item.get("apply_url", ""),
                source_name=source["name"],
                provider="Recruitee",
                published_at=item.get("published_at", ""),
            )
        )
    return jobs


def _xml_text(element: ElementTree.Element, tag: str) -> str:
    child = element.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def _fetch_personio(source: dict[str, Any]) -> list[Job]:
    slug = source["slug"]
    language = source.get("language", "en")
    url = f"https://{slug}.jobs.personio.de/xml?language={language}"
    response = requests.get(
        url,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT, "Accept": "application/xml"},
    )
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    jobs: list[Job] = []
    for position in root.findall(".//position"):
        job_id = _xml_text(position, "id")
        description_parts: list[str] = []
        for block in position.findall(".//jobDescription"):
            description_parts.extend(
                [_xml_text(block, "name"), _clean_html(_xml_text(block, "value"))]
            )
        location = ", ".join(
            filter(None, [_xml_text(position, "office"), _xml_text(position, "subcompany")])
        )
        job_url = (
            f"https://{slug}.jobs.personio.de/job/{job_id}?display={language}"
            if job_id
            else f"https://{slug}.jobs.personio.de/"
        )
        jobs.append(
            Job(
                company=source["name"],
                title=_xml_text(position, "name") or "Untitled role",
                location=location,
                description=" ".join(filter(None, description_parts)),
                job_url=job_url,
                apply_url=job_url,
                source_name=source["name"],
                provider="Personio",
                published_at=_xml_text(position, "createdAt"),
            )
        )
    return jobs


FETCHERS = {
    "greenhouse": _fetch_greenhouse,
    "lever": _fetch_lever,
    "ashby": _fetch_ashby,
    "recruitee": _fetch_recruitee,
    "personio": _fetch_personio,
}


def fetch_source(source: dict[str, Any]) -> list[Job]:
    provider = str(source.get("provider", "")).lower()
    fetcher = FETCHERS.get(provider)
    if fetcher is None:
        raise SourceFetchError(f"Unsupported provider: {provider or 'missing'}")
    try:
        return fetcher(source)
    except (requests.RequestException, ValueError, KeyError, ElementTree.ParseError) as exc:
        raise SourceFetchError(f"{source.get('name', provider)}: {exc}") from exc


def fetch_many(sources: list[dict[str, Any]]) -> tuple[list[Job], list[str]]:
    """Fetch several independent public feeds concurrently."""
    jobs, errors, _ = fetch_many_with_status(sources)
    return jobs, errors


def fetch_many_with_status(
    sources: list[dict[str, Any]],
) -> tuple[list[Job], list[str], list[SourceStatus]]:
    """Fetch feeds and expose per-source coverage instead of hiding failures."""

    jobs: list[Job] = []
    errors: list[str] = []
    statuses: dict[str, SourceStatus] = {}
    with ThreadPoolExecutor(max_workers=min(5, max(1, len(sources)))) as executor:
        future_map = {executor.submit(fetch_source, source): source for source in sources}
        for future in as_completed(future_map):
            source = future_map[future]
            name = str(source.get("name", "Unknown source"))
            provider = str(source.get("provider", "Unknown"))
            try:
                source_jobs = future.result()
                jobs.extend(source_jobs)
                statuses[name] = SourceStatus(
                    company=name,
                    provider=provider,
                    status="OK" if source_jobs else "No jobs returned",
                    jobs_found=len(source_jobs),
                )
            except SourceFetchError as exc:
                errors.append(str(exc))
                statuses[name] = SourceStatus(
                    company=name,
                    provider=provider,
                    status="Failed",
                    message=str(exc),
                )
            except Exception as exc:  # defensive isolation between independent sources
                message = f"{name}: {exc}"
                errors.append(message)
                statuses[name] = SourceStatus(
                    company=name,
                    provider=provider,
                    status="Failed",
                    message=message,
                )

    ordered_statuses = [
        statuses.get(
            str(source.get("name", "Unknown source")),
            SourceStatus(
                company=str(source.get("name", "Unknown source")),
                provider=str(source.get("provider", "Unknown")),
                status="Not attempted",
            ),
        )
        for source in sources
    ]
    return _deduplicate_jobs(jobs), sorted(errors), ordered_statuses


def _deduplicate_jobs(jobs: list[Job]) -> list[Job]:
    """Prefer direct company feeds when the same vacancy appears in an index."""

    priority = {
        "Official company feed": 0,
        "Public employment index": 1,
        "Regional ATS index": 2,
    }
    unique: dict[tuple[str, str, str], Job] = {}
    for job in sorted(jobs, key=lambda item: priority.get(item.source_type, 9)):
        key = (
            re.sub(r"\s+", " ", job.company.lower()).strip(),
            re.sub(r"\s+", " ", job.title.lower()).strip(),
            re.sub(r"\s+", " ", job.location.lower()).strip(),
        )
        unique.setdefault(key, job)
    return list(unique.values())


def fetch_hybrid_with_status(
    sources: list[dict[str, Any]],
    countries: tuple[str, ...],
    cities: tuple[str, ...],
    search_terms: tuple[str, ...],
    relocation_willing: bool = True,
) -> tuple[list[Job], list[str], list[SourceStatus]]:
    """Combine verified feeds with broad indexes while isolating every failure."""

    selected_sources = sources_for_countries(sources, countries)
    jobs: list[Job] = []
    errors: list[str] = []
    statuses: list[SourceStatus] = []

    tasks: dict[Any, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        official_future = executor.submit(fetch_many_with_status, selected_sources)
        if set(countries) & {"Germany", "Switzerland"}:
            tasks[executor.submit(_fetch_arbeitnow)] = (
                "Arbeitnow ATS index",
                "Regional ATS index",
            )
        if "Germany" in countries and search_terms:
            federal_locations = cities
            if relocation_willing and "Deutschland" not in federal_locations:
                federal_locations = (*federal_locations, "Deutschland")
            tasks[
                executor.submit(
                    _fetch_arbeitsagentur,
                    search_terms,
                    federal_locations,
                )
            ] = (
                "Federal Employment Agency index",
                "Public employment index",
            )

        official_jobs, official_errors, official_statuses = official_future.result()
        jobs.extend(official_jobs)
        errors.extend(official_errors)
        statuses.extend(official_statuses)

        for future in as_completed(tasks):
            name, provider = tasks[future]
            try:
                source_jobs = future.result()
                jobs.extend(source_jobs)
                statuses.append(
                    SourceStatus(
                        company=name,
                        provider=provider,
                        status="OK" if source_jobs else "No jobs returned",
                        jobs_found=len(source_jobs),
                    )
                )
            except Exception as exc:
                message = f"{name}: {exc}"
                errors.append(message)
                statuses.append(
                    SourceStatus(
                        company=name,
                        provider=provider,
                        status="Failed",
                        message=message,
                    )
                )

    return _deduplicate_jobs(jobs), sorted(errors), statuses
