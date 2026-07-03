#!/usr/bin/env python3
"""
Export data from PostgreSQL database to frontend-ready JSON files.
This replaces preprocess_data.py to work with the new PostgreSQL pipeline.
"""

import json
import os
import argparse
import sys
from collections import defaultdict

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

# Import the existing processing logic
from university_ranking_processor import (
    process_university_ranking, 
    get_unique_fields,
    load_subfields_mapping,
    get_all_subfields
)
from university_ranking_by_mainfield import (
    generate_individual_mainfield_files,
    save_mainfield_rankings
)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export data from PostgreSQL and generate frontend JSON files."
    )
    parser.add_argument("--host", default=os.getenv("PGHOST", "127.0.0.1"))
    parser.add_argument("--port", default=os.getenv("PGPORT", "5432"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "proj_paper"))
    parser.add_argument("--password", default=os.getenv("PGPASSWORD", ""))
    return parser.parse_args()

def load_data_from_postgres(args):
    """Load and format data from PostgreSQL to match what the processing functions expect"""
    print(f"Connecting to PostgreSQL database {args.dbname} at {args.host}:{args.port}...")
    
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        dbname=args.dbname,
    )
    
    papers_dict = {}
    
    # 1. Load papers
    print("Loading papers from database...")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT 
                paper_id, title, abstract, 
                fields_of_study, predicted_fields, main_fields, pdf_urls
            FROM core.papers
        """)
        
        for row in cur:
            paper_id = str(row['paper_id'])
            papers_dict[paper_id] = {
                'paperId': paper_id,
                'title': row['title'],
                'abstract': row['abstract'],
                # The database stores these as JSONB, which psycopg2 automatically parses into Python lists/dicts
                'api_fieldsOfStudy': row['fields_of_study'] or [],
                'predicted_fieldsOfStudy': row['predicted_fields'] or [],
                'main_fields': row['main_fields'] or [],
                'pdf_urls': row['pdf_urls'] or [],
                'api_authors': []
            }
            
    # 2. Load authors and affiliations
    print("Loading author affiliations from database...")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT 
                pa.paper_id, a.name as author_name, u.name as university_name
            FROM core.paper_authors pa
            JOIN core.authors a ON pa.author_id = a.author_id
            JOIN core.universities u ON pa.university_id = u.university_id
            ORDER BY pa.paper_id, pa.author_order
        """)
        
        for row in cur:
            paper_id = str(row['paper_id'])
            if paper_id in papers_dict:
                papers_dict[paper_id]['api_authors'].append({
                    'name': row['author_name'],
                    'affiliation': row['university_name']
                })
                
    conn.close()
    
    # Convert dictionary to list
    papers_list = list(papers_dict.values())
    print(f"Loaded {len(papers_list)} papers with affiliations from database")
    return papers_list

def export_frontend_data(args):
    """Main export function that runs the preprocessing logic on DB data"""
    # Load data from PostgreSQL
    papers = load_data_from_postgres(args)
    
    if not papers:
        print("No papers found in database! Have you run fetch_openalex.py yet?")
        return
        
    # Load subfields mapping from CSV
    subfields_map = load_subfields_mapping()
    print(f"Loaded subfields mapping for {len(subfields_map)} main fields")
    
    # Get all unique fields (including subfields from papers)
    unique_fields = get_unique_fields(papers)
    print(f"Found {len(unique_fields)} unique fields in papers")
    
    # Get all defined subfields from CSV
    all_defined_subfields = get_all_subfields(subfields_map)
    print(f"Found {len(all_defined_subfields)} defined subfields in CSV")
    
    # Combine main fields and subfields
    main_fields = list(subfields_map.keys())
    
    # Save unique fields to a JSON file (all fields found in papers)
    src_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'data')
    fields_output_path = os.path.join(src_dir, 'fields.json')
    os.makedirs(os.path.dirname(fields_output_path), exist_ok=True)
    
    with open(fields_output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'fields': unique_fields,
            'mainFields': main_fields,
            'subfieldsMap': subfields_map,
            'total': len(unique_fields)
        }, f, ensure_ascii=False, indent=2)
    
    print(f"Saved fields to {fields_output_path}")
    
    # Generate hierarchical structure: main field folders with subfield JSON files
    print(f"\nGenerating hierarchical field structure...")
    total_subfields_generated = 0
    
    for main_field, subfields in subfields_map.items():
        # Create folder for main field
        main_field_dir = os.path.join(src_dir, main_field.replace(' ', '_').replace('/', '_').replace('&', 'and'))
        os.makedirs(main_field_dir, exist_ok=True)
        
        # Generate JSON file for each subfield
        for subfield in subfields:
            subfield_result = process_university_ranking(papers, [subfield], target_subfield=subfield)
            subfield_filename = subfield.replace(' ', '_').replace('/', '_').replace('&', 'and').replace('–', '-').replace('—', '-').lower()
            subfield_output_path = os.path.join(main_field_dir, f'{subfield_filename}.json')
            
            with open(subfield_output_path, 'w', encoding='utf-8') as f:
                json.dump(subfield_result, f, ensure_ascii=False, indent=2)
            
            total_subfields_generated += 1
        
        print(f"  Generated {len(subfields)} subfield files for {main_field}")
    
    print(f"\nGenerated {total_subfields_generated} subfield JSON files across {len(subfields_map)} main field folders")
    
    # Generate mainfield rankings for better frontend performance
    print(f"\nGenerating mainfield rankings for improved frontend performance...")
    rankings_output_dir = os.path.join(src_dir, 'rankings')
    os.makedirs(rankings_output_dir, exist_ok=True)
    
    # Generate individual mainfield ranking files
    generate_individual_mainfield_files(papers, rankings_output_dir)
    
    # Also generate a combined overall ranking file
    from university_ranking_by_mainfield import generate_mainfield_rankings_for_all_mainfields
    overall_rankings = generate_mainfield_rankings_for_all_mainfields(papers)
    overall_rankings_path = os.path.join(rankings_output_dir, 'overall_rankings.json')
    save_mainfield_rankings(overall_rankings, overall_rankings_path)
    
    print(f"Generated mainfield rankings in {rankings_output_dir}")
    
    print("\n" + "="*50)
    print("FRONTEND DATA EXPORT COMPLETE!")
    print("="*50)
    print("You can now run 'npm run dev' to see the updated rankings in the frontend.")

if __name__ == "__main__":
    args = parse_args()
    export_frontend_data(args)
