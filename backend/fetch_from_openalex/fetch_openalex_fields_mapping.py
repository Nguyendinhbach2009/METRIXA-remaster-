#!/usr/bin/env python3
"""
Fetch field-subfield relationships from OpenAlex API and generate fields.json.

This script queries the OpenAlex /topics endpoint to discover the hierarchical
relationship between main fields and subfields.

Usage:
    python fetch_openalex_fields_mapping.py
    python fetch_openalex_fields_mapping.py --api-key "your-api-key"
    python fetch_openalex_fields_mapping.py --output /path/to/fields.json
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is required.\nInstall it with: pip install requests", file=sys.stderr)
    sys.exit(1)

OPENALEX_API_BASE = "https://api.openalex.org"
TOPICS_ENDPOINT = f"{OPENALEX_API_BASE}/topics"


def fetch_topics_from_openalex(api_key: str = "", per_page: int = 200) -> List[Dict]:
    """Fetch all topics from OpenAlex API."""
    session = requests.Session()
    
    if api_key:
        session.headers["x-api-key"] = api_key
    
    topics = []
    cursor = "*"
    
    while True:
        params = {
            "per_page": per_page,
            "cursor": cursor,
            "select": "id,display_name,domain,field,subfield"
        }
        
        resp = session.get(TOPICS_ENDPOINT, params=params, timeout=30)
        resp.raise_for_status()
        
        data = resp.json()
        results = data.get("results", [])
        topics.extend(results)
        
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor:
            break
        cursor = next_cursor
    
    return topics


def build_subfields_mapping(topics: List[Dict]) -> Dict[str, List[str]]:
    """
    Build subfield-to-mainfield mapping from OpenAlex topics.
    
    Each subfield is assigned to only ONE mainfield (first occurrence).
    
    Returns: {mainfield: [subfield1, subfield2, ...], ...}
    """
    subfield_to_mainfield = {}
    mainfield_subfields = defaultdict(set)
    
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        
        field = topic.get("field") or {}
        subfield = topic.get("subfield") or {}
        
        mainfield_name = field.get("display_name") if isinstance(field, dict) else None
        subfield_name = subfield.get("display_name") if isinstance(subfield, dict) else None
        
        if mainfield_name and subfield_name:
            if subfield_name not in subfield_to_mainfield:
                subfield_to_mainfield[subfield_name] = mainfield_name
                mainfield_subfields[mainfield_name].add(subfield_name)
    
    return {k: sorted(list(v)) for k, v in mainfield_subfields.items()}


def get_all_subfields(topics: List[Dict]) -> List[str]:
    """Get all unique subfields from topics."""
    subfields = set()
    
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        
        subfield = topic.get("subfield") or {}
        subfield_name = subfield.get("display_name") if isinstance(subfield, dict) else None
        
        if subfield_name:
            subfields.add(subfield_name)
    
    return sorted(list(subfields))


def build_fields_json(output_path: str, api_key: str = "") -> None:
    """Build and save fields.json from OpenAlex topics."""
    print("Fetching topics from OpenAlex API...", flush=True)
    topics = fetch_topics_from_openalex(api_key=api_key)
    print(f"  Fetched {len(topics)} topics", flush=True)
    
    subfields_map = build_subfields_mapping(topics)
    all_subfields = get_all_subfields(topics)
    main_fields = sorted(list(subfields_map.keys()))
    
    fields_data = {
        'fields': all_subfields,
        'mainFields': main_fields,
        'subfieldsMap': subfields_map,
        'total': len(all_subfields)
    }
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(fields_data, f, ensure_ascii=False, indent=2)
    
    print(f"Saved fields.json to {output_path}", flush=True)
    print(f"  - {len(all_subfields)} total subfields", flush=True)
    print(f"  - {len(main_fields)} main fields", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Build fields.json from OpenAlex API field-subfield relationships"
    )
    parser.add_argument(
        '--api-key',
        type=str,
        default='',
        help='OpenAlex API key (optional, for higher rate limits)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output path for fields.json (default: ../../src/data/fields.json)'
    )
    parser.add_argument(
        '--per-page',
        type=int,
        default=200,
        help='Results per API page (max 200). Default: 200'
    )
    
    args = parser.parse_args()
    
    output_path = args.output or os.path.join(
        os.path.dirname(__file__), '..', '..', 'src', 'data', 'fields.json'
    )
    
    build_fields_json(output_path, args.api_key)


if __name__ == "__main__":
    main()