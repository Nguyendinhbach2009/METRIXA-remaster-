import json
import os
from collections import defaultdict
from typing import List, Dict, Any, Optional
from university_ranking_processor import process_university_ranking, load_subfields_mapping


def calculate_mainfield_rankings(papers: List[Dict[str, Any]], selected_fields: List[str]) -> Dict[str, Any]:
    """
    Calculate university rankings by main field for the selected universities
    
    Args:
        papers: List of paper objects
        selected_fields: List of selected fields to analyze
    
    Returns:
        Dict containing mainfield rankings for all universities in the selected fields
    """
    
    # Load subfields mapping to understand main field hierarchy
    subfields_map = load_subfields_mapping()
    
    # Get all main fields from the mapping
    main_fields = list(subfields_map.keys())
    
    # Aggregate university contributions by main field
    uni_mainfield_contrib = {}
    
    # First, process each subfield to get its contribution data
    for main_field in main_fields:
        uni_mainfield_contrib[main_field] = {}
        
        # Get subfields for this main field
        subfields = subfields_map.get(main_field, [])
        
        # Process each subfield and accumulate contributions for the main field
        for subfield in subfields:
            if subfield in selected_fields:
                # Process ranking for this specific subfield
                subfield_result = process_university_ranking(papers, [subfield], target_subfield=subfield)
                
                # Accumulate contributions for each university in this main field
                for uni_data in subfield_result.get('ranking', []):
                    uni_name = uni_data['university']
                    contrib = uni_data['totalContribution']
                    
                    if uni_name not in uni_mainfield_contrib[main_field]:
                        uni_mainfield_contrib[main_field][uni_name] = 0
                    
                    uni_mainfield_contrib[main_field][uni_name] += contrib
    
    # Calculate rankings for each main field
    mainfield_rankings = {}
    
    for main_field, uni_contribs in uni_mainfield_contrib.items():
        # Convert to list and sort by contribution
        ranking_list = [
            {
                'university': uni,
                'totalContribution': contrib,
                'paperCount': 0,  # We'll add paper count from subfield data if needed
                'authorCount': 0  # We'll add author count from subfield data if needed
            }
            for uni, contrib in uni_contribs.items()
        ]
        
        # Sort by total contribution
        ranking_list.sort(key=lambda x: x['totalContribution'], reverse=True)
        
        # Add rank position
        for i, uni_data in enumerate(ranking_list):
            uni_data['rank'] = i + 1
        
        mainfield_rankings[main_field] = ranking_list
    
    return {
        'mainfieldRankings': mainfield_rankings,
        'selectedFields': selected_fields,
        'mainFields': main_fields
    }


def generate_mainfield_rankings_for_all_mainfields(papers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate mainfield rankings for all main fields
    
    Args:
        papers: List of paper objects
    
    Returns:
        Dict containing all mainfield rankings
    """
    
    # Load subfields mapping to get all main fields and their subfields
    subfields_map = load_subfields_mapping()
    main_fields = list(subfields_map.keys())
    
    all_rankings = {}
    
    for main_field in main_fields:
        subfields = subfields_map.get(main_field, [])
        
        # Calculate rankings for this main field using all its subfields
        main_field_ranking = calculate_mainfield_rankings(papers, subfields)
        all_rankings[main_field] = main_field_ranking
    
    return {
        'allMainfieldRankings': all_rankings,
        'totalMainFields': len(main_fields),
        'mainFields': main_fields
    }


def calculate_subfield_rankings_within_mainfield(papers: List[Dict[str, Any]], main_field: str, subfields: List[str]) -> Dict[str, Any]:
    """
    Calculate individual rankings for each subfield within a main field
    
    Args:
        papers: List of paper objects
        main_field: The main field name
        subfields: List of subfields within this main field
    
    Returns:
        Dict containing rankings for each subfield within the main field
    """
    from university_ranking_processor import process_university_ranking
    
    subfield_rankings = {}
    
    # Calculate rankings for each subfield individually
    for subfield in subfields:
        print(f"  Calculating rankings for subfield: {subfield}")
        subfield_result = process_university_ranking(papers, [subfield], target_subfield=subfield)
        
        # Extract ranking information for this subfield
        subfield_ranking = []
        for uni_data in subfield_result.get('ranking', []):
            subfield_ranking.append({
                'university': uni_data['university'],
                'totalContribution': uni_data['totalContribution'],
                'rank': len(subfield_ranking) + 1  # Assign rank based on position
            })
        
        subfield_rankings[subfield] = subfield_ranking
    
    return {
        'mainField': main_field,
        'subfields': subfields,
        'subfieldRankings': subfield_rankings
    }


def save_mainfield_rankings(rankings_data: Dict[str, Any], output_path: str):
    """Save mainfield rankings to JSON file"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(rankings_data, f, ensure_ascii=False, indent=2)


def generate_individual_mainfield_files(papers: List[Dict[str, Any]], output_dir: str):
    """
    Generate individual JSON files for each main field's rankings
    
    Args:
        papers: List of paper objects
        output_dir: Directory to save the files
    """
    
    # Load subfields mapping
    subfields_map = load_subfields_mapping()
    
    for main_field, subfields in subfields_map.items():
        # Generate rankings for this main field
        main_field_rankings = calculate_mainfield_rankings(papers, subfields)
        
        # Also generate individual subfield rankings within this main field
        subfield_rankings = calculate_subfield_rankings_within_mainfield(papers, main_field, subfields)
        
        # Create filename for this main field
        main_field_filename = main_field.replace(' ', '_').replace('/', '_').replace('&', 'and').replace('–', '-').replace('—', '-').lower()
        output_path = os.path.join(output_dir, f'{main_field_filename}_rankings.json')
        
        # Combine both main field rankings and subfield rankings
        combined_rankings = {
            **main_field_rankings,  # Include existing main field rankings
            'subfieldRankings': subfield_rankings['subfieldRankings'],  # Add subfield rankings
            'mainField': main_field,
            'totalSubfields': len(subfields)
        }
        
        # Save the rankings
        save_mainfield_rankings(combined_rankings, output_path)
        
        print(f"Generated rankings for {main_field}: {len(subfields)} subfields with individual rankings")


if __name__ == "__main__":
    # Example usage
    from preprocess_data import load_merged_data
    
    # Load papers data
    papers = load_merged_data()
    print(f"Loaded {len(papers)} papers for mainfield ranking calculation")
    
    # Generate rankings for all main fields
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'rankings')
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate individual mainfield files
    generate_individual_mainfield_files(papers, output_dir)
    
    print("Mainfield rankings generation complete!")