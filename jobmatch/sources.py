from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import requests
import yaml
from bs4 import BeautifulSoup

from .models import Job, SourceStatus


USER_AGENT = "JobMatchAI/0.1 (personal portfolio project; public job feeds only)"
TIMEOUT_SECONDS = 20


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


def _get_json(url: str) -> Any:
    response = requests.get(
        url,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    response.raise_for_status()
    return response.json()


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

    # Some feeds occasionally publish duplicate localized entries.
    unique: dict[tuple[str, str, str], Job] = {}
    for job in jobs:
        key = (
            re.sub(r"\s+", " ", job.company.lower()).strip(),
            re.sub(r"\s+", " ", job.title.lower()).strip(),
            job.job_url,
        )
        unique[key] = job
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
    return list(unique.values()), sorted(errors), ordered_statuses
