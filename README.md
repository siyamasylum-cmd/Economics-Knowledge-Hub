# Bangladesh Economic Pulse Index

An economics intelligence dashboard that collects economics articles, summarizes them, labels topics, and computes a media-based Bangladesh Economic Pulse Index (BEPI).

The goal is to turn daily economics coverage into a searchable research tool: articles become structured evidence, evidence becomes a weekly pulse score, and selected evidence can be turned into policy briefs.

## What It Does

- Collects economics articles from Bangladesh and global RSS sources.
- Extracts readable article text when available.
- Generates summaries and topic labels.
- Computes a BEPI signal from -100 to +100 for each article.
- Stores weekly BEPI history for Bangladesh and global coverage.
- Displays a Streamlit dashboard with pulse charts, topic breakdowns, article search, and a policy brief generator.

## BEPI Methodology

BEPI is a lightweight media-based pulse index. It is not an official macroeconomic statistic.

Each article is scored by counting positive and negative economic language in the title, summary, and body text.

Positive terms include growth, recovery, stability, investment, export growth, remittance, productivity, and wage growth.

Negative terms include inflation, food inflation, crisis, deficit, unemployment, non-performing loans, debt distress, currency pressure, reserve pressure, and poverty.

The article score is calculated as:

```text
(positive_weight - negative_weight) / (positive_weight + negative_weight)
```

That value is adjusted by topic weight and scaled to a -100 to +100 range. Weekly BEPI is the average score across articles in the same geography and week.

Interpretation:

- Above 10: mildly positive coverage.
- Above 35: strongly positive coverage.
- Between -10 and 10: mixed or neutral coverage.
- Below -10: mildly negative coverage.
- Below -35: strongly negative coverage.

## Sources

Default sources are defined in `bepi/database.py`.

- The Daily Star Business
- The Financial Express
- CPD Bangladesh
- SANEM
- IMF Blog
- World Bank Blogs
- VoxEU
- NBER New Working Papers
- Marginal Revolution

## Local Setup

```powershell
setup.bat
```

Or manually:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m bepi.database
```

Copy `.env.example` to `.env` and add a Groq API key if you want AI-generated summaries and briefs. Without an API key, the app uses fallback summaries and fallback brief generation.

## Daily Pipeline

Run the full pipeline once:

```powershell
venv\Scripts\activate
python -m bepi.pipeline
```

Run the dashboard:

```powershell
streamlit run bepi/dashboard.py
```

Run the data quality audit:

```powershell
python -m bepi.audit
```

## Schedule Daily Collection on Windows

Open PowerShell in the project folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\schedule_daily_task.ps1
```

This creates a Windows Task Scheduler job named `BEPI Daily Pipeline` that runs every morning at 7:00 AM. Logs are written to `logs\daily_pipeline.log`.

## Deploy to Streamlit Cloud

1. Push this folder to a GitHub repository.
2. On Streamlit Cloud, create a new app from the repository.
3. Set the main file path to:

```text
bepi/dashboard.py
```

4. Add secrets if needed, especially `GROQ_API_KEY`.

The SQLite database is ignored by Git by default. For a public demo, either commit a small seed database intentionally, add a seed data loader, or run the collector in the hosted environment before sharing the URL.

This repo includes small CSV demo files in `bepi_data/`. If the SQLite database is missing, the dashboard automatically loads those demo files so the public Streamlit app is not empty on first deploy.

## Project Structure

- `bepi/database.py`: SQLite schema and source list.
- `bepi/collector.py`: RSS collection, text extraction, and retry handling.
- `bepi/analyzer.py`: summaries and topic labels.
- `bepi/index_engine.py`: article scoring and weekly BEPI history.
- `bepi/pipeline.py`: one-command daily pipeline.
- `bepi/audit.py`: data quality audit.
- `bepi/brief_generator.py`: policy brief generation.
- `bepi/dashboard.py`: Streamlit dashboard.
