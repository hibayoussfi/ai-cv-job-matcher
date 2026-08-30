# JobMatch AI

A Streamlit tool that reads a CV, retrieves live vacancies from regional indexes
and verified company career feeds in Germany and Switzerland, ranks the
vacancies, and exports the results to a formatted Excel workbook.

## What V1.1 does

- Accepts text-based PDF, DOCX, and TXT CVs.
- Reads public job feeds from Greenhouse, Lever, Ashby, Recruitee, and Personio.
- Searches Germany's Federal Employment Agency vacancy index using the selected
  cities and up to three target roles or skills.
- Reads the public Arbeitnow ATS index to broaden employer coverage in the
  selected market.
- Starts with six official sources: Enpal, Climeworks, TWAICE, Voltfang,
  The Mobility House, and Entrix.
- Builds a personal search profile with countries, preferred cities, work mode,
  relocation willingness, seniority, job type, and excluded keywords.
- Applies conservative hard filters while retaining uncertain metadata with a
  visible warning.
- Separates transferable technical skills from domain skills, so experience in
  model-based development, controls, validation, or systems engineering can
  match roles outside the battery sector.
- Shows an explainable score instead of an opaque hiring probability.
- Provides expandable job cards with reasons, missing skills, warnings,
  language requirements, and a direct application link.
- Tracks Saved, Applied, and Rejected status within the current browser session.
- Exports six Excel sheets: Top Matches, All Jobs, Missing Skills, Application
  Tracker, Source Status, and Scoring Method.
- Applies a 5 MB upload limit, validates obvious file-type mismatches, and can
  redact email addresses, phone numbers, URLs, and user-provided names before
  matching.

## What it does **not** do

- It cannot guarantee every company in Germany and Switzerland. No single public
  API provides every official vacancy, and many career systems expose no
  permitted public feed. The app reports the sources actually queried.
- It does not bypass website protections or scrape sites that prohibit it.
- It does not apply automatically.
- Its score is not a prediction that a company will interview or hire you.
- Saved/application status is session-only until an external database is added.
- It does not yet use semantic embeddings or a generative-AI API.
- Scanned PDFs need OCR, which is outside V1.1.

That boundary is deliberate. Career systems differ substantially. The app uses
regional indexes plus verified public feeds and reports the status and job count
of every source it actually queried. Results are labeled as official company
feeds, public employment index entries, or regional ATS index entries.

## Scoring

| Component | Weight | Meaning |
|---|---:|---|
| Skill overlap | 40% | Bilingual, inspectable aliases with transferable engineering skills scored separately from domain skills |
| Role-title relevance | 20% | Extra evidence from the concise job title, reducing boilerplate bias |
| Text similarity | 15% | Character n-gram TF-IDF similarity between CV and vacancy |
| Experience fit | 15% | Candidate years compared with explicit/inferred requirement |
| Location fit | 10% | Selected country or remote/European compatibility |

The Excel file exposes every component, matching reasons, warnings, language
requirements, and matched/missing skills. Unknown work mode, seniority, or job
type remains visible instead of being treated as reliable data.

## Search-profile behavior

- Target roles or skills drive regional discovery. If left blank, up to three
  transferable skills are inferred from the CV.
- Preferred countries are always hard filters.
- With relocation enabled, preferred cities improve the location score.
- Without relocation, preferred cities become hard filters for non-remote jobs.
- Explicitly detected work mode, seniority, job type, and excluded keywords are
  hard filters.
- Unknown metadata is retained and flagged because rejecting it would create
  false negatives.

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

On Streamlit Community Cloud, connect this repository, select branch `main`,
entry point `app.py`, and Python 3.12. Changes merged into `main` redeploy
automatically.

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

1. Expand the verified source registry and add connectors only where official,
   permitted endpoints exist.
2. Add optional multilingual semantic embeddings and compare them with the transparent
   baseline rather than assuming the more complex model is better.
3. Add an external database for persistent Saved/Applied/Rejected status and
   flag new, previously seen, removed, and expired jobs.
4. Add unit-tested connectors only for ATS platforms with permitted public
   endpoints.

## Privacy

Never commit a real CV, API key, password, or confidential employer/customer
information. `.gitignore` blocks common CV formats, but you remain responsible
for checking every commit. The application does not intentionally save CV text
or write it to logs, but an uploaded file still passes through the Streamlit
server during the active session. Use an anonymized CV on public deployments.
