"""
Preprocess data from database and generate frontend-ready JSON files.
"""

import json
import os
import sys
import time
from typing import List, Dict, Any
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_processing.university_ranking_processor import (
    process_university_ranking,
    load_papers_from_db,
)
from database_connection import close_pool

def should_skip_file(filepath: str, skip_existing: bool = True) -> bool:
    """Check if file exists and should be skipped."""
    return skip_existing and os.path.exists(filepath)

def write_json_file(filepath: str, data: dict, skip_existing: bool = True) -> bool:
    """Write JSON file, skipping if it already exists. Returns True if written, False if skipped."""
    if should_skip_file(filepath, skip_existing):
        return False
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True

def preprocess_data() -> None:
    """Preprocess the data and save frontend-ready files."""
    
    print("=" * 60)
    print("PREPROCESSING DATA FROM DATABASE")
    print("=" * 60)
    start_time = time.time()
    
    print("\n[1/5] Loading papers from database...")
    sys.stdout.flush()
    papers = load_papers_from_db()
    print(f"      Loaded {len(papers)} papers")
    sys.stdout.flush()
    
    print("\n[2/5] Loading subfields mapping from fields.json...")
    sys.stdout.flush()
    fields_output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'data', 'fields.json')
    
    try:
        with open(fields_output_path, 'r', encoding='utf-8') as f:
            fields_data = json.load(f)
    except Exception as e:
        print(f"      Warning: Could not load fields.json: {e}")
        print("      Run 'fetch_openalex_fields_mapping.py' first to generate it.")
        return
    
    subfields_map = fields_data.get('subfieldsMap', {})
    all_subfields = fields_data.get('fields', [])
    main_fields = fields_data.get('mainFields', [])
    
    print(f"      Loaded mapping for {len(subfields_map)} main fields")
    print(f"      Found {len(all_subfields)} total subfields")
    sys.stdout.flush()
    
    unique_fields = all_subfields
    
    print("\n[3/5] Generating field structure and rankings...")
    sys.stdout.flush()
    
    data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'data')
    rankings_output_dir = os.path.join(data_dir, 'rankings')
    os.makedirs(rankings_output_dir, exist_ok=True)
    
    total_subfields_generated = 0
    mainfield_contrib_maps = {}
    mainfield_combined_rankings = {}
    mainfield_authors_by_uni = {}
    
    for main_field, subfields in subfields_map.items():
        main_field_filename = main_field.replace(' ', '_').replace('/', '_').replace('&', 'and').lower()
        main_field_dir = os.path.join(rankings_output_dir, main_field_filename)
        os.makedirs(main_field_dir, exist_ok=True)
        
        mainfield_contrib_maps[main_field] = defaultdict(lambda: defaultdict(float))
        mainfield_universities = {}
        mainfield_authors_by_uni[main_field] = defaultdict(lambda: defaultdict(float))
        
        for subfield in subfields:
            subfield_result = process_university_ranking(papers, [subfield], target_subfield=subfield)
            subfield_filename = subfield.replace(' ', '_').replace('/', '_').replace('&', 'and').replace('–', '-').replace('—', '-').lower()
            subfield_output_path = os.path.join(main_field_dir, f'{subfield_filename}.json')
            
            # Limit authors to 100 per university in subfield files
            limited_subfield_authors = {}
            for uni, authors in subfield_result.get('authorsByUniversity', {}).items():
                limited_subfield_authors[uni] = authors[:100]
            
            ranking_data = {
                'ranking': subfield_result.get('ranking', []),
                'authorsByUniversity': limited_subfield_authors,
                'totalPapers': subfield_result.get('totalPapers', 0)
            }
            
            if write_json_file(subfield_output_path, ranking_data):
                total_subfields_generated += 1
            
            for uni, contrib_dict in subfield_result.get('uniFieldContrib', {}).items():
                for sf, contrib in contrib_dict.items():
                    mainfield_contrib_maps[main_field][uni][sf] += contrib
                    if uni not in mainfield_universities:
                        mainfield_universities[uni] = 0
                    mainfield_universities[uni] += contrib
            
            for uni, authors in subfield_result.get('authorsByUniversity', {}).items():
                for author_data in authors:
                    author_name = author_data.get('author')
                    author_contrib = author_data.get('contribution', 0)
                    if author_name and author_contrib > 0:
                        mainfield_authors_by_uni[main_field][uni][author_name] += author_contrib
        
        mainfield_combined_rankings[main_field] = [
            {'university': uni, 'totalContribution': contrib, 'rank': i + 1}
            for i, (uni, contrib) in enumerate(sorted(mainfield_universities.items(), key=lambda x: x[1], reverse=True))
        ]
        
        formatted_authors = {}
        for uni, authors in mainfield_authors_by_uni[main_field].items():
            total = sum(authors.values())
            formatted_authors[uni] = [
                {'author': author, 'contribution': contrib, 'percent': contrib / total if total > 0 else 0}
                for author, contrib in sorted(authors.items(), key=lambda x: x[1], reverse=True)[:100]
            ]
        
        mainfield_json_path = os.path.join(data_dir, f'{main_field_filename}.json')
        mainfield_json_data = {
            'mainField': main_field,
            'ranking': mainfield_combined_rankings[main_field],
            'subfields': subfields,
            'totalSubfields': len(subfields),
            'authorsByUniversity': formatted_authors,
            'uniFieldContrib': dict(mainfield_contrib_maps[main_field])
        }
        write_json_file(mainfield_json_path, mainfield_json_data)
        
        uni_field_contrib_path = os.path.join(main_field_dir, 'uniFieldContrib.json')
        write_json_file(uni_field_contrib_path, dict(mainfield_contrib_maps[main_field]))
        
        print(f"      Generated {len(subfields)} files for '{main_field}'")
        sys.stdout.flush()
    
    print("\n[4/5] Generating overall rankings...")
    sys.stdout.flush()
    
    overall_combined = {}
    overall_uni_field_contrib = {}
    overall_authors_by_uni = defaultdict(lambda: defaultdict(float))
    
    for main_field, ranking_list in mainfield_combined_rankings.items():
        for uni_data in ranking_list:
            uni = uni_data['university']
            overall_combined[uni] = overall_combined.get(uni, 0) + uni_data['totalContribution']
    
    for main_field, contrib_map in mainfield_contrib_maps.items():
        for uni, fields in contrib_map.items():
            if uni not in overall_uni_field_contrib:
                overall_uni_field_contrib[uni] = {}
            for sf, contrib in fields.items():
                overall_uni_field_contrib[uni][sf] = overall_uni_field_contrib[uni].get(sf, 0) + contrib
    
    for main_field, authors_map in mainfield_authors_by_uni.items():
        for uni, authors in authors_map.items():
            for author_name, contrib in authors.items():
                overall_authors_by_uni[uni][author_name] += contrib
    
    formatted_overall_authors = {}
    for uni, authors in overall_authors_by_uni.items():
        total = sum(authors.values())
        formatted_overall_authors[uni] = [
            {'author': author, 'contribution': contrib, 'percent': contrib / total if total > 0 else 0}
            for author, contrib in sorted(authors.items(), key=lambda x: x[1], reverse=True)[:100]
        ]
    
    overall_ranking_list = sorted(
        [{'university': uni, 'totalContribution': contrib, 'rank': i + 1} 
         for i, (uni, contrib) in enumerate(sorted(overall_combined.items(), key=lambda x: x[1], reverse=True))],
        key=lambda x: x['rank']
    )
    
    overall_rankings_path = os.path.join(rankings_output_dir, 'overall_rankings.json')
    overall_rankings_data = {
        'ranking': overall_ranking_list,
        'authorsByUniversity': formatted_overall_authors,
        'uniFieldContrib': overall_uni_field_contrib,
        'totalSubfields': len(all_subfields)
    }
    write_json_file(overall_rankings_path, overall_rankings_data)
    
    print(f"      Generated overall rankings for {len(overall_ranking_list)} universities")
    sys.stdout.flush()
    
    print(f"\n[5/5] Done!")
    sys.stdout.flush()
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("PREPROCESSING COMPLETE!")
    print("=" * 60)
    print(f"Time elapsed: {elapsed:.1f}s")
    print(f"  - {len(unique_fields)} unique fields")
    print(f"  - {len(main_fields)} main fields")
    print(f"  - {total_subfields_generated} subfield JSON files")
    print(f"  - {len(main_fields)} mainfield combined JSON files")
    
    close_pool()

if __name__ == "__main__":
    preprocess_data()