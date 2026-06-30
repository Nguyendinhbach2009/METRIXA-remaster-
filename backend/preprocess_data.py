#!/usr/bin/env python3
"""
Preprocess CSV data merged with affiliation data to generate frontend-ready data files
This creates processed data that can be used directly by the frontend without heavy processing
"""

import json
import os
import pandas as pd
import ast
from config import get_all_json_files, get_all_csv_files, get_merge_json_file_path
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

def load_merged_data(csv_path=None, affiliation_path=None):
    """Load data from multiple CSV and JSON files and merge with affiliation data"""
    
    # Load affiliation data from single merge.json file
    affiliation_data = {}
    json_file = get_merge_json_file_path() if affiliation_path is None else affiliation_path
    
    print(f"Loading affiliation data from {json_file}...")
    if os.path.exists(json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            affiliation_data.update(data)
            print(f"  Loaded {len(data)} papers from {os.path.basename(json_file)}")
    else:
        print(f"  Warning: File not found: {json_file}")
    
    print(f"Total affiliation data loaded: {len(affiliation_data)} papers")
    
    # Load CSV data from multiple files
    csv_files = get_all_csv_files() if csv_path is None else [csv_path]
    
    print(f"Loading CSV data from {len(csv_files)} files...")
    df_list = []
    for csv_file in csv_files:
        if os.path.exists(csv_file):
            df_temp = pd.read_csv(csv_file)
            df_list.append(df_temp)
            print(f"  Loaded {len(df_temp)} papers from {os.path.basename(csv_file)}")
        else:
            print(f"  Warning: File not found: {csv_file}")
    
    # Concatenate all dataframes
    if df_list:
        df = pd.concat(df_list, ignore_index=True)
        print(f"Total CSV data loaded: {len(df)} papers")
    else:
        print("Error: No CSV files loaded!")
        return []
    
    papers = []
    matched_count = 0
    skipped_count = 0
    
    for _, row in df.iterrows():
        paper_id = str(row.get('paperId'))
        
        # Skip if paper ID not in affiliation data
        if paper_id not in affiliation_data:
            skipped_count += 1
            continue
        
        matched_count += 1
        affiliation_info = affiliation_data[paper_id]
        
        paper = {
            'paperId': row.get('paperId'),
            'title': row.get('title'),
            'abstract': row.get('abstract'),
            'pdf_urls': row.get('pdf_urls'),
        }
        
        # Parse fieldsOfStudy (main fields from original data)
        fields_of_study = row.get('fieldsOfStudy', '[]')
        if isinstance(fields_of_study, str):
            try:
                paper['api_fieldsOfStudy'] = ast.literal_eval(fields_of_study)
            except:
                paper['api_fieldsOfStudy'] = []
        else:
            paper['api_fieldsOfStudy'] = []
        
        # Parse predicted_fieldsOfStudy (subfields)
        predicted_fields = row.get('predicted_fieldsOfStudy', '[]')
        if isinstance(predicted_fields, str):
            try:
                paper['predicted_fieldsOfStudy'] = ast.literal_eval(predicted_fields)
            except:
                paper['predicted_fieldsOfStudy'] = []
        else:
            paper['predicted_fieldsOfStudy'] = []
        
        # Parse main_fields
        main_fields = row.get('main_fields', '[]')
        if isinstance(main_fields, str):
            try:
                paper['main_fields'] = ast.literal_eval(main_fields)
            except:
                paper['main_fields'] = []
        else:
            paper['main_fields'] = []
        
        # Get author affiliations from affiliation file
        author_affiliations = affiliation_info.get('author_affiliations', [])
        if author_affiliations:
            paper['api_authors'] = []
            for author_info in author_affiliations:
                author_name = author_info.get('author', 'Unknown')
                affiliations = author_info.get('affiliations', [])
                # Use the first affiliation if available
                affiliation = affiliations[0] if affiliations else None
                paper['api_authors'].append({
                    'name': author_name,
                    'affiliation': affiliation
                })
        else:
            # Fallback to CSV authors if no affiliation data
            authors = row.get('authors', '[]')
            if isinstance(authors, str):
                try:
                    author_list = ast.literal_eval(authors)
                    paper['api_authors'] = [{'name': name, 'affiliation': None} for name in author_list]
                except:
                    paper['api_authors'] = []
            else:
                paper['api_authors'] = []
        
        papers.append(paper)
    
    print(f"Matched {matched_count} papers, skipped {skipped_count} papers not in affiliation file")
    return papers

def preprocess_data():
    """Preprocess the data and save frontend-ready files"""
    
    # Load merged data from CSV and affiliation file
    papers = load_merged_data()
    print(f"Total papers to process: {len(papers)}")
    
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
    fields_output_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'fields.json')
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
        main_field_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'data', main_field.replace(' ', '_').replace('/', '_').replace('&', 'and'))
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
    rankings_output_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'rankings')
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
    print("PREPROCESSING COMPLETE!")
    print("="*50)
    print(f"Total fields (including subfields): {len(unique_fields)}")
    print(f"Main fields: {len(main_fields)}")
    print(f"Defined subfields: {len(all_defined_subfields)}")
    print(f"Generated {total_subfields_generated} subfield JSON files across {len(subfields_map)} main field folders")
    print(f"Generated hierarchical field structure with subfields organized in main field folders")
    print(f"Generated {len(main_fields)} mainfield ranking JSON files for improved frontend performance")

if __name__ == "__main__":
    preprocess_data()
