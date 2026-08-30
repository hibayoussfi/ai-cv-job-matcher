from jobmatch import sources


def test_sources_are_selected_by_country():
    configured = [
        {"name": "German", "country": "Germany"},
        {"name": "Swiss", "country": "Switzerland"},
        {"name": "Legacy"},
    ]
    selected = sources.sources_for_countries(configured, ("Switzerland",))
    assert [item["name"] for item in selected] == ["Swiss", "Legacy"]


def test_arbeitnow_jobs_are_labeled_as_regional_index(monkeypatch):
    monkeypatch.setattr(
        sources,
        "_get_json",
        lambda *args, **kwargs: {
            "data": [
                {
                    "company_name": "Example AG",
                    "title": "Controls Engineer",
                    "description": "<p>MATLAB and Simulink</p>",
                    "location": "Zurich, Switzerland",
                    "remote": False,
                    "url": "https://www.arbeitnow.com/example",
                    "created_at": 1_700_000_000,
                    "tags": ["Engineering"],
                    "job_types": ["Full Time"],
                }
            ],
            "links": {"next": None},
        },
    )
    job = sources._fetch_arbeitnow()[0]
    assert job.company == "Example AG"
    assert job.source_type == "Regional ATS index"
    assert job.provider == "Arbeitnow"
    assert "MATLAB and Simulink" in job.description


def test_federal_index_hydrates_description_and_external_link(monkeypatch):
    searched_locations = []

    def fake_get(url, **kwargs):
        if url.endswith("/jobs"):
            searched_locations.append(kwargs["params"]["wo"])
            return {
                "ergebnisliste": [
                    {
                        "referenznummer": "10000-TEST-S",
                        "stellenangebotsTitel": "Model-Based Engineer",
                        "firma": "Example GmbH",
                        "stellenlokationen": [
                            {"adresse": {"ort": "München", "land": "DEUTSCHLAND"}}
                        ],
                    }
                ]
            }
        return {
            "referenznummer": "10000-TEST-S",
            "stellenangebotsTitel": "Model-Based Engineer",
            "stellenangebotsBeschreibung": "Develop controls with Simulink.",
            "firma": "Example GmbH",
            "stellenlokationen": [
                {"adresse": {"ort": "München", "land": "DEUTSCHLAND"}}
            ],
            "externeURL": "https://careers.example.test/job",
            "datumErsteVeroeffentlichung": "2026-08-01",
        }

    monkeypatch.setattr(sources, "_get_json", fake_get)
    job = sources._fetch_arbeitsagentur(
        ("Model-Based Engineer",),
        ("Munich",),
        max_jobs=5,
    )[0]
    assert job.description == "Develop controls with Simulink."
    assert job.location == "München, Germany"
    assert job.apply_url == "https://careers.example.test/job"
    assert job.source_type == "Public employment index"
    assert searched_locations == ["München"]
