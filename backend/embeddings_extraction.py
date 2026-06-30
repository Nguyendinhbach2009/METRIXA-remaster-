import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import json
import os
import sys
import re
import html

# Add the backend directory to the path so we can import the config module
sys.path.append(os.path.dirname(__file__))

# Import the configuration and functions from other backend modules
from config import get_all_json_files, get_all_csv_files

def load_data_from_files():
    """Load data from multiple CSV and JSON files based on config"""
    csv_files = get_all_csv_files()
    json_files = get_all_json_files()
    
    print(f"Found {len(csv_files)} CSV files and {len(json_files)} JSON files")
    
    all_data = []
    total_papers = 0
    valid_papers = 0
    
    for i, (csv_file, json_file) in enumerate(zip(csv_files, json_files)):
        print(f"Processing file pair {i+1}/{len(csv_files)}")
        print(f"  CSV: {os.path.basename(csv_file)}")
        print(f"  JSON: {os.path.basename(json_file)}")
        
        # Check if both files exist
        if not os.path.exists(csv_file):
            print(f"  Warning: CSV file not found: {csv_file}")
            continue
            
        if not os.path.exists(json_file):
            print(f"  Warning: JSON file not found: {json_file}")
            continue
        
        try:
            # Load CSV data
            csv_df = pd.read_csv(csv_file)
            csv_papers = set(csv_df['paperId'].astype(str))
            
            # Load JSON data
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            json_papers = set(json_data.keys())
            
            # Find papers that exist in both CSV and JSON
            common_papers = csv_papers.intersection(json_papers)
            
            print(f"  CSV papers: {len(csv_papers)}")
            print(f"  JSON papers: {len(json_papers)}")
            print(f"  Common papers: {len(common_papers)}")
            
            # Process each common paper
            for paper_id in common_papers:
                # Get CSV data for this paper
                csv_row = csv_df[csv_df['paperId'].astype(str) == paper_id].iloc[0]
                
                # Get JSON data for this paper
                json_paper_data = json_data[paper_id]
                author_affiliations = json_paper_data.get('author_affiliations', [])
                
                # Skip if no author affiliations
                if not author_affiliations:
                    continue
                
                # Extract author names
                authors = []
                for author_info in author_affiliations:
                    if isinstance(author_info, dict):
                        author_name = author_info.get('author', '').strip()
                        if author_name:
                            authors.append(author_name)
                
                # Skip if no valid authors found
                if not authors:
                    continue
                
                # Create combined record
                record = {
                    'paperId': paper_id,
                    'title': csv_row['title'],
                    'predicted_fieldsOfStudy': csv_row['predicted_fieldsOfStudy'],
                    'main_fields': csv_row['main_fields'],
                    'pdf_urls': csv_row['pdf_urls'],
                    'authors': ', '.join(authors)
                }
                
                all_data.append(record)
                valid_papers += 1
            
            total_papers += len(csv_papers)
            
        except Exception as e:
            print(f"  Error processing files: {e}")
            continue
    
    print(f"\nSummary:")
    print(f"Total CSV papers processed: {total_papers}")
    print(f"Valid papers with both CSV and JSON data: {valid_papers}")
    
    # Create DataFrame from collected data
    df = pd.DataFrame(all_data)
    df.to_csv("final_data.csv", index=False)
    sys.exit(0)
    if len(df) > 0:
        print(f"Final dataset shape: {df.shape}")
    else:
        print("Warning: No valid papers found in any file pair!")
    
    return df

# -------------------------
# 1️⃣ Load data from multiple CSV and JSON files
# -------------------------
df = load_data_from_files()

def clean_scientific_text(text: str) -> str:
    """
    Clean text while preserving essential scientific content.
    Removes noise but keeps words useful for topic modeling or context extraction.
    """
    if not isinstance(text, str):
        return ""

    # Decode HTML entities (e.g., &amp; → &)
    text = html.unescape(text)

    # Remove LaTeX-like expressions and equations (keep variable words)
    text = re.sub(r"\$[^$]*\$", " ", text)              # Inline math
    text = re.sub(r"\\\[.*?\\\]", " ", text)            # Display math
    text = re.sub(r"\\\((.*?)\\\)", " ", text)

    # Remove URLs, DOIs, and emails
    text = re.sub(r"http\S+|www\S+|doi\S+|@\S+", " ", text)

    # Remove citations like [12], (Smith et al., 2020), etc.
    text = re.sub(r"\[[0-9,\s\-]+\]", " ", text)
    text = re.sub(r"\([A-Z][a-z]+ et al\.,? \d{4}\)", " ", text)

    # Remove figure/table references
    text = re.sub(r"(Figure|Table|Eq\.?|Equation)\s*\d+", " ", text)

    # Remove special symbols (keep scientific tokens like hyphenated words)
    text = re.sub(r"[^a-zA-Z0-9\-.,;:()/%\s]", " ", text)

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Normalize case (optional)
    text = text.strip()

    return text

df['title'] = df['title'].apply(clean_scientific_text)

import ast

def parse_subfields(x, main_field=None):
    # Convert string representation to list
    if isinstance(x, str):
        try:
            lst = ast.literal_eval(x)
            if isinstance(lst, list):
                subfields = [str(s) for s in lst]  # ensure all items are strings
            else:
                subfields = []
        except:
            subfields = []
    elif isinstance(x, list):
        subfields = [str(s) for s in x]
    else:
        subfields = []

    # Prepend the main field at the start if given
    if main_field is not None:
        if isinstance(main_field, str):
            lst = ast.literal_eval(main_field)
            if isinstance(lst, list):
                for field in lst:
                    subfields.append(field)

    return subfields

def concat_strings(x):
    if isinstance(x, str):
        try:
            lst = ast.literal_eval(x)
            if isinstance(lst, list):
                concat = ", ".join(str(s) for s in lst)
            else:
                concat = ""
        except:
            concat = ""
    elif isinstance(x, list):
        concat = ", ".join(str(s) for s in x)
    else:
        concat = ""

    return concat

df['Subfields'] = df['predicted_fieldsOfStudy'].apply(concat_strings)

df['fields'] = df.apply(
    lambda row: parse_subfields(row['main_fields']),
    axis=1
)
                
df['predicted_fieldsOfStudy'] = df.apply(
    lambda row: parse_subfields(row['predicted_fieldsOfStudy'], main_field=row['main_fields']),
    axis=1
)

# Authors field is already processed as string when loading from JSON, no need to apply concat_strings

df['pdf_urls'] = df.apply(
    lambda row: concat_strings(row['pdf_urls']),
    axis=1
)

def split_fields(field_list):
    if not isinstance(field_list, list) or len(field_list) == 0:
        return "", []  # empty fallback

    main = field_list[0]
    related_list = field_list[1:] if len(field_list) > 1 else []
    related = concat_strings(related_list)
    return main, related


df['original_field'], df['related_fields'] = zip(*df['fields'].apply(split_fields))

# model = SentenceTransformer("sentence-transformers/allenai-specter")
model = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")

def embed_subfields(subfields):
    if not subfields:
        return np.zeros(model.get_sentence_embedding_dimension())
    embeddings = model.encode(subfields)
    return np.mean(embeddings, axis=0)

def embed_subfields_string(subfields):
    if not subfields:
        return np.zeros(model.get_sentence_embedding_dimension())
    embeddings = model.encode(subfields)
    return np.array(embeddings)

df['embedding'] = df['predicted_fieldsOfStudy'].apply(embed_subfields)
# df['embedding'] = df['Subfields'].apply(embed_subfields_string)
paper_vectors = np.stack(df['embedding'].values)

# -----------------------------------------
# Step 3: Reduce dimensions to 3D with t-SNE
# -----------------------------------------
from sklearn.manifold import TSNE

tsne = TSNE(
    n_components=3,
    metric='cosine',
    perplexity=20,       # adjust based on dataset size
    learning_rate=200,
    max_iter=3000,
    random_state=42
)

embeddings_3d = tsne.fit_transform(paper_vectors)

df['x'] = embeddings_3d[:, 0]
df['y'] = embeddings_3d[:, 1]
df['z'] = embeddings_3d[:, 2]

rng = np.random.default_rng(seed=42)
JITTER_SCALE = 0.3
df['x_vis'] = df['x'] + rng.normal(scale=JITTER_SCALE, size=len(df))
df['y_vis'] = df['y'] + rng.normal(scale=JITTER_SCALE, size=len(df))
df['z_vis'] = df['z'] + rng.normal(scale=JITTER_SCALE, size=len(df))


df = df.drop(columns=["embedding", "x", "y", "z", "predicted_fieldsOfStudy", "main_fields", "fields"])
df.to_json("/home/dtth/proj_paper/website/public/points_list.json", index=False)