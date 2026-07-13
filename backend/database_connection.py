"""
Database connection utilities for the Metrixa backend.
Provides connection pooling and query helpers for PostgreSQL database access.
"""

import os
import sys
import time
import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

_pool: Optional[SimpleConnectionPool] = None

def get_db_config() -> Dict[str, Any]:
    """Get database configuration from environment variables."""
    return {
        'host': os.getenv('PGHOST', '127.0.0.1'),
        'port': int(os.getenv('PGPORT', '5432')),
        'user': os.getenv('PGUSER', 'postgres'),
        'password': os.getenv('PGPASSWORD', ''),
        'dbname': os.getenv('PGDATABASE', 'proj_paper'),
        'connect_timeout': 10,
        'options': '-c statement_timeout=300000'
    }

def init_pool(minconn: int = 1, maxconn: int = 10) -> SimpleConnectionPool:
    """Initialize the connection pool."""
    global _pool
    config = get_db_config()
    print(f"Connecting to database at {config['host']}:{config['port']} as {config['user']}...", flush=True)
    sys.stdout.flush()
    _pool = psycopg2.pool.SimpleConnectionPool(
        minconn, maxconn,
        **config
    )
    print("Database connection established!", flush=True)
    sys.stdout.flush()
    return _pool

def get_connection() -> psycopg2.extensions.connection:
    """Get a connection from the pool."""
    global _pool
    if _pool is None:
        init_pool()
    return _pool.getconn()

def put_connection(conn: psycopg2.extensions.connection) -> None:
    """Return a connection to the pool."""
    global _pool
    if _pool and conn:
        _pool.putconn(conn)

@contextmanager
def get_cursor():
    """Context manager for database cursor operations."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            put_connection(conn)

def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None

def fetch_all_papers() -> List[Dict[str, Any]]:
    """Fetch all papers from core.papers table."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT paper_id, title, abstract, fields_of_study, 
                   predicted_fields, main_fields, pdf_urls
            FROM core.papers
            ORDER BY paper_id
        """)
        return cur.fetchall()

def fetch_paper_authors_by_paper_id(paper_id: str) -> List[Dict[str, Any]]:
    """Fetch authors for a specific paper."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT pa.author_order, a.name as author_name, u.name as university_name
            FROM core.paper_authors pa
            JOIN core.authors a ON pa.author_id = a.author_id
            LEFT JOIN core.universities u ON pa.university_id = u.university_id
            WHERE pa.paper_id = %s
            ORDER BY pa.author_order
        """, (paper_id,))
        return cur.fetchall()

def fetch_all_subfields() -> List[str]:
    """Get all unique subfields."""
    with get_cursor() as cur:
        cur.execute("SELECT DISTINCT subfield FROM core.paper_subfields ORDER BY subfield")
        return [row['subfield'] for row in cur.fetchall()]

def fetch_all_mainfields() -> List[str]:
    """Get all unique main fields."""
    with get_cursor() as cur:
        cur.execute("SELECT DISTINCT mainfield FROM core.paper_mainfields ORDER BY mainfield")
        return [row['mainfield'] for row in cur.fetchall()]

def fetch_university_ranking_by_subfield(subfield: str) -> List[Dict[str, Any]]:
    """Get university ranking for a specific subfield from materialized view."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT u.name as university, m.total_contribution, m.rank
            FROM core.mv_subfield_university_ranking m
            JOIN core.universities u ON m.university_id = u.university_id
            WHERE m.subfield = %s
            ORDER BY m.rank
        """, (subfield,))
        return cur.fetchall()

def fetch_overall_university_ranking() -> List[Dict[str, Any]]:
    """Get overall university ranking from materialized view."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT u.name as university, m.total_contribution, m.rank
            FROM core.mv_overall_university_contribution m
            JOIN core.universities u ON m.university_id = u.university_id
            ORDER BY m.rank
        """)
        return cur.fetchall()