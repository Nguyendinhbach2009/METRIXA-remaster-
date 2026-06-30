import json
import re
import csv
import os
from collections import defaultdict
from config import get_all_json_files, get_merge_json_file_path

# Load author affiliations data at module level
def load_author_affiliations():
    """Load author affiliations data from single merge.json file"""
    all_affiliations = {}
    json_file = get_merge_json_file_path()
    
    print(f"Loading author affiliations from {json_file}...")
    
    try:
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Load data from the merge file
                all_affiliations.update(data)
                print(f"  Loaded {len(data)} papers from {os.path.basename(json_file)}")
        else:
            print(f"  Warning: File not found: {json_file}")
    except Exception as e:
        print(f"  Warning: Could not load {json_file}: {e}")
    
    print(f"Total papers loaded: {len(all_affiliations)}")
    return all_affiliations

# Load the affiliations data
author_affiliations_data = load_author_affiliations()

def load_subfields_mapping(csv_path=None):
    """Load subfields mapping from CSV file"""
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'fields.csv')
    
    subfields_map = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                field = row['fieldsOfStudy']
                subfields_str = row['subfields']
                # Parse the JSON array string
                subfields = json.loads(subfields_str)
                subfields_map[field] = subfields
    except Exception as e:
        print(f"Warning: Could not load subfields mapping: {e}")
    
    return subfields_map

def get_all_subfields(subfields_map):
    """Get a flat list of all subfields from the mapping"""
    all_subfields = []
    for subfields in subfields_map.values():
        all_subfields.extend(subfields)
    return sorted(list(set(all_subfields)))


from typing import List, Dict, Any, Optional

def to_paper_array(data):
    """Convert data to paper array format"""
    if not data:
        return []
    if isinstance(data, list):
        return data
    return list(data.values())

def norm(s):
    """Normalize string"""
    if not s and s != 0:
        return None
    return re.sub(r'\s+', ' ', str(s)).strip()

def extract_field(paper):
    """Extract field from paper - only from api_fieldsOfStudy"""
    if not paper:
        return None
    if isinstance(paper.get('api_fieldsOfStudy'), list) and paper['api_fieldsOfStudy']:
        f = paper['api_fieldsOfStudy'][0]
        if f:
            return norm(f)

def extract_subfields_only(paper):
    """Extract only subfields from paper - from predicted_fieldsOfStudy"""
    if not paper:
        return []
    
    subfields = []
    
    # Get subfields from predicted_fieldsOfStudy only
    if isinstance(paper.get('predicted_fieldsOfStudy'), list) and paper['predicted_fieldsOfStudy']:
        for f in paper['predicted_fieldsOfStudy']:
            if f:
                normalized = norm(f)
                if normalized:
                    subfields.append(normalized)
    
    return subfields

def extract_all_fields(paper):
    """Extract all fields from paper - returns list of all fields including subfields"""
    if not paper:
        return []
    
    fields = []
    
    # Get main fields from api_fieldsOfStudy
    if isinstance(paper.get('api_fieldsOfStudy'), list) and paper['api_fieldsOfStudy']:
        for f in paper['api_fieldsOfStudy']:
            if f:
                normalized = norm(f)
                if normalized:
                    fields.append(normalized)
    
    # Get subfields from predicted_fieldsOfStudy
    if isinstance(paper.get('predicted_fieldsOfStudy'), list) and paper['predicted_fieldsOfStudy']:
        for f in paper['predicted_fieldsOfStudy']:
            if f:
                normalized = norm(f)
                if normalized:
                    fields.append(normalized)
    
    # Get from main_fields if available
    if isinstance(paper.get('main_fields'), list) and paper['main_fields']:
        for f in paper['main_fields']:
            if f:
                normalized = norm(f)
                if normalized:
                    fields.append(normalized)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_fields = []
    for f in fields:
        if f not in seen:
            seen.add(f)
            unique_fields.append(f)
    
    return unique_fields

def normalize_university_name(s):
    """Normalize university/org name using simple heuristics"""
    if not s:
        return None
    t = str(s).strip()
    t = re.sub(r"([a-z])([A-Z][a-z]{2,})$", r"\1, \2", t)
    t = re.sub(r"\s+", " ", t).replace(", ", ", ").replace(" ,", ",").strip()
    t = re.sub(r"^[,.\-:\s]+|[,.\-:\s]+$", "", t)
    return t or None

def parse_affiliation_block(text):
    """Parse affiliation block to extract university name"""
    if not text or not isinstance(text, str):
        return None
    
    parts = [p.strip() for p in re.split(r'\n|;|,|\(|\)|—', text) if p.strip()]
    if not parts:
        return None
    
    strong_re = re.compile(r'\b(university|universit|univ|college|institute|hospital|school|faculty|centre|center|academy|research|clinic)\b', re.I)
    uni_re = re.compile(r'\b(university|univ)\b', re.I)
    
    # Look for explicit university mentions first
    for p in parts:
        if uni_re.search(p):
            return normalize_university_name(p)
    
    # Look for strong institutional indicators
    for p in parts:
        if strong_re.search(p):
            if re.match(r'^\s*(department|dept|division|section)\b', p, re.I) and not uni_re.search(p):
                continue
            return normalize_university_name(p)
    
    # Look for candidates with sufficient words
    candidates = []
    for p in parts:
        words = [w for w in p.split() if w]
        if len(words) < 3:
            continue
        if re.match(r'^\s*(department|dept|division|section|table|figure)\b', p, re.I):
            continue
        candidates.append(p)
    
    if candidates:
        candidates.sort(key=len, reverse=True)
        return normalize_university_name(candidates[0])
    
    # Fallback to last part
    last = parts[-1]
    last_words = [w for w in last.split() if w]
    if len(last_words) >= 2 and not re.match(r'^\s*(department|dept)\b', last, re.I):
        return normalize_university_name(last)
    
    return None

def build_authors(paper):
    """Build authors list from paper"""
    if not paper:
        return []
    
    out = []
    
    # Try to get authors and affiliations from the external JSON file first
    paper_id = str(paper.get('paperId', ''))
    if paper_id and paper_id in author_affiliations_data:
        paper_data = author_affiliations_data[paper_id]
        author_affiliations = paper_data.get('author_affiliations', [])
        
        if isinstance(author_affiliations, list) and author_affiliations:
            for author_info in author_affiliations:
                if isinstance(author_info, dict):
                    name = norm(author_info.get('author', '')) or "Unknown"
                    affiliations = author_info.get('affiliations', [])
                    # Use the first affiliation if available, otherwise None
                    affiliation = affiliations[0] if affiliations and isinstance(affiliations, list) and len(affiliations) > 0 else None
                    if affiliation:
                        affiliation = normalize_university_name(affiliation)
                    out.append({'name': name, 'affiliation': affiliation})
            return out
    
    # Fallback to api_authors - now with direct affiliation support
    if isinstance(paper.get('api_authors'), list) and paper['api_authors']:
        for a in paper['api_authors']:
            if isinstance(a, dict):
                name = norm(a.get('name', '')) or "Unknown"
                # Get affiliation directly from the author dict
                affiliation = a.get('affiliation')
                if affiliation:
                    affiliation = normalize_university_name(affiliation)
                out.append({'name': name, 'affiliation': affiliation})
            else:
                name = norm(a) or "Unknown"
                out.append({'name': name, 'affiliation': None})
        return out
    
    # Fallback to annotations
    annotations = paper.get('content', {}).get('annotations', {})
    
    if isinstance(annotations.get('author'), list) and annotations['author']:
        aff_arr = annotations.get('authoraffiliation', [])
        
        if isinstance(aff_arr, list) and len(aff_arr) >= len(annotations['author']):
            for i, author in enumerate(annotations['author']):
                raw = str(author or "")
                name_line = raw.split('\n')[0].strip()
                name = norm(name_line) or "Unknown"
                aff = parse_affiliation_block(str(aff_arr[i] or ""))
                out.append({'name': name, 'affiliation': aff})
            return out
        
        for author in annotations['author']:
            raw = str(author or "")
            lines = [l.strip() for l in raw.split('\n') if l.strip()]
            name = norm(lines[0] or "") or "Unknown"
            rest = ' '.join(lines[1:])
            aff_from_rest = parse_affiliation_block(rest) if rest else None
            out.append({'name': name, 'affiliation': aff_from_rest})
        return out
    
    # Fallback to bibauthor
    if isinstance(annotations.get('bibauthor'), list) and annotations['bibauthor']:
        aff_arr = annotations.get('authoraffiliation', [])
        
        for i, author in enumerate(annotations['bibauthor']):
            raw = str(author or "")
            name = norm(raw.split('\n')[0]) or "Unknown"
            aff = parse_affiliation_block(str(aff_arr[i])) if aff_arr and isinstance(aff_arr, list) and i < len(aff_arr) and aff_arr[i] else None
            out.append({'name': name, 'affiliation': aff})
        return out
    
    return out

def is_informative_university(uni):
    """Check if university name is informative"""
    if not uni:
        return False
    
    s = str(uni).strip()
    if len(s) < 4:
        return False
    
    if re.match(r'^\s*(department|dept|division|section)\b', s, re.I) and not re.search(r'\b(university|univ|hospital|institute|college|faculty|centre|center)\b', s, re.I):
        return False
    
    if re.match(r'^\d+', s):
        return False
    
    return True

def process_university_ranking(raw_data: List[Dict[str, Any]], selected_fields: Optional[List[str]] = None, target_subfield: Optional[str] = None) -> Dict[str, Any]:
    """
    Process university ranking data
    
    Args:
        raw_data: List of paper objects
        selected_fields: Optional list of fields to filter by
        target_subfield: Optional specific subfield to calculate rankings for
    
    Returns:
        Dict containing ranking data, authors by university, and field contributions
    """
    papers = to_paper_array(raw_data)
    
    uni_contrib = {}
    uni_author_detail = {}
    uni_author_set = {}  # Track unique authors per university using sets
    uni_field_map = {}
    
    for p in papers:
        if not p:
            continue
        
        # Extract all fields (including subfields) from the paper
        all_fields = extract_all_fields(p)
        # Extract only subfields for contribution calculation
        subfields_only = extract_subfields_only(p)
        field = extract_field(p)  # Keep for backward compatibility
        
        # Filter by selected fields if provided
        if selected_fields and selected_fields:
            # Check if any of the paper's fields match the selected fields
            has_match = False
            for paper_field in all_fields:
                if paper_field in selected_fields:
                    has_match = True
                    break
            if not has_match:
                continue
        
        # Filter by target subfield if specified
        if target_subfield:
            # Only include papers that have the target subfield
            if target_subfield not in subfields_only:
                continue
        
        authors = build_authors(p)
        
        # Fallback for author list
        if not authors and isinstance(p.get('api_authors'), list):
            authors = [{'name': norm(a['name'] if isinstance(a, dict) else a) or "Unknown", 'affiliation': None} for a in p['api_authors']]
        
        if not authors:
            continue
        
        # Calculate contributions: each author gets 1/authors total, then divided by number of subfields
        num_authors = len(authors)
        num_subfields = len(subfields_only) if subfields_only else 1  # Only count subfields, not main fields
        per_author_per_subfield = 1.0 / (num_authors * num_subfields) if num_authors > 0 and num_subfields > 0 else 0
        
        seen_unis = set()
        
        for a in authors:
            name = norm(a['name']) or "Unknown"
            aff_raw = a.get('affiliation')
            uni_candidate = normalize_university_name(aff_raw) if aff_raw else None
            uni = uni_candidate if is_informative_university(uni_candidate) else None
            
            if not uni:
                continue
            
            if uni not in seen_unis:
                seen_unis.add(uni)
            
            # Add the author's total contribution (per_author_per_subfield * num_subfields)
            total_author_contrib = per_author_per_subfield * num_subfields if num_subfields > 0 else 0
            uni_contrib[uni] = uni_contrib.get(uni, 0) + total_author_contrib
            
            if uni not in uni_author_detail:
                uni_author_detail[uni] = {}
            uni_author_detail[uni][name] = uni_author_detail[uni].get(name, 0) + total_author_contrib
            
            # Track unique authors using sets
            if uni not in uni_author_set:
                uni_author_set[uni] = set()
            uni_author_set[uni].add(name)
            
            # Track contribution for each subfield individually
            for paper_field in subfields_only:
                if uni not in uni_field_map:
                    uni_field_map[uni] = {}
                uni_field_map[uni][paper_field] = uni_field_map[uni].get(paper_field, 0) + per_author_per_subfield
    
    # Sort universities by contribution - use subfield-specific contribution if target_subfield is specified
    def get_university_contribution(u):
        if target_subfield:
            # Return only the contribution for the target subfield
            return uni_field_map.get(u, {}).get(target_subfield, 0)
        else:
            # Return total contribution across all subfields
            return uni_contrib.get(u, 0)
    
    sorted_universities = [
        {
            'university': u,
            'totalContribution': get_university_contribution(u)
        }
        for u in uni_contrib
    ]
    sorted_universities.sort(key=lambda x: x['totalContribution'], reverse=True)
    
    # Build authors by university object
    authors_by_uni_obj = {}
    for u in uni_author_detail:
        author_map = uni_author_detail[u]
        
        if target_subfield:
            # For subfield-specific rankings, use only the target subfield contribution
            total = uni_field_map.get(u, {}).get(target_subfield, 0)
            # Approximate author contributions for the target subfield
            # In a full implementation, we'd track per-author per-subfield contributions
            # For now, distribute the subfield contribution proportionally among authors
            total_uni_contrib = uni_contrib.get(u, 0)
            if total_uni_contrib > 0:
                authors_by_uni_obj[u] = [
                    {
                        'author': author,
                        'contribution': contrib * (total / total_uni_contrib),
                        'percent': (contrib * (total / total_uni_contrib)) / total if total > 0 else 0
                    }
                    for author, contrib in author_map.items()
                ]
            else:
                authors_by_uni_obj[u] = []
        else:
            # For overall rankings, use total contribution
            total = uni_contrib.get(u, 0)
            authors_by_uni_obj[u] = [
                {
                    'author': author,
                    'contribution': contrib,
                    'percent': contrib / total if total > 0 else 0
                }
                for author, contrib in author_map.items()
            ]
        
        authors_by_uni_obj[u].sort(key=lambda x: x['contribution'], reverse=True)
    
    return {
        'ranking': sorted_universities,
        'authorsByUniversity': authors_by_uni_obj,
        'uniFieldContrib': uni_field_map,
        'totalPapers': len(papers)
    }

def get_unique_fields(raw_data: List[Dict[str, Any]]) -> List[str]:
    """Get unique fields from the dataset - includes all fields and subfields"""
    papers = to_paper_array(raw_data)
    fields_set = set()
    
    for p in papers:
        if not p:
            continue
        # Get all fields including subfields
        all_fields = extract_all_fields(p)
        for field in all_fields:
            if field:
                fields_set.add(field)
    
    return sorted(list(fields_set))