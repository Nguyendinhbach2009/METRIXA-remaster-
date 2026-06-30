#!/usr/bin/env python3
r"""
Load project paper data into PostgreSQL.

Pipeline:
1) Build staging CSV files from shard CSV data and merge.json.
2) Bulk load staging tables with psql \copy.
3) Rebuild core tables and refresh ranking materialized views.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from glob import glob
from pathlib import Path
from typing import Dict, Iterable, List


RAW_PAPERS_COLUMNS = [
    "paper_id",
    "title",
    "abstract",
    "fields_of_study_raw",
    "predicted_fields_raw",
    "main_fields_raw",
    "pdf_urls_raw",
    "authors_raw",
    "source_csv",
]

RAW_AFFILIATIONS_COLUMNS = [
    "paper_id",
    "author_name",
    "affiliations_json",
    "source_json",
]


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve()
    website_root = here.parents[1]
    project_root = here.parents[2]

    parser = argparse.ArgumentParser(
        description="Migrate shard CSV + merge.json into PostgreSQL core schema."
    )
    parser.add_argument("--host", default=os.getenv("PGHOST", "127.0.0.1"))
    parser.add_argument("--port", default=os.getenv("PGPORT", "5432"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "proj_paper"))
    parser.add_argument("--password", default=os.getenv("PGPASSWORD"))

    parser.add_argument(
        "--project-root",
        default=str(project_root),
        help="Project root containing duck/ and duy/ directories.",
    )
    parser.add_argument(
        "--schema-file",
        default=str(website_root / "db" / "schema.sql"),
        help="Path to schema.sql.",
    )
    parser.add_argument(
        "--csv-glob",
        default="duck/output_shard/*/result_many_prompts_deleted_empty.csv",
        help="Glob (relative to project root) for shard CSV files.",
    )
    parser.add_argument(
        "--merge-json",
        default="duy/extracted_combined_merged/merge.json",
        help="Path (relative to project root) to merged affiliations JSON.",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Do not apply schema.sql before migration.",
    )
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Do not refresh materialized views after rebuild.",
    )
    parser.add_argument(
        "--keep-temp-files",
        action="store_true",
        help="Keep generated temporary CSV files for inspection.",
    )
    return parser.parse_args()


def psql_env(password: str | None) -> Dict[str, str]:
    env = dict(os.environ)
    if password:
        env["PGPASSWORD"] = password
    return env


def run_psql(
    *,
    host: str,
    port: str,
    user: str,
    dbname: str,
    password: str | None,
    sql: str | None = None,
    sql_file: str | None = None,
    capture_output: bool = False,
    extra_args: List[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if sql is None and sql_file is None:
        raise ValueError("Either sql or sql_file must be provided.")

    cmd = [
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        host,
        "-p",
        str(port),
        "-U",
        user,
        "-d",
        dbname,
    ]
    if extra_args:
        cmd.extend(extra_args)

    if sql_file is not None:
        cmd.extend(["-f", sql_file])
    else:
        cmd.extend(["-c", sql or ""])

    return subprocess.run(
        cmd,
        check=True,
        text=True,
        env=psql_env(password),
        capture_output=capture_output,
    )


def set_csv_field_limit_max() -> None:
    """
    Increase Python csv parser field limit to the largest supported value.
    """
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10
            if limit <= 0:
                raise


def iter_csv_rows(csv_paths: Iterable[Path]) -> Iterable[Dict[str, str]]:
    for csv_path in csv_paths:
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["_source_csv"] = str(csv_path)
                yield row


def build_staging_csv_files(
    *,
    csv_paths: List[Path],
    merge_json_path: Path,
    raw_papers_csv_path: Path,
    raw_aff_csv_path: Path,
) -> Dict[str, int]:
    counts = {
        "csv_files": len(csv_paths),
        "staging_raw_papers_rows": 0,
        "staging_raw_affiliations_rows": 0,
        "merge_papers": 0,
    }

    with raw_papers_csv_path.open("w", encoding="utf-8", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=RAW_PAPERS_COLUMNS)
        writer.writeheader()

        for row in iter_csv_rows(csv_paths):
            paper_id = str(row.get("paperId") or "").strip()
            if not paper_id:
                continue

            writer.writerow(
                {
                    "paper_id": paper_id,
                    "title": row.get("title") or "",
                    "abstract": row.get("abstract") or "",
                    "fields_of_study_raw": row.get("fieldsOfStudy") or "",
                    "predicted_fields_raw": row.get("predicted_fieldsOfStudy") or "",
                    "main_fields_raw": row.get("main_fields") or "",
                    "pdf_urls_raw": row.get("pdf_urls") or "",
                    "authors_raw": row.get("authors") or "",
                    "source_csv": row.get("_source_csv") or "",
                }
            )
            counts["staging_raw_papers_rows"] += 1

    with merge_json_path.open("r", encoding="utf-8") as f:
        merged = json.load(f)
    counts["merge_papers"] = len(merged)

    with raw_aff_csv_path.open("w", encoding="utf-8", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=RAW_AFFILIATIONS_COLUMNS)
        writer.writeheader()

        for paper_id, payload in merged.items():
            author_affiliations = payload.get("author_affiliations") or []
            if not isinstance(author_affiliations, list):
                continue

            for item in author_affiliations:
                if not isinstance(item, dict):
                    continue
                author_name = (item.get("author") or "").strip()
                affiliations = item.get("affiliations")
                if not isinstance(affiliations, list):
                    affiliations = []

                writer.writerow(
                    {
                        "paper_id": str(paper_id),
                        "author_name": author_name,
                        "affiliations_json": json.dumps(affiliations, ensure_ascii=False),
                        "source_json": str(merge_json_path),
                    }
                )
                counts["staging_raw_affiliations_rows"] += 1

    return counts


def sql_quote_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "''")


def copy_csv_into_staging(
    *,
    host: str,
    port: str,
    user: str,
    dbname: str,
    password: str | None,
    raw_papers_csv_path: Path,
    raw_aff_csv_path: Path,
) -> None:
    run_psql(
        host=host,
        port=port,
        user=user,
        dbname=dbname,
        password=password,
        sql="""
            TRUNCATE TABLE staging.raw_papers;
            TRUNCATE TABLE staging.raw_affiliations;
        """,
    )

    papers_path = sql_quote_literal(str(raw_papers_csv_path.resolve()))
    aff_path = sql_quote_literal(str(raw_aff_csv_path.resolve()))

    run_psql(
        host=host,
        port=port,
        user=user,
        dbname=dbname,
        password=password,
        sql=(
            "\\copy staging.raw_papers ("
            "paper_id, title, abstract, fields_of_study_raw, predicted_fields_raw, "
            "main_fields_raw, pdf_urls_raw, authors_raw, source_csv"
            f") FROM '{papers_path}' WITH (FORMAT csv, HEADER true)"
        ),
    )

    run_psql(
        host=host,
        port=port,
        user=user,
        dbname=dbname,
        password=password,
        sql=(
            "\\copy staging.raw_affiliations ("
            "paper_id, author_name, affiliations_json, source_json"
            f") FROM '{aff_path}' WITH (FORMAT csv, HEADER true)"
        ),
    )


def rebuild_core(
    *,
    host: str,
    port: str,
    user: str,
    dbname: str,
    password: str | None,
    refresh_views: bool,
) -> None:
    run_psql(
        host=host,
        port=port,
        user=user,
        dbname=dbname,
        password=password,
        sql="CALL core.rebuild_core_from_staging();",
    )
    if refresh_views:
        run_psql(
            host=host,
            port=port,
            user=user,
            dbname=dbname,
            password=password,
            sql="""
                REFRESH MATERIALIZED VIEW core.mv_subfield_university_ranking;
                REFRESH MATERIALIZED VIEW core.mv_overall_university_contribution;
            """,
        )


def print_summary(
    *,
    host: str,
    port: str,
    user: str,
    dbname: str,
    password: str | None,
    local_counts: Dict[str, int],
) -> None:
    sql = """
        SELECT 'core.papers', count(*)::text FROM core.papers
        UNION ALL
        SELECT 'core.authors', count(*)::text FROM core.authors
        UNION ALL
        SELECT 'core.universities', count(*)::text FROM core.universities
        UNION ALL
        SELECT 'core.paper_authors', count(*)::text FROM core.paper_authors
        UNION ALL
        SELECT 'core.paper_subfields', count(*)::text FROM core.paper_subfields
        UNION ALL
        SELECT 'core.paper_mainfields', count(*)::text FROM core.paper_mainfields
        UNION ALL
        SELECT 'core.mv_subfield_university_ranking', count(*)::text FROM core.mv_subfield_university_ranking
        UNION ALL
        SELECT 'core.mv_overall_university_contribution', count(*)::text FROM core.mv_overall_university_contribution
        ORDER BY 1;
    """
    result = run_psql(
        host=host,
        port=port,
        user=user,
        dbname=dbname,
        password=password,
        sql=sql,
        capture_output=True,
        extra_args=["-A", "-t"],
    )

    print("\nLocal processing counts:")
    for key in sorted(local_counts.keys()):
        print(f"  {key}: {local_counts[key]}")

    print("\nDatabase row counts:")
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        table_name, count = line.split("|", 1)
        print(f"  {table_name}: {count}")


def main() -> int:
    args = parse_args()

    project_root = Path(args.project_root).resolve()
    schema_file = Path(args.schema_file).resolve()
    merge_json_path = (project_root / args.merge_json).resolve()
    csv_pattern = str((project_root / args.csv_glob).resolve())

    csv_paths = [Path(p) for p in sorted(glob(csv_pattern))]
    if not csv_paths:
        print(f"No CSV files found with glob: {csv_pattern}", file=sys.stderr)
        return 1

    if not merge_json_path.exists():
        print(f"merge.json not found: {merge_json_path}", file=sys.stderr)
        return 1

    if not schema_file.exists():
        print(f"schema.sql not found: {schema_file}", file=sys.stderr)
        return 1

    set_csv_field_limit_max()

    print("Starting PostgreSQL migration.")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  User: {args.user}")
    print(f"  Database: {args.dbname}")
    print(f"  Project root: {project_root}")
    print(f"  CSV files: {len(csv_paths)}")
    print(f"  merge.json: {merge_json_path}")

    if not args.skip_schema:
        print("\nApplying schema...")
        run_psql(
            host=args.host,
            port=args.port,
            user=args.user,
            dbname=args.dbname,
            password=args.password,
            sql_file=str(schema_file),
        )

    tmpdir = Path(tempfile.mkdtemp(prefix="proj_paper_migrate_"))
    raw_papers_csv_path = tmpdir / "staging_raw_papers.csv"
    raw_aff_csv_path = tmpdir / "staging_raw_affiliations.csv"

    try:
        print("\nBuilding staging CSV files...")
        local_counts = build_staging_csv_files(
            csv_paths=csv_paths,
            merge_json_path=merge_json_path,
            raw_papers_csv_path=raw_papers_csv_path,
            raw_aff_csv_path=raw_aff_csv_path,
        )

        print("\nLoading staging tables with \\copy...")
        copy_csv_into_staging(
            host=args.host,
            port=args.port,
            user=args.user,
            dbname=args.dbname,
            password=args.password,
            raw_papers_csv_path=raw_papers_csv_path,
            raw_aff_csv_path=raw_aff_csv_path,
        )

        print("\nRebuilding core tables and ranking views...")
        rebuild_core(
            host=args.host,
            port=args.port,
            user=args.user,
            dbname=args.dbname,
            password=args.password,
            refresh_views=not args.skip_refresh,
        )

        print_summary(
            host=args.host,
            port=args.port,
            user=args.user,
            dbname=args.dbname,
            password=args.password,
            local_counts=local_counts,
        )
        print("\nMigration completed.")
    finally:
        if args.keep_temp_files:
            print(f"\nKept temp files in: {tmpdir}")
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
