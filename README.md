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

### ⚡ Performance & Data Filtering Optimizations
* **Vietnamese University Whitelist**: The ranking pipeline filters and processes authors and universities against a whitelisted directory list in [universities.json](src/data/universities.json). Non-Vietnamese institutions (e.g. from foreign co-authors) are excluded.
* **100-Author Limit**: To optimize network payload size and frontend memory footprint, author lists per university in the generated JSON structures are limited to the top 100 contributors. Background contribution calculations remain 100% complete.

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
**Load data from OpenAlex and add to database:**
```bash
pip install requests psycopg2-binary

# Fetch Vietnamese-affiliated papers (resumable, cursor-paginated)
python backend/fetch_from_openalex/fetch_openalex.py

# Or fetch a small batch for testing
python backend/fetch_from_openalex/fetch_openalex.py --max-papers 500 --skip-rebuild
```

### 4. Build field-subfield relationships from OpenAlex API

**Generate fields.json from OpenAlex topics API:**
```bash
# Build fields.json from OpenAlex API (run BEFORE processing)
python backend/fetch_from_openalex/fetch_openalex_fields_mapping.py

# With API key for higher rate limits
python backend/fetch_from_openalex/fetch_openalex_fields_mapping.py --api-key "your-api-key"

# With custom output path
python backend/fetch_from_openalex/fetch_openalex_fields_mapping.py --output /path/to/fields.json
```

This creates:
- `src/data/fields.json` — field hierarchy with main fields and subfields

### 5. Process data from database to JSON files

**Important:** The database must contain data before running this step. First populate it using `fetch_openalex.py`:

```bash
# Fetch data from OpenAlex into PostgreSQL
python backend/fetch_from_openalex/fetch_openalex.py --password "your_password" --max-papers 500 --skip-rebuild  # Quick test
python backend/fetch_from_openalex/fetch_openalex.py --password "your_password"  # Full fetch

# Build field-subfield mapping from OpenAlex API (if not already done)
python backend/fetch_from_openalex/fetch_openalex_fields_mapping.py

# Process the data
python backend/run.py --password "your_password"

# Or run individual components
python backend/data_processing/preprocess_data.py
```

### 6. Generate embeddings for 3D visualization

Generate t-SNE embeddings for interactive 3D visualization of papers:

```bash
# Generate embeddings (uses env vars for DB connection)
python backend/data_processing/embeddings_extraction.py

# With explicit password
python backend/data_processing/embeddings_extraction.py --password "your_password"

# With custom database settings
python backend/data_processing/embeddings_extraction.py --host "localhost" --port 5432 --user "postgres" --dbname "proj_paper" --password "your_password"
```

This creates:
- `public/points_list.json` — 3D t-SNE embeddings for all papers

**Optimization options:**
- `--max-papers N` — Limit to N papers (auto-limited to 2000 for large datasets)
- `--batch-size N` — Batch size for embedding computation (default: 64)
- `--password "xxx"` — Database password

**Environment variables:**
- `EMBEDDING_MODEL` — Sentence transformer model (default: all-MiniLM-L6-v2)
- `SKIP_EMBEDDINGS=true` — Skip embeddings, use random projection (fastest)

**Note:** For large datasets (>2000 papers), the script automatically samples 2000 papers for t-SNE to keep computation under 5 minutes. Use `--max-papers N` to control this.

**Dependencies:** `pip install sentence-transformers scikit-learn tqdm`

### 7. Run the frontend

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🏗 Architecture

```
metrixa/
│
├── backend/                         # Python data pipeline
│   ├── fetch_from_openalex/         # OpenAlex data fetching scripts
│   │   ├── fetch_openalex.py        # Fetch papers from OpenAlex → PostgreSQL
│   │   └── fetch_openalex_fields_mapping.py  # Build fields.json from OpenAlex API
│   ├── run.py                         # Main entry point for data processing
│   ├── database_connection.py       # Database connection utilities
│   ├── embeddings_extraction.py       # Generate t-SNE embeddings for 3D visualization
│   │
│   └── data_processing/             # Organized data processing scripts
│       ├── preprocess_data.py       # Generate frontend-ready JSON files
│       ├── university_ranking_processor.py  # Core ranking algorithm
│       └── university_ranking_by_mainfield.py # Per-mainfield aggregation
│
├── db/
│   └── schema.sql                   # Full PostgreSQL schema (staging + core)
│
├── src/                            # React frontend (Vite + MUI)
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
│       ├── universities.json   # Whitelist of Vietnamese institutions
│       ├── Computer_Science.json
│       ├── Medicine.json
│       ├── Physics_and_Astronomy.json
│       ├── Engineering.json
│       ├── ...                 # One file per main field
│       └── rankings/
│           ├── Computer_Science/
│           │   ├── artificial_intelligence.json
│           │   ├── computer_vision.json
│           │   └── uniFieldContrib.json
│           ├── Medicine/
│           │   ├── ...         # Subfield files
│           │   └── uniFieldContrib.json
│           └── overall_rankings.json
│
└── test/                       # Test files & prototypes
```

---

## 🔄 Data Pipeline

The project uses **database-backed processing** - data is loaded into PostgreSQL first, then processed to generate JSON files for the frontend.

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
                                                              ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    backend/data_processing/*.py                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ preprocess_data.py → src/data/fields.json,                          │   │
│  │                     <MainField>.json,                               │   │
│  │                     rankings/<MainField>/*.json                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

```bash
# Full fetch (all Vietnamese papers, auto-rebuilds core tables)
python backend/fetch_from_openalex/fetch_openalex.py

# Year-filtered fetch
python backend/fetch_from_openalex/fetch_openalex.py --from-year 2020 --to-year 2025

# Resume interrupted fetch (cursor state is auto-saved)
python backend/fetch_from_openalex/fetch_openalex.py
```

**Key flags:**

| Flag                | Description                                     |
| ------------------- | ----------------------------------------------- |
| `--email`           | Email for OpenAlex polite pool (higher rate limits)  |
| `--from-year`       | Only fetch papers from this year onwards         |
| `--to-year`         | Only fetch papers up to this year                |
| `--max-papers`      | Stop after N papers (for testing)              |
| `--truncate-staging`| Clear staging tables before inserting          |
| `--skip-rebuild`    | Don't rebuild core tables after fetching       |
| `--no-resume`       | Ignore saved cursor state, start fresh         |

### Processing data from database

After loading data into PostgreSQL, generate the static JSON files:

```bash
# Build field-subfield mapping from OpenAlex API (if not already done)
python backend/fetch_from_openalex/fetch_openalex_fields_mapping.py

# Run full pipeline
python backend/run.py

# Or run individual components
python backend/data_processing/preprocess_data.py
```

This creates:
- `src/data/fields.json` — field hierarchy with main fields and subfields
- `src/data/<MainField>.json` — combined ranking for each main field with `uniFieldContrib`
- `src/data/rankings/<MainField>/<subfield>.json` — per-subfield rankings
- `src/data/rankings/<MainField>/uniFieldContrib.json`
- `src/data/rankings/overall_rankings.json`
- `public/points_list.json` — 3D t-SNE embeddings for visualization

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

- **Field selector** — hierarchical picker for 25 main fields and 244 subfields
- **Ranking table** — sortable, searchable university rankings
- **University modal** — detailed breakdown showing per-field contributions, author lists, and charts

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

---

## 🌐 Academic Fields Covered

The ranking system covers **25 main fields** with **244 subfields**:

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