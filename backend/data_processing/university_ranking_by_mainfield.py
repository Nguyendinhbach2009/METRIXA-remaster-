"""
University ranking by main field processor.
Generates per-mainfield and overall ranking JSON files from database data.
"""

import json
import os
from typing import List, Dict, Any
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_processing.university_ranking_processor import (
    process_university_ranking,
)

def calculate_mainfield_rankings(
    papers: List[Dict[str, Any]], 
    selected_fields: List[str],
    subfields_map: Dict[str, List[str]],
    target_mainfield: str = None
) -> Dict[str, Any]:
    """
    Calculate university rankings by main field for the selected subfields.
    
    Args:
        papers: List of paper objects
        selected_fields: List of subfields to analyze
        subfields_map: Mapping of main fields to their subfields
        target_mainfield: Optional specific main field to calculate for
    
    Returns:
        Dict containing mainfield rankings for all universities in the selected fields
    """
    selected_set = set(selected_fields)
    main_fields_to_process = [target_mainfield] if target_mainfield else list(subfields_map.keys())
    
    uni_mainfield_contrib = {}
    
    for main_field in main_fields_to_process:
        uni_mainfield_contrib[main_field] = {}
        subfields = subfields_map.get(main_field, [])
        
        for subfield in subfields:
            if subfield in selected_set:
                subfield_result = process_university_ranking(papers, [subfield], target_subfield=subfield)
                
                for uni_data in subfield_result.get('ranking', []):
                    uni_name = uni_data['university']
                    contrib = uni_data['totalContribution']
                    
                    if uni_name not in uni_mainfield_contrib[main_field]:
                        uni_mainfield_contrib[main_field][uni_name] = 0
                    
                    uni_mainfield_contrib[main_field][uni_name] += contrib
    
    mainfield_rankings = {}
    
    for main_field, uni_contribs in uni_mainfield_contrib.items():
        ranking_list = [
            {
                'university': uni,
                'totalContribution': contrib,
                'paperCount': 0,
                'authorCount': 0
            }
            for uni, contrib in uni_contribs.items()
        ]
        
        ranking_list.sort(key=lambda x: x['totalContribution'], reverse=True)
        
        for i, uni_data in enumerate(ranking_list):
            uni_data['rank'] = i + 1
        
        mainfield_rankings[main_field] = ranking_list
    
    return {
        'mainfieldRankings': mainfield_rankings,
        'selectedFields': selected_fields,
        'mainFields': list(main_fields_to_process)
    }

def generate_mainfield_rankings_for_all_mainfields(
    papers: List[Dict[str, Any]],
    subfields_map: Dict[str, List[str]]
) -> Dict[str, Any]:
    """
    Generate mainfield rankings for all main fields.
    
    Args:
        papers: List of paper objects
        subfields_map: Mapping of main fields to their subfields
    
    Returns:
        Dict containing all mainfield rankings
    """
    main_fields = list(subfields_map.keys())
    
    all_rankings = {}
    
    for main_field in main_fields:
        subfields = subfields_map.get(main_field, [])
        main_field_ranking = calculate_mainfield_rankings(papers, subfields, subfields_map, target_mainfield=main_field)
        all_rankings[main_field] = main_field_ranking
    
    return {
        'allMainfieldRankings': all_rankings,
        'totalMainFields': len(main_fields),
        'mainFields': main_fields
    }

def calculate_subfield_rankings_within_mainfield(
    papers: List[Dict[str, Any]], 
    main_field: str, 
    subfields: List[str]
) -> Dict[str, Any]:
    """
    Calculate individual rankings for each subfield within a main field.
    
    Args:
        papers: List of paper objects
        main_field: The main field name
        subfields: List of subfields within this main field
    
    Returns:
        Dict containing rankings for each subfield within the main field
    """
    subfield_rankings = {}
    
    for subfield in subfields:
        print(f"  Calculating rankings for subfield: {subfield}")
        subfield_result = process_university_ranking(papers, [subfield], target_subfield=subfield)
        
        subfield_ranking = []
        for uni_data in subfield_result.get('ranking', []):
            subfield_ranking.append({
                'university': uni_data['university'],
                'totalContribution': uni_data['totalContribution'],
                'rank': len(subfield_ranking) + 1
            })
        
        subfield_rankings[subfield] = subfield_ranking
    
    return {
        'mainField': main_field,
        'subfields': subfields,
        'subfieldRankings': subfield_rankings
    }

def save_mainfield_rankings(rankings_data: Dict[str, Any], output_path: str) -> None:
    """Save mainfield rankings to JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(rankings_data, f, ensure_ascii=False, indent=2)

def generate_individual_mainfield_files(
    papers: List[Dict[str, Any]], 
    subfields_map: Dict[str, List[str]],
    output_dir: str
) -> None:
    """
    Generate individual JSON files for each main field's rankings.
    
    Args:
        papers: List of paper objects
        subfields_map: Mapping of main fields to their subfields
        output_dir: Directory to save the files
    """
    for main_field, subfields in subfields_map.items():
        main_field_rankings = calculate_mainfield_rankings(papers, subfields, subfields_map, target_mainfield=main_field)
        subfield_rankings = calculate_subfield_rankings_within_mainfield(papers, main_field, subfields)
        
        main_field_filename = main_field.replace(' ', '_').replace('/', '_').replace('&', 'and').replace('–', '-').replace('—', '-').lower()
        output_path = os.path.join(output_dir, f'{main_field_filename}_rankings.json')
        
        combined_rankings = {
            **main_field_rankings,
            'subfieldRankings': subfield_rankings['subfieldRankings'],
            'mainField': main_field,
            'totalSubfields': len(subfields)
        }
        
        save_mainfield_rankings(combined_rankings, output_path)
        
        print(f"Generated rankings for {main_field}: {len(subfields)} subfields with individual rankings")

if __name__ == "__main__":
    print("Use this module via preprocess_data.py or run.py")