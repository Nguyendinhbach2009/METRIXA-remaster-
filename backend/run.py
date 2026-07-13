#!/usr/bin/env python3
"""
Main data processing script for Metrixa backend.
Reads data from PostgreSQL database and generates frontend-ready JSON files.

Usage:
    python run.py                    # Run full pipeline (uses env vars for DB)
    python run.py --password "xxx"   # Run with explicit password
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    parser = argparse.ArgumentParser(
        description="Process database data and generate frontend JSON files"
    )
    parser.add_argument(
        '--password',
        type=str,
        default='',
        help='Database password (default: use PGPASSWORD env var)'
    )
    
    args = parser.parse_args()
    
    if args.password:
        os.environ['PGPASSWORD'] = args.password
    
    print("=" * 60, flush=True)
    print("METRIXA DATA PROCESSING PIPELINE", flush=True)
    print("=" * 60, flush=True)
    print(f"Database: {os.getenv('PGDATABASE', 'proj_paper')}", flush=True)
    print(f"Host: {os.getenv('PGHOST', '127.0.0.1')}", flush=True)
    print(f"User: {os.getenv('PGUSER', 'postgres')}", flush=True)
    print("=" * 60, flush=True)
    print()
    
    start_time = time.time()
    
    print("[Step 1/1] Generating university rankings...", flush=True)
    print("-" * 40, flush=True)
    sys.stdout.flush()
    from data_processing.preprocess_data import preprocess_data
    preprocess_data()
    print("Step 1 complete!", flush=True)
    print()
    
    elapsed = time.time() - start_time
    
    print("=" * 60, flush=True)
    print("DATA PROCESSING COMPLETE!", flush=True)
    print("=" * 60, flush=True)
    print(f"\nTotal time: {elapsed:.1f} seconds", flush=True)
    print("\nGenerated files:", flush=True)
    print("  - src/data/fields.json", flush=True)
    print("  - src/data/<MainField>.json (combined main field rankings)", flush=True)
    print("  - src/data/rankings/<MainField>/<subfield>.json", flush=True)
    print("  - src/data/rankings/<MainField>/uniFieldContrib.json", flush=True)
    print("  - src/data/rankings/overall_rankings.json", flush=True)
    print()
    print("Run the frontend with: npm run dev", flush=True)

if __name__ == "__main__":
    main()