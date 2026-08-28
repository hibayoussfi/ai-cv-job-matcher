# JobMatch AI 

A local Streamlit tool that reads a CV, retrieves live vacancies from selected
official company career feeds in Germany and Switzerland, ranks the vacancies,
and exports the results to a formatted Excel workbook.

## What the first version does

- Accepts text-based PDF, DOCX, and TXT CVs.
- Reads public job feeds from Greenhouse, Lever, Ashby, Recruitee, and Personio.
- Starts with six official sources: Enpal, Climeworks, TWAICE, Voltfang,
  The Mobility House, and Entrix.
- Filters Germany, Switzerland, remote Europe, and uncertain locations.
- Shows an explainable score instead of an opaque hiring probability.
- Exports ranked jobs, score components, skills, and application links to Excel.
- Processes the CV in memory; the repository ignores CV files.

## What it does **not** do

- It does not search every company in Germany and Switzerland.
- It does not bypass website protections or scrape sites that prohibit it.
- It does not apply automatically.
- Its score is not a prediction that a company will interview or hire you.
- Scanned PDFs need OCR, which is outside this first version.

That boundary is deliberate. Career systems differ substantially. The MVP uses
documented public feeds and fails visibly when one source is unavailable.

## Scoring

| Component | Weight | Meaning |
|---|---:|---|
| Skill overlap | 40% | Bilingual, inspectable engineering-skill aliases |
| Role-title relevance | 20% | Extra evidence from the concise job title, reducing boilerplate bias |
| Text similarity | 15% | Character n-gram TF-IDF similarity between CV and vacancy |
| Experience fit | 15% | Candidate years compared with explicit/inferred requirement |
| Location fit | 10% | Selected country or remote/European compatibility |

The Excel file exposes every component plus matched and missing skills.

## Windows setup

Open PowerShell in this project folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The app will open at `http://localhost:8501`. For later launches, double-click
`run_app.bat`.

## Run the tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

GitHub Actions runs the same tests after each push.

## Add another official company source

Edit `config/sources.yaml`. First confirm the company's actual ATS and board
slug from its official career page. Supported examples:

```yaml
- name: Example Company
  provider: greenhouse
  slug: company-board-token

- name: Another Company
  provider: lever
  slug: company-site-name
```

Public-feed documentation:

- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html)
- [Lever Postings API](https://github.com/lever/postings-api)
- [Ashby Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api)
- [Recruitee Careers Site API](https://docs.recruitee.com/reference/intro-to-careers-site-api)
- [Personio open-position XML](https://developer.personio.de/v1.0/reference/get_xml)

## Suggested next versions

1. Add more verified German and Swiss company sources.
2. Add optional multilingual embeddings and compare them with the transparent
   baseline rather than assuming the more complex model is better.
3. Store result history locally and flag new or removed jobs.
4. Add unit-tested connectors only for ATS platforms with permitted public
   endpoints.

## Privacy

Never commit a real CV, API key, password, or confidential employer/customer
information. `.gitignore` blocks common CV formats, but you remain responsible
for checking every commit.
