#!/usr/bin/env python3
"""
Fetch scholarly works from the OpenAlex API and load them into PostgreSQL.

This script:
  1. Queries the OpenAlex /works endpoint for papers affiliated with
     Vietnamese institutions (country_code:VN).
  2. Parses each work's authorships, topics, fields, and abstract.
  3. Inserts rows into staging.raw_papers and staging.raw_affiliations.
  4. Optionally rebuilds core tables and refreshes materialized views.

Usage examples:
  # Fetch all Vietnamese-affiliated papers (cursor-paginated, resumable):
  python fetch_openalex.py

  # Fetch only papers from 2023 onwards with a specific email for polite pool:
  python fetch_openalex.py --from-year 2023 --email you@example.com

  # Fetch a limited number for testing, skip core rebuild:
  python fetch_openalex.py --max-papers 500 --skip-rebuild

  # Use a specific filter (overrides the default Vietnam filter):
  python fetch_openalex.py --filter "authorships.institutions.country_code:VN,publication_year:2024"

Environment variables for database connection:
  PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    print(
        "ERROR: 'requests' library is required.\n"
        "Install it with:  pip install requests",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print(
        "ERROR: 'psycopg2' library is required.\n"
        "Install it with:  pip install psycopg2-binary",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OPENALEX_API_BASE = "https://api.openalex.org"
WORKS_ENDPOINT = f"{OPENALEX_API_BASE}/works"

# Default filter: papers with at least one author affiliated with a
# Vietnamese institution.
DEFAULT_FILTER = "authorships.institutions.country_code:VN"

# How many results per API page (max 200 for OpenAlex).
DEFAULT_PER_PAGE = 200

# Polite delay between API requests (seconds).  OpenAlex asks for ≤10 req/s
# for unauthenticated users; with an email ("polite pool") the limit is higher.
DEFAULT_REQUEST_DELAY = 0.12

# Where to persist the cursor so we can resume after interruption.
DEFAULT_CURSOR_FILE = "openalex_cursor_state.json"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch papers from OpenAlex API and load into PostgreSQL."
    )

    # --- Database ---
    db = parser.add_argument_group("Database connection")
    db.add_argument("--host", default=os.getenv("PGHOST", "127.0.0.1"))
    db.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")))
    db.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    db.add_argument("--dbname", default=os.getenv("PGDATABASE", "proj_paper"))
    db.add_argument("--password", default=os.getenv("PGPASSWORD", ""))

    # --- OpenAlex ---
    api = parser.add_argument_group("OpenAlex API options")
    api.add_argument(
        "--email",
        default=os.getenv("OPENALEX_EMAIL", ""),
        help="Email for OpenAlex polite pool (higher rate limit).",
    )
    api.add_argument(
        "--api-key",
        default=os.getenv("OPENALEX_API_KEY", ""),
        help="OpenAlex API key (optional, for higher rate limits).",
    )
    api.add_argument(
        "--filter",
        dest="openalex_filter",
        default=DEFAULT_FILTER,
        help=f"OpenAlex filter string. Default: '{DEFAULT_FILTER}'",
    )
    api.add_argument(
        "--from-year",
        type=int,
        default=None,
        help="Only fetch papers published from this year onwards.",
    )
    api.add_argument(
        "--to-year",
        type=int,
        default=None,
        help="Only fetch papers published up to this year.",
    )
    api.add_argument(
        "--per-page",
        type=int,
        default=DEFAULT_PER_PAGE,
        help=f"Results per API page (max 200). Default: {DEFAULT_PER_PAGE}",
    )
    api.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help="Stop after fetching this many papers (for testing).",
    )
    api.add_argument(
        "--request-delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY,
        help=f"Seconds to wait between requests. Default: {DEFAULT_REQUEST_DELAY}",
    )

    # --- Behaviour ---
    beh = parser.add_argument_group("Behaviour")
    beh.add_argument(
        "--truncate-staging",
        action="store_true",
        help="Truncate staging tables before inserting new data.",
    )
    beh.add_argument(
        "--skip-rebuild",
        action="store_true",
        help="Do not rebuild core tables / refresh views after loading.",
    )
    beh.add_argument(
        "--skip-schema",
        action="store_true",
        help="Do not apply schema.sql before running.",
    )
    beh.add_argument(
        "--cursor-file",
        default=DEFAULT_CURSOR_FILE,
        help="File path to persist cursor state for resumable fetching.",
    )
    beh.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore any saved cursor state and start from scratch.",
    )
    beh.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of rows to insert per database batch. Default: 500",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# OpenAlex helpers
# ---------------------------------------------------------------------------

def reconstruct_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> str:
    """
    Reconstruct a plain-text abstract from OpenAlex's inverted-index format.

    The inverted index maps each word to a list of positions where that word
    appears in the original abstract.  We rebuild the text by placing each
    word at its positions and joining.
    """
    if not inverted_index:
        return ""

    max_pos = -1
    for positions in inverted_index.values():
        for p in positions:
            if p > max_pos:
                max_pos = p

    if max_pos < 0:
        return ""

    words: List[Optional[str]] = [None] * (max_pos + 1)
    for word, positions in inverted_index.items():
        for p in positions:
            words[p] = word

    return " ".join(w for w in words if w is not None)


def extract_topics_hierarchy(work: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Extract the 4-level topic hierarchy from an OpenAlex work object.

    Returns a dict with keys:
      - domains:   list of domain display_names
      - fields:    list of field display_names    (≈ fieldsOfStudy / main_fields)
      - subfields: list of subfield display_names (≈ predicted_fieldsOfStudy)
      - topics:    list of topic display_names
    """
    domains: List[str] = []
    fields: List[str] = []
    subfields: List[str] = []
    topics_list: List[str] = []

    seen_domains: set = set()
    seen_fields: set = set()
    seen_subfields: set = set()
    seen_topics: set = set()

    # OpenAlex provides `topics` (list) and `primary_topic` (single).
    # We collect from both.
    all_topics = list(work.get("topics") or [])
    primary = work.get("primary_topic")
    if primary and primary not in all_topics:
        all_topics.insert(0, primary)

    for t in all_topics:
        if not isinstance(t, dict):
            continue

        # topic name
        tname = (t.get("display_name") or "").strip()
        if tname and tname not in seen_topics:
            seen_topics.add(tname)
            topics_list.append(tname)

        # subfield
        sf = t.get("subfield") or {}
        sfname = (sf.get("display_name") or "").strip() if isinstance(sf, dict) else ""
        if sfname and sfname not in seen_subfields:
            seen_subfields.add(sfname)
            subfields.append(sfname)

        # field
        fld = t.get("field") or {}
        fname = (fld.get("display_name") or "").strip() if isinstance(fld, dict) else ""
        if fname and fname not in seen_fields:
            seen_fields.add(fname)
            fields.append(fname)

        # domain
        dom = t.get("domain") or {}
        dname = (dom.get("display_name") or "").strip() if isinstance(dom, dict) else ""
        if dname and dname not in seen_domains:
            seen_domains.add(dname)
            domains.append(dname)

    return {
        "domains": domains,
        "fields": fields,
        "subfields": subfields,
        "topics": topics_list,
    }


def parse_work(work: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse a single OpenAlex work object into staging-ready dicts.

    Returns a dict with:
      - paper: dict matching staging.raw_papers columns
      - affiliations: list of dicts matching staging.raw_affiliations columns
    or None if the work cannot be meaningfully parsed.
    """
    openalex_id = work.get("id", "")
    # Use the short OpenAlex ID (e.g. "W2741809807") as paper_id
    paper_id = openalex_id.replace("https://openalex.org/", "") if openalex_id else ""
    if not paper_id:
        return None

    title = (work.get("title") or "").strip()

    # Reconstruct abstract from inverted index
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

    # Extract topic hierarchy
    hierarchy = extract_topics_hierarchy(work)

    # Map to the staging columns:
    #   fields_of_study_raw  -> OpenAlex "fields" (≈ main academic disciplines)
    #   predicted_fields_raw -> OpenAlex "subfields" (more specific)
    #   main_fields_raw      -> OpenAlex "fields" (same as fields_of_study for
    #                           compatibility with existing pipeline)
    fields_of_study_raw = json.dumps(hierarchy["fields"], ensure_ascii=False)
    predicted_fields_raw = json.dumps(hierarchy["subfields"], ensure_ascii=False)
    main_fields_raw = json.dumps(hierarchy["fields"], ensure_ascii=False)

    # Build PDF URL list
    pdf_urls: List[str] = []
    best_oa = work.get("best_oa_location") or {}
    if isinstance(best_oa, dict):
        pdf_url = best_oa.get("pdf_url")
        if pdf_url:
            pdf_urls.append(pdf_url)
    # Also check primary_location
    primary_loc = work.get("primary_location") or {}
    if isinstance(primary_loc, dict):
        pdf_url = primary_loc.get("pdf_url")
        if pdf_url and pdf_url not in pdf_urls:
            pdf_urls.append(pdf_url)

    pdf_urls_raw = json.dumps(pdf_urls, ensure_ascii=False)

    # Build authors list and affiliations
    authorships = work.get("authorships") or []
    author_names: List[str] = []
    affiliation_rows: List[Dict[str, Any]] = []

    for idx, authorship in enumerate(authorships):
        if not isinstance(authorship, dict):
            continue

        author_obj = authorship.get("author") or {}
        author_name = (author_obj.get("display_name") or "").strip()
        if not author_name:
            author_name = "Unknown"

        author_names.append(author_name)

        # Collect institution names for this author
        institutions = authorship.get("institutions") or []
        inst_names: List[str] = []
        for inst in institutions:
            if isinstance(inst, dict):
                iname = (inst.get("display_name") or "").strip()
                if iname:
                    inst_names.append(iname)

        # If no structured institutions, try raw_affiliation_strings
        if not inst_names:
            raw_aff_strings = authorship.get("raw_affiliation_strings") or []
            if isinstance(raw_aff_strings, list):
                for raw_aff in raw_aff_strings:
                    if isinstance(raw_aff, str) and raw_aff.strip():
                        inst_names.append(raw_aff.strip())

        affiliation_rows.append({
            "paper_id": paper_id,
            "author_name": author_name,
            "affiliations_json": json.dumps(inst_names, ensure_ascii=False),
            "source_json": "openalex_api",
        })

    authors_raw = json.dumps(author_names, ensure_ascii=False)

    paper_row = {
        "paper_id": paper_id,
        "title": title,
        "abstract": abstract,
        "fields_of_study_raw": fields_of_study_raw,
        "predicted_fields_raw": predicted_fields_raw,
        "main_fields_raw": main_fields_raw,
        "pdf_urls_raw": pdf_urls_raw,
        "authors_raw": authors_raw,
        "source_csv": "openalex_api",
    }

    return {
        "paper": paper_row,
        "affiliations": affiliation_rows,
    }


# ---------------------------------------------------------------------------
# Cursor state persistence (for resumable fetching)
# ---------------------------------------------------------------------------

def load_cursor_state(path: str) -> Optional[Dict[str, Any]]:
    """Load cursor state from a JSON file, if it exists."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_cursor_state(path: str, state: Dict[str, Any]) -> None:
    """Persist cursor state to a JSON file."""
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def clear_cursor_state(path: str) -> None:
    """Remove the cursor state file."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_connection(args: argparse.Namespace):
    """Create a psycopg2 connection from CLI args."""
    return psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        dbname=args.dbname,
    )


def apply_schema(conn, schema_path: str) -> None:
    """Apply schema.sql to ensure tables exist."""
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    log.info("Schema applied from %s", schema_path)


def truncate_staging(conn) -> None:
    """Truncate staging tables."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE staging.raw_papers;")
        cur.execute("TRUNCATE TABLE staging.raw_affiliations;")
    conn.commit()
    log.info("Staging tables truncated.")


def insert_papers_batch(conn, papers: List[Dict[str, Any]]) -> int:
    """Insert a batch of paper rows into staging.raw_papers."""
    if not papers:
        return 0

    sql = """
        INSERT INTO staging.raw_papers
            (paper_id, title, abstract, fields_of_study_raw,
             predicted_fields_raw, main_fields_raw, pdf_urls_raw,
             authors_raw, source_csv)
        VALUES
            (%(paper_id)s, %(title)s, %(abstract)s, %(fields_of_study_raw)s,
             %(predicted_fields_raw)s, %(main_fields_raw)s, %(pdf_urls_raw)s,
             %(authors_raw)s, %(source_csv)s)
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, papers, page_size=len(papers))
    conn.commit()
    return len(papers)


def insert_affiliations_batch(conn, affiliations: List[Dict[str, Any]]) -> int:
    """Insert a batch of affiliation rows into staging.raw_affiliations."""
    if not affiliations:
        return 0

    sql = """
        INSERT INTO staging.raw_affiliations
            (paper_id, author_name, affiliations_json, source_json)
        VALUES
            (%(paper_id)s, %(author_name)s, %(affiliations_json)s, %(source_json)s)
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, affiliations, page_size=len(affiliations))
    conn.commit()
    return len(affiliations)


def rebuild_core_tables(conn, refresh_views: bool = True) -> None:
    """Call the stored procedure to rebuild core tables from staging data."""
    log.info("Rebuilding core tables from staging...")
    with conn.cursor() as cur:
        cur.execute("CALL core.rebuild_core_from_staging();")
    conn.commit()
    log.info("Core tables rebuilt.")

    if refresh_views:
        log.info("Refreshing materialized views...")
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW core.mv_subfield_university_ranking;")
            cur.execute("REFRESH MATERIALIZED VIEW core.mv_overall_university_contribution;")
        conn.commit()
        log.info("Materialized views refreshed.")


def print_db_summary(conn) -> None:
    """Print row counts for all core tables."""
    tables = [
        "core.papers",
        "core.authors",
        "core.universities",
        "core.paper_authors",
        "core.paper_subfields",
        "core.paper_mainfields",
    ]
    log.info("Database summary:")
    with conn.cursor() as cur:
        for table in tables:
            cur.execute(f"SELECT count(*) FROM {table}")  # noqa: S608
            count = cur.fetchone()[0]
            log.info("  %-40s %s", table, f"{count:,}")


# ---------------------------------------------------------------------------
# Main fetch loop
# ---------------------------------------------------------------------------

def build_api_params(args: argparse.Namespace) -> Dict[str, str]:
    """Build query parameters for the OpenAlex /works endpoint."""
    # Build filter
    filter_parts = [args.openalex_filter]
    if args.from_year:
        filter_parts.append(f"publication_year:>={args.from_year}")
    if args.to_year:
        filter_parts.append(f"publication_year:<={args.to_year}")
    combined_filter = ",".join(filter_parts)

    params: Dict[str, str] = {
        "filter": combined_filter,
        "per_page": str(min(args.per_page, 200)),
        "cursor": "*",
        # Ask for authorships with institutions and topics
        "select": ",".join([
            "id",
            "title",
            "abstract_inverted_index",
            "authorships",
            "primary_topic",
            "topics",
            "best_oa_location",
            "primary_location",
            "publication_year",
        ]),
    }

    # Polite pool: include email in mailto parameter
    if args.email:
        params["mailto"] = args.email

    # API key
    if args.api_key:
        params["api_key"] = args.api_key

    return params


def fetch_and_load(args: argparse.Namespace) -> Dict[str, int]:
    """
    Main loop: fetch works from OpenAlex, parse, and insert into PostgreSQL.

    Returns a dict of counters.
    """
    counters = {
        "api_pages": 0,
        "works_fetched": 0,
        "papers_inserted": 0,
        "affiliations_inserted": 0,
        "works_skipped": 0,
        "errors": 0,
    }

    # --- Database connection ---
    conn = get_connection(args)
    log.info(
        "Connected to PostgreSQL  %s@%s:%s/%s",
        args.user, args.host, args.port, args.dbname,
    )

    # --- Apply schema ---
    if not args.skip_schema:
        schema_path = str(
            (Path(__file__).resolve().parent.parent / "db" / "schema.sql")
        )
        if os.path.exists(schema_path):
            apply_schema(conn, schema_path)
        else:
            log.warning("schema.sql not found at %s – skipping.", schema_path)

    # --- Truncate staging if requested ---
    if args.truncate_staging:
        truncate_staging(conn)

    # --- Build API params ---
    params = build_api_params(args)

    # --- Resume from saved cursor ---
    cursor_file = args.cursor_file
    if not args.no_resume:
        saved = load_cursor_state(cursor_file)
        if saved and saved.get("filter") == params["filter"]:
            params["cursor"] = saved["cursor"]
            counters["works_fetched"] = saved.get("works_fetched", 0)
            counters["papers_inserted"] = saved.get("papers_inserted", 0)
            counters["affiliations_inserted"] = saved.get("affiliations_inserted", 0)
            log.info(
                "Resuming from saved cursor (already fetched %s works).",
                f"{counters['works_fetched']:,}",
            )
        else:
            if saved:
                log.info("Cursor file exists but filter changed – starting fresh.")
            clear_cursor_state(cursor_file)

    # --- Buffers for batch insert ---
    paper_buffer: List[Dict[str, Any]] = []
    aff_buffer: List[Dict[str, Any]] = []

    session = requests.Session()
    # Set User-Agent header to be polite
    ua = "MetrixaFetcher/1.0"
    if args.email:
        ua += f" (mailto:{args.email})"
    session.headers["User-Agent"] = ua

    total_expected: Optional[int] = None

    log.info("Starting OpenAlex fetch with filter: %s", params["filter"])

    try:
        while True:
            # --- Rate limit ---
            time.sleep(args.request_delay)

            # --- API request ---
            try:
                resp = session.get(WORKS_ENDPOINT, params=params, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as e:
                counters["errors"] += 1
                log.error("API request failed: %s", e)
                if counters["errors"] > 10:
                    log.error("Too many consecutive errors – aborting.")
                    break
                # Back off and retry
                time.sleep(5)
                continue

            data = resp.json()
            counters["api_pages"] += 1

            # On first page, log total count
            meta = data.get("meta", {})
            if total_expected is None:
                total_expected = meta.get("count", 0)
                log.info("Total works matching filter: %s", f"{total_expected:,}")

            results = data.get("results", [])
            if not results:
                log.info("No more results – pagination complete.")
                break

            # --- Parse works ---
            for work in results:
                parsed = parse_work(work)
                if parsed is None:
                    counters["works_skipped"] += 1
                    continue

                counters["works_fetched"] += 1
                paper_buffer.append(parsed["paper"])
                aff_buffer.extend(parsed["affiliations"])

            # --- Flush buffers if large enough ---
            if len(paper_buffer) >= args.batch_size:
                counters["papers_inserted"] += insert_papers_batch(conn, paper_buffer)
                counters["affiliations_inserted"] += insert_affiliations_batch(conn, aff_buffer)
                paper_buffer.clear()
                aff_buffer.clear()

            # --- Log progress ---
            if counters["api_pages"] % 10 == 0:
                pct = ""
                if total_expected and total_expected > 0:
                    pct = f" ({counters['works_fetched'] / total_expected * 100:.1f}%)"
                log.info(
                    "Page %s  |  fetched %s works%s  |  inserted %s papers, %s affiliations",
                    f"{counters['api_pages']:,}",
                    f"{counters['works_fetched']:,}",
                    pct,
                    f"{counters['papers_inserted']:,}",
                    f"{counters['affiliations_inserted']:,}",
                )

            # --- Save cursor for resumability ---
            next_cursor = meta.get("next_cursor")
            if next_cursor:
                params["cursor"] = next_cursor
                save_cursor_state(cursor_file, {
                    "cursor": next_cursor,
                    "filter": params["filter"],
                    "works_fetched": counters["works_fetched"],
                    "papers_inserted": counters["papers_inserted"],
                    "affiliations_inserted": counters["affiliations_inserted"],
                })
            else:
                log.info("No next cursor – reached end of results.")
                break

            # --- Check max_papers limit ---
            if args.max_papers and counters["works_fetched"] >= args.max_papers:
                log.info(
                    "Reached --max-papers limit (%s). Stopping.",
                    f"{args.max_papers:,}",
                )
                break

    except KeyboardInterrupt:
        log.warning("Interrupted by user. Progress has been saved.")

    # --- Flush remaining buffers ---
    if paper_buffer:
        counters["papers_inserted"] += insert_papers_batch(conn, paper_buffer)
        counters["affiliations_inserted"] += insert_affiliations_batch(conn, aff_buffer)
        paper_buffer.clear()
        aff_buffer.clear()

    # --- Rebuild core tables ---
    if not args.skip_rebuild and counters["papers_inserted"] > 0:
        rebuild_core_tables(conn, refresh_views=True)
        print_db_summary(conn)

    # --- Clean up cursor file on successful completion ---
    if (
        not args.max_papers
        or (args.max_papers and counters["works_fetched"] >= args.max_papers)
    ):
        # Only clear if we actually completed (not interrupted)
        if counters["errors"] == 0:
            clear_cursor_state(cursor_file)

    conn.close()
    return counters


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    log.info("=" * 60)
    log.info("OpenAlex → PostgreSQL Loader")
    log.info("=" * 60)
    log.info("  Host:     %s:%s", args.host, args.port)
    log.info("  Database: %s", args.dbname)
    log.info("  User:     %s", args.user)
    log.info("  Filter:   %s", args.openalex_filter)
    if args.from_year:
        log.info("  From year: %s", args.from_year)
    if args.to_year:
        log.info("  To year:   %s", args.to_year)
    if args.max_papers:
        log.info("  Max papers: %s", f"{args.max_papers:,}")
    if args.email:
        log.info("  Email (polite pool): %s", args.email)
    log.info("=" * 60)

    counters = fetch_and_load(args)

    log.info("")
    log.info("=" * 60)
    log.info("FETCH COMPLETE")
    log.info("=" * 60)
    for key, value in sorted(counters.items()):
        log.info("  %-30s %s", key, f"{value:,}")

    return 0 if counters["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
