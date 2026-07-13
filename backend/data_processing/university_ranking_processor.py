"""
University ranking processor for database-backed data processing.
Reads data from PostgreSQL and processes rankings.
"""

import json
import re
import os
from typing import List, Dict, Any, Optional
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_connection import (
    get_db_config,
    fetch_all_papers,
    fetch_paper_authors_by_paper_id,
    fetch_all_subfields,
    fetch_all_mainfields,
    fetch_university_ranking_by_subfield,
    fetch_overall_university_ranking,
)

_allowed_universities = None

def get_allowed_universities() -> set:
    """Get the set of allowed university names (normalized, lowercase)."""
    global _allowed_universities
    if _allowed_universities is not None:
        return _allowed_universities
        
    import json
    import os
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    universities_path = os.path.join(base_dir, 'src', 'data', 'universities.json')
    
    allowed = set()
    try:
        with open(universities_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                # Normalize and add display name
                disp = item.get('display_name')
                if disp:
                    norm_disp = normalize_university_name(disp)
                    if norm_disp:
                        allowed.add(norm_disp.lower())
                
                # Normalize and add aliases
                for alias in item.get('aliases', []):
                    if alias:
                        norm_alias = normalize_university_name(alias)
                        if norm_alias:
                            allowed.add(norm_alias.lower())
                
                # Normalize and add acronyms
                for acr in item.get('acronyms', []):
                    if acr:
                        norm_acr = normalize_university_name(acr)
                        if norm_acr:
                            allowed.add(norm_acr.lower())
    except Exception as e:
        print(f"Warning: Could not load allowed universities from {universities_path}: {e}")
    
    _allowed_universities = allowed
    return _allowed_universities

def load_subfields_mapping() -> Dict[str, List[str]]:
    """Load subfields mapping from fields.json, or build from database if empty."""
    import json
    fields_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'src', 'data', 'fields.json')
    
    try:
        with open(fields_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            subfields_map = data.get('subfieldsMap', {})
            if subfields_map:
                return subfields_map
    except Exception as e:
        print(f"Warning: Could not load subfields mapping from file: {e}")
    
    print("Building subfields mapping from database...")
    return build_subfields_mapping_from_db()

def build_subfields_mapping_from_db() -> Dict[str, List[str]]:
    """Build subfields mapping from database by joining on paper_id."""
    import psycopg2
    from collections import defaultdict
    
    config = get_db_config()
    conn = psycopg2.connect(**config)
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT pm.mainfield, ps.subfield
            FROM core.paper_mainfields pm
            INNER JOIN core.paper_subfields ps ON pm.paper_id = ps.paper_id
            ORDER BY pm.mainfield, ps.subfield
        """)
        
        mapping = defaultdict(list)
        for row in cur.fetchall():
            mainfield = row[0]
            subfield = row[1]
            if subfield not in mapping[mainfield]:
                mapping[mainfield].append(subfield)
        
        for mainfield in mapping:
            mapping[mainfield] = sorted(mapping[mainfield])
        
        cur.close()
        return dict(mapping)
    finally:
        conn.close()

def get_all_subfields(subfields_map: Dict[str, List[str]]) -> List[str]:
    """Get a flat list of all subfields from the mapping."""
    all_subfields = []
    for subfields in subfields_map.values():
        all_subfields.extend(subfields)
    return sorted(list(set(all_subfields)))

def norm(s: str) -> Optional[str]:
    """Normalize string."""
    if not s and s != 0:
        return None
    return re.sub(r'\s+', ' ', str(s)).strip()

def is_informative_university(uni: str) -> bool:
    """Check if university name is informative."""
    if not uni:
        return False
    s = str(uni).strip()
    if len(s) < 4:
        return False
    if re.match(r'^\s*(department|dept|division|section)\b', s, re.I):
        if not re.search(r'\b(university|univ|hospital|institute|college|faculty|centre|center)\b', s, re.I):
            return False
    if re.match(r'^\d+', s):
        return False
    return True

def normalize_university_name(s: str) -> Optional[str]:
    """Normalize university/org name."""
    if not s:
        return None
    t = str(s).strip()
    t = re.sub(r"([a-z])([A-Z][a-z]{2,})$", r"\1, \2", t)
    t = re.sub(r"\s+", " ", t).replace(", ", ", ").replace(" ,", ",").strip()
    t = re.sub(r"^[,.\-:\s]+|[,.\-:\s]+$", "", t)
    return t or None

def build_paper_from_db(paper_row: Dict[str, Any]) -> Dict[str, Any]:
    """Build a paper dict from database row, fetching authors from db."""
    paper = {
        'paperId': paper_row['paper_id'],
        'title': paper_row['title'],
        'abstract': paper_row['abstract'],
        'pdf_urls': paper_row.get('pdf_urls', []),
        'fields_of_study': paper_row.get('fields_of_study', []),
        'predicted_fields': paper_row.get('predicted_fields', []),
        'main_fields': paper_row.get('main_fields', []),
    }
    
    authors = fetch_paper_authors_by_paper_id(paper['paperId'])
    if authors:
        paper['api_authors'] = [
            {
                'name': a['author_name'],
                'affiliation': a.get('university_name')
            }
            for a in authors
        ]
    else:
        paper['api_authors'] = []
    
    return paper

def extract_all_fields(paper: Dict[str, Any]) -> List[str]:
    """Extract all fields from paper - returns list of all fields including subfields."""
    if not paper:
        return []
    
    fields = []
    
    for field_list in [
        paper.get('fields_of_study', []),
        paper.get('predicted_fields', []),
        paper.get('main_fields', [])
    ]:
        if isinstance(field_list, list):
            for f in field_list:
                if f:
                    normalized = norm(f)
                    if normalized:
                        fields.append(normalized)
    
    seen = set()
    unique_fields = []
    for f in fields:
        if f not in seen:
            seen.add(f)
            unique_fields.append(f)
    
    return unique_fields

def extract_subfields_only(paper: Dict[str, Any]) -> List[str]:
    """Extract only subfields from paper - from predicted_fields."""
    if not paper:
        return []
    
    subfields = []
    
    if isinstance(paper.get('predicted_fields'), list) and paper['predicted_fields']:
        for f in paper['predicted_fields']:
            if f:
                normalized = norm(f)
                if normalized:
                    subfields.append(normalized)
    
    return subfields

def to_paper_array(data) -> List[Dict[str, Any]]:
    """Convert data to paper array format."""
    if not data:
        return []
    if isinstance(data, list):
        return data
    return list(data.values())

def process_university_ranking(
    papers: List[Dict[str, Any]], 
    selected_fields: Optional[List[str]] = None, 
    target_subfield: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process university ranking data from papers.
    
    Args:
        papers: List of paper objects
        selected_fields: Optional list of fields to filter by
        target_subfield: Optional specific subfield to calculate rankings for
    
    Returns:
        Dict containing ranking data, authors by university, and field contributions
    """
    papers = to_paper_array(papers)
    
    selected_fields_lower = [f.lower() for f in selected_fields] if selected_fields else None
    target_subfield_lower = target_subfield.lower() if target_subfield else None
    
    uni_contrib = {}
    uni_author_detail = {}
    uni_field_map = {}
    
    for p in papers:
        if not p:
            continue
        
        all_fields = extract_all_fields(p)
        subfields_only = extract_subfields_only(p)
        
        if selected_fields_lower:
            has_match = False
            for paper_field in all_fields:
                if paper_field.lower() in selected_fields_lower:
                    has_match = True
                    break
            if not has_match:
                continue
        
        if target_subfield_lower:
            subfield_match = False
            for sf in subfields_only:
                if sf.lower() == target_subfield_lower:
                    subfield_match = True
                    break
            if not subfield_match:
                continue
        
        authors = p.get('api_authors', [])
        if not authors:
            continue
        
        num_authors = len(authors)
        num_subfields = len(subfields_only) if subfields_only else 1
        per_author_per_subfield = 1.0 / (num_authors * num_subfields) if num_authors > 0 and num_subfields > 0 else 0
        
        seen_unis = set()
        
        for a in authors:
            name = norm(a.get('name')) or "Unknown"
            aff_raw = a.get('affiliation')
            uni_candidate = normalize_university_name(aff_raw) if aff_raw else None
            uni = uni_candidate if is_informative_university(uni_candidate) else None
            
            if not uni:
                continue
            
            allowed_unis = get_allowed_universities()
            if allowed_unis and uni.lower() not in allowed_unis:
                continue
            
            if uni not in seen_unis:
                seen_unis.add(uni)
            
            total_author_contrib = per_author_per_subfield * num_subfields if num_subfields > 0 else 0
            uni_contrib[uni] = uni_contrib.get(uni, 0) + total_author_contrib
            
            if uni not in uni_author_detail:
                uni_author_detail[uni] = {}
            uni_author_detail[uni][name] = uni_author_detail[uni].get(name, 0) + total_author_contrib
            
            for paper_field in subfields_only:
                if target_subfield_lower and paper_field.lower() != target_subfield_lower:
                    continue
                if uni not in uni_field_map:
                    uni_field_map[uni] = {}
                uni_field_map[uni][paper_field] = uni_field_map[uni].get(paper_field, 0) + per_author_per_subfield
    
    def get_university_contribution(u):
        if target_subfield_lower:
            for field_name, contrib in uni_field_map.get(u, {}).items():
                if field_name.lower() == target_subfield_lower:
                    return contrib
            return 0
        return uni_contrib.get(u, 0)
    
    def get_author_contrib_for_subfield(u, target_sf_lower):
        author_map = uni_author_detail.get(u, {})
        field_contribs = uni_field_map.get(u, {})
        total = 0
        for field_name, contrib in field_contribs.items():
            if field_name.lower() == target_sf_lower:
                total += contrib
        return total
    
    sorted_universities = [
        {'university': u, 'totalContribution': get_university_contribution(u)}
        for u in uni_contrib
    ]
    sorted_universities.sort(key=lambda x: x['totalContribution'], reverse=True)
    
    authors_by_uni_obj = {}
    for u in uni_author_detail:
        author_map = uni_author_detail[u]
        
        if target_subfield_lower:
            total = get_author_contrib_for_subfield(u, target_subfield_lower)
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
    """Get unique fields from the dataset - includes all fields and subfields."""
    papers = to_paper_array(raw_data)
    fields_set = set()
    
    for p in papers:
        if not p:
            continue
        all_fields = extract_all_fields(p)
        for field in all_fields:
            if field:
                fields_set.add(field)
    
    return sorted(list(fields_set))

def load_papers_from_db() -> List[Dict[str, Any]]:
    """Load all papers from database."""
    print("Loading papers from database...")
    sys.stdout.flush()
    papers = []
    
    db_rows = fetch_all_papers()
    print(f"  Loaded {len(db_rows)} papers from database")
    sys.stdout.flush()
    
    for i, row in enumerate(db_rows):
        paper = build_paper_from_db(row)
        papers.append(paper)
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(db_rows)} papers...")
            sys.stdout.flush()
    
    print(f"  Finished loading {len(papers)} papers")
    sys.stdout.flush()
    return papers