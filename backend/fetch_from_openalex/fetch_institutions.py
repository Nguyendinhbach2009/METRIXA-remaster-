#!/usr/bin/env python3
"""
Fetch institutions from the OpenAlex API and save to universities.json.

This script queries the OpenAlex /institutions endpoint for institutions
located in Vietnam (country_code:VN) and saves the results to a JSON file.

Usage:
    python fetch_institutions.py
    python fetch_institutions.py --api-key "your-api-key"
    python fetch_institutions.py --output /path/to/universities.json
"""

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is required.\nInstall it with: pip install requests", file=sys.stderr)
    sys.exit(1)

OPENALEX_API_BASE = "https://api.openalex.org"
INSTITUTIONS_ENDPOINT = f"{OPENALEX_API_BASE}/institutions"


def fetch_institutions_from_openalex(
    api_key: str = "",
    per_page: int = 200,
    country_code: str = "VN"
) -> List[Dict[str, Any]]:
    """Fetch all institutions from OpenAlex API filtered by country code."""
    session = requests.Session()
    
    if api_key:
        session.headers["x-api-key"] = api_key
    
    institutions = []
    cursor = "*"
    
    while True:
        params = {
            "filter": f"country_code:{country_code}",
            "per_page": per_page,
            "cursor": cursor
        }
        
        resp = session.get(INSTITUTIONS_ENDPOINT, params=params, timeout=30)
        resp.raise_for_status()
        
        data = resp.json()
        results = data.get("results", [])
        institutions.extend(results)
        
        meta = data.get("meta", {})
        total_expected = meta.get("count", 0)
        
        next_cursor = meta.get("next_cursor")
        if not next_cursor:
            log.info("Pagination complete. Total: %d institutions", len(institutions))
            break
        
        cursor = next_cursor
        log.info("  Fetched %d institutions (total: %d)...", len(institutions), total_expected)
    
    return institutions


def transform_institution(inst: Dict[str, Any]) -> Dict[str, Any]:
    """Transform OpenAlex institution object to simplified format."""
    openalex_id = inst.get("id", "")
    short_id = openalex_id.replace("https://openalex.org/", "") if openalex_id else ""
    
    display_name = inst.get("display_name", "") or ""
    hostname = inst.get("hostname", "") or ""
    website = inst.get("website", "") or ""
    inst_type = inst.get("type", "") or ""
    established = inst.get("established_date", "") or ""
    
    aliases = inst.get("aliases", []) or []
    acronyms = inst.get("acronyms", []) or []
    
    return {
        "id": short_id,
        "openalex_id": openalex_id,
        "display_name": display_name,
        "hostname": hostname,
        "website": website,
        "type": inst_type,
        "established_date": established,
        "aliases": aliases if isinstance(aliases, list) else [],
        "acronyms": acronyms if isinstance(acronyms, list) else [],
    }


def save_institutions_to_json(
    output_path: str,
    api_key: str = ""
) -> None:
    """Fetch institutions from OpenAlex and save to JSON file."""
    log.info("Fetching institutions from OpenAlex API...")
    
    raw_institutions = fetch_institutions_from_openalex(
        api_key=api_key,
        per_page=200,
        country_code="VN"
    )
    
    transformed = [transform_institution(inst) for inst in raw_institutions]
    transformed.sort(key=lambda x: x.get("display_name", "").lower())
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transformed, f, ensure_ascii=False, indent=2)
    
    log.info("Saved institutions to %s", output_path)
    log.info("  - %d institutions saved", len(transformed))


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Vietnamese institutions from OpenAlex API and save to JSON"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="",
        help="OpenAlex API key (optional, for higher rate limits)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for universities.json (default: ../src/data/universities.json)"
    )
    parser.add_argument(
        "--country-code",
        type=str,
        default="VN",
        help="Country code to filter institutions by. Default: VN"
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=200,
        help="Results per API page (max 200). Default: 200"
    )
    
    args = parser.parse_args()
    
    output_path = args.output or os.path.join(
        os.path.dirname(__file__), "..", "..", "src", "data", "universities.json"
    )
    
    save_institutions_to_json(
        output_path=output_path,
        api_key=args.api_key
    )


if __name__ == "__main__":
    main()