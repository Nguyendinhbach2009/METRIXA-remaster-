<p align="center">
  <img src="public/LOGO_STARFOX.png" alt="Metrixa Logo" width="160" />
</p>

<h1 align="center">METRIXA</h1>

<p align="center">
  <strong>Ranking Vietnamese Universities by Research Output</strong>
</p>

<p align="center">
  <em>
    An open-source platform that collects scholarly papers, analyzes author affiliations,
    and produces transparent, data-driven university rankings across 23 academic fields.
  </em>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-data-pipeline">Data Pipeline</a> •
  <a href="#-database">Database</a> •
  <a href="#-frontend">Frontend</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## 📖 Overview

**Metrixa** ranks universities in Vietnam based on their scholarly research contributions.
It works by:

1. **Collecting papers** — from the [OpenAlex API](https://openalex.org) (and previously from local CSV/JSON shards)
2. **Extracting affiliations** — mapping each author to their university
3. **Computing rankings** — using a fractional contribution model:
   each paper's "credit" is split equally among its authors and across its subfields
4. **Visualizing results** — through an interactive React web app with field filtering,
   search, and detailed per-university breakdowns

> **Contribution formula:**  
> For a paper with **N** authors and **S** subfields, each (author, subfield) pair
> receives a contribution of `1 / (N × S)`.

---

## 🚀 Quick Start

### Prerequisites

| Tool       | Version  | Purpose                     |
| ---------- | -------- | --------------------------- |
| Node.js    | ≥ 18     | Frontend dev server & build |
| Python     | ≥ 3.10   | Backend data pipeline       |
| PostgreSQL | ≥ 14     | Database                    |

### 1. Clone & install

```bash
git clone https://github.com/Nguyendinhbach2009/METRIXA-remaster-.git
cd METRIXA-remaster-
npm install
```

### 2. Set up the database

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE proj_paper;"
```

### 3. Fetch data from OpenAlex

```bash
pip install requests psycopg2-binary

# Fetch Vietnamese-affiliated papers (resumable, cursor-paginated)
python backend/fetch_openalex.py

# Or fetch a small batch for testing
python backend/fetch_openalex.py --max-papers 500 --skip-rebuild
```

### 4. Run the frontend

```bas
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🏗 Architecture

```
metrixa/
│
├── backend/                    # Python data pipeline
│   ├── fetch_openalex.py       # 🆕 Fetch papers from OpenAlex → PostgreSQL
│   ├── config.py               # Data source paths & file range config
│   ├── preprocess_data.py      # Generate frontend-ready JSON files
│   ├── university_ranking_processor.py
│   │                           # Core ranking algorithm
│   ├── university_ranking_by_mainfield.py
│   │                           # Per-mainfield ranking aggregation
│   └── embeddings_extraction.py
│                               # t-SNE embeddings for 3D visualization
│
├── db/
│   ├── schema.sql              # Full PostgreSQL schema (staging + core)
│   └── migrate_to_postgres.py  # Legacy CSV/JSON → PostgreSQL migration
│
├── src/                        # React frontend (Vite + MUI)
│   ├── App.jsx                 # Root component
│   ├── components/
│   │   ├── Header.jsx          # App header / branding
│   │   ├── MainContent.jsx     # Layout: sidebar + ranking table
│   │   ├── FieldsSelector.jsx  # Hierarchical field/subfield picker
│   │   ├── RankingTable.jsx    # Sortable university ranking table
│   │   ├── UniversityCard.jsx  # University summary card
│   │   ├── UniversityModal.jsx # Detailed per-university breakdown
│   │   ├── ChartComponent.jsx  # Contribution charts
│   │   └── SearchBar.jsx       # University search input
│   ├── hooks/
│   │   └── useFieldData.js     # Data loading & ranking hooks
│   ├── lib/
│   │   └── utils.js            # Field mapping utilities
│   └── data/                   # Pre-generated ranking JSON files
│       ├── fields.json         # Field/subfield hierarchy
│       ├── rankings/           # Per-mainfield ranking files
│       └── <FieldName>/        # Per-subfield ranking files
│
├── public/
│   ├── fields.csv              # Main field → subfield mapping (23 fields, 485 subfields)
│   └── points_list.json        # 3D embedding coordinates for visualization
│
└── test/                       # Test files & prototypes
```

---

## 🔄 Data Pipeline

The project supports **two data paths** — the new OpenAlex pipeline and the legacy CSV/JSON pipeline.

### Path A — OpenAlex API (recommended)

```
┌─────────────┐     cursor      ┌──────────────┐    rebuild     ┌──────────────┐
│  OpenAlex   │───pagination──▶ │   staging.*  │──────────────▶│   core.*     │
│  /works API │                 │  raw_papers  │               │  papers      │
│             │                 │  raw_affiliations            │  authors     │
└─────────────┘                 └──────────────┘               │  universities│
                                                               │  paper_authors│
                                                               │  rankings    │
                                                               └──────────────┘
```

```bash
# Full fetch (all Vietnamese papers, auto-rebuilds core tables)
python backend/fetch_openalex.py

# Year-filtered fetch
python backend/fetch_openalex.py --from-year 2020 --to-year 2025

# Resume interrupted fetch (cursor state is auto-saved)
python backend/fetch_openalex.py
```

**Key flags:**

| Flag                | Description                                         |
| ------------------- | --------------------------------------------------- |
| `--email`           | Email for OpenAlex polite pool (higher rate limits)  |
| `--from-year`       | Only fetch papers from this year onwards             |
| `--to-year`         | Only fetch papers up to this year                    |
| `--max-papers`      | Stop after N papers (for testing)                    |
| `--truncate-staging`| Clear staging tables before inserting                |
| `--skip-rebuild`    | Don't rebuild core tables after fetching             |
| `--no-resume`       | Ignore saved cursor state, start fresh               |

### Path B — Legacy CSV/JSON migration

```bash
# Requires shard CSV files and merge.json on the server
python db/migrate_to_postgres.py \
  --project-root /home/dtth/proj_paper \
  --host 127.0.0.1 \
  --dbname proj_paper
```

### Generating frontend data

After loading data into PostgreSQL, generate the static JSON files used by the frontend:

```bash
cd backend
python preprocess_data.py
```

This creates:
- `src/data/fields.json` — field hierarchy
- `src/data/<FieldName>/<subfield>.json` — per-subfield rankings
- `src/data/rankings/<mainfield>_rankings.json` — per-mainfield rankings

---

## 🗄 Database

### Schema overview

The database uses **two schemas**:

**`staging`** — raw ingestion tables (append-only, no constraints)

| Table                  | Purpose                                   |
| ---------------------- | ----------------------------------------- |
| `raw_papers`           | Paper metadata as-is from source          |
| `raw_affiliations`     | Author–affiliation pairs per paper        |

**`core`** — normalized, deduplicated tables (rebuilt from staging)

| Table / View                        | Purpose                                       |
| ----------------------------------- | --------------------------------------------- |
| `papers`                            | Deduplicated papers with parsed JSONB fields   |
| `authors`                           | Unique author names                            |
| `universities`                      | Unique institution names                       |
| `paper_authors`                     | Paper ↔ Author ↔ University junction           |
| `paper_subfields`                   | Paper ↔ Subfield junction                      |
| `paper_mainfields`                  | Paper ↔ Main field junction                    |
| `mv_subfield_university_ranking`    | Materialized view: rankings by subfield        |
| `mv_overall_university_contribution`| Materialized view: overall rankings            |
| `v_subfield_university_ranking`     | View: subfield rankings with university names  |
| `v_overall_university_ranking`      | View: overall rankings with university names   |

### Rebuilding rankings

```sql
-- Rebuild all core tables from staging data
CALL core.rebuild_core_from_staging();

-- Refresh ranking views
REFRESH MATERIALIZED VIEW core.mv_subfield_university_ranking;
REFRESH MATERIALIZED VIEW core.mv_overall_university_contribution;
```

### Quick queries

```sql
-- Top 10 universities overall
SELECT * FROM core.v_overall_university_ranking
ORDER BY rank LIMIT 10;

-- Top universities in "Artificial Intelligence"
SELECT * FROM core.v_subfield_university_ranking
WHERE subfield = 'Artificial Intelligence'
ORDER BY rank LIMIT 10;

-- How many papers per university
SELECT u.name, count(*) AS papers
FROM core.paper_authors pa
JOIN core.universities u ON u.university_id = pa.university_id
GROUP BY u.name
ORDER BY papers DESC
LIMIT 20;
```

---

## 🖥 Frontend

Built with **React 19 + Vite + Material UI**, the frontend provides:

- **Field selector** — hierarchical picker for 23 main fields and 485 subfields
- **Ranking table** — sortable, searchable university rankings
- **University modal** — detailed breakdown showing per-field contributions, author lists, and charts
- **3D visualization** — t-SNE embedding of papers in 3D space (Three.js)

### Development

```bash
npm run dev       # Start dev server (http://localhost:5173)
npm run build     # Production build
npm run preview   # Preview production build
npm run lint      # Run ESLint
```

### Tech stack

| Layer      | Technology                          |
| ---------- | ----------------------------------- |
| Framework  | React 19                            |
| Bundler    | Vite (rolldown-vite)                |
| UI Library | Material UI 7                       |
| Styling    | Tailwind CSS 4                      |
| Icons      | Lucide React                        |
| 3D Viz     | Three.js                            |

---

## 🌐 Academic Fields Covered

The ranking system covers **23 main fields** with **485 subfields**:

| | | | |
|---|---|---|---|
| Mathematics | Physics | Chemistry | Biology |
| Computer Science | Engineering | Medicine | Materials Science |
| Environmental Science | Geology | Geography | Economics |
| Business | Education | Psychology | Sociology |
| Political Science | Law | Philosophy | History |
| Linguistics | Art | Agricultural & Food Sciences | |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m "Add my feature"`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## 📄 License

This project is open source. See the repository for license details.

---

<p align="center">
  <sub>Built with ❤️ for Vietnamese academia</sub>
</p>