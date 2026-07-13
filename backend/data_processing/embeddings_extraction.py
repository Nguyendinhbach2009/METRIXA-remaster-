"""
Embeddings extraction for 3D visualization.
Reads data from PostgreSQL and generates t-SNE embeddings for visualization.

Usage:
    python embeddings_extraction.py                    # Run (uses env vars for DB)
    python embeddings_extraction.py --password "xxx"   # Run with explicit password
"""

import argparse
import json
import os
import sys
import numpy as np
import pandas as pd
import re
import html
import ast
import time
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_connection import (
    get_db_config,
    fetch_all_papers,
    fetch_paper_authors_by_paper_id,
    close_pool,
)

def clean_scientific_text(text: str) -> str:
    """
    Clean text while preserving essential scientific content.
    """
    if not isinstance(text, str):
        return ""

    text = html.unescape(text)
    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(r"\\\[.*?\\\]", " ", text)
    text = re.sub(r"\\\((.*?)\\\)", " ", text)
    text = re.sub(r"http\S+|www\S+|doi\S+|@\S+", " ", text)
    text = re.sub(r"\[[0-9,\s\-]+\]", " ", text)
    text = re.sub(r"\([A-Z][a-z]+ et al\.,? \d{4}\)", " ", text)
    text = re.sub(r"(Figure|Table|Eq\.?|Equation)\s*\d+", " ", text)
    text = re.sub(r"[^a-zA-Z0-9\-.,;:()/%\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return text

def norm(s: str) -> str:
    """Normalize string."""
    if not s and s != 0:
        return None
    return re.sub(r'\s+', ' ', str(s)).strip()

def parse_subfields(x, main_field=None) -> List[str]:
    """Parse subfields from string or list."""
    if isinstance(x, str):
        try:
            lst = ast.literal_eval(x)
            if isinstance(lst, list):
                subfields = [str(s) for s in lst]
            else:
                subfields = []
        except:
            subfields = []
    elif isinstance(x, list):
        subfields = [str(s) for s in x]
    else:
        subfields = []

    if main_field is not None:
        if isinstance(main_field, str):
            try:
                lst = ast.literal_eval(main_field)
                if isinstance(lst, list):
                    for field in lst:
                        subfields.append(field)
            except:
                pass

    return subfields

def concat_strings(x) -> str:
    """Concatenate strings from list or string representation."""
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

def load_papers_from_db_for_embeddings() -> List[Dict[str, Any]]:
    """Load papers from database for embeddings processing."""
    print("Loading papers from database for embeddings...")
    sys.stdout.flush()
    papers = []
    
    db_rows = fetch_all_papers()
    print(f"  Loaded {len(db_rows)} papers")
    sys.stdout.flush()
    
    for row in db_rows:
        paper = {
            'paperId': row['paper_id'],
            'title': row['title'],
            'abstract': row.get('abstract', ''),
            'pdf_urls': row.get('pdf_urls', []),
            'fields_of_study': row.get('fields_of_study', []),
            'predicted_fields': row.get('predicted_fields', []),
            'main_fields': row.get('main_fields', []),
        }
        papers.append(paper)
    
    return papers

def extract_embeddings_data() -> pd.DataFrame:
    """Extract and process data for embeddings visualization."""
    papers = load_papers_from_db_for_embeddings()
    
    print(f"Processing {len(papers)} papers for embeddings...")
    sys.stdout.flush()
    
    all_data = []
    for paper in papers:
        record = {
            'paperId': paper['paperId'],
            'title': paper['title'],
            'predicted_fieldsOfStudy': paper.get('predicted_fields', []),
            'main_fields': paper.get('main_fields', []),
        }
        all_data.append(record)
    
    df = pd.DataFrame(all_data)
    
    if len(df) == 0:
        print("Warning: No papers found!")
        sys.stdout.flush()
        return df
    
    df['title'] = df['title'].apply(clean_scientific_text)
    
    df['Subfields'] = df['predicted_fieldsOfStudy'].apply(concat_strings)
    
    df['fields'] = df.apply(
        lambda row: parse_subfields(row['main_fields']),
        axis=1
    )
    
    df['predicted_fieldsOfStudy'] = df.apply(
        lambda row: parse_subfields(row['predicted_fieldsOfStudy'], main_field=row['main_fields']),
        axis=1
    )
    
    df['pdf_urls'] = df.apply(
        lambda row: concat_strings(row.get('pdf_urls', [])),
        axis=1
    )
    
    def split_fields(field_list):
        if not isinstance(field_list, list) or len(field_list) == 0:
            return "", []
        main = field_list[0]
        related_list = field_list[1:] if len(field_list) > 1 else []
        related = concat_strings(related_list)
        return main, related
    
    df['original_field'], df['related_fields'] = zip(*df['fields'].apply(split_fields))
    
    return df

def generate_embeddings(df: pd.DataFrame, output_path: str, batch_size: int = 32) -> None:
    """Generate t-SNE embeddings and save to JSON."""
    from sentence_transformers import SentenceTransformer
    from sklearn.manifold import TSNE
    from tqdm import tqdm
    
    if len(df) == 0:
        print("No data to generate embeddings for!")
        sys.stdout.flush()
        return
    
    model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    skip_embeddings = os.getenv("SKIP_EMBEDDINGS", "false").lower() == "true"
    
    if skip_embeddings:
        print("Skipping embeddings - using random projection...")
        sys.stdout.flush()
        n_samples = min(len(df), 2000)
        indices = np.random.RandomState(42).choice(len(df), n_samples, replace=False)
        df_sample = df.iloc[indices].reset_index(drop=True)
        
        X = np.random.randn(len(df_sample), 384)
        
        tsne = TSNE(
            n_components=3,
            metric='euclidean',
            perplexity=min(30, max(5, n_samples // 10)),
            learning_rate='auto',
            max_iter=300,
            random_state=42,
            init='pca'
        )
        
        embeddings_3d = tsne.fit_transform(X)
        
        df_sample['x'] = embeddings_3d[:, 0]
        df_sample['y'] = embeddings_3d[:, 1]
        df_sample['z'] = embeddings_3d[:, 2]
        
        rng = np.random.default_rng(seed=42)
        JITTER_SCALE = 0.3
        df_sample['x_vis'] = df_sample['x'] + rng.normal(scale=JITTER_SCALE, size=len(df_sample))
        df_sample['y_vis'] = df_sample['y'] + rng.normal(scale=JITTER_SCALE, size=len(df_sample))
        df_sample['z_vis'] = df_sample['z'] + rng.normal(scale=JITTER_SCALE, size=len(df_sample))
        
        df_sample = df_sample.drop(columns=["embedding", "x", "y", "z", "predicted_fieldsOfStudy", "main_fields", "fields"], errors='ignore')
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df_sample.to_json(output_path, orient='records', indent=2, force_ascii=False)
        
        print(f"Saved embeddings to {output_path}")
        sys.stdout.flush()
        return
    
    print(f"Loading sentence transformer model ({model_name})...")
    sys.stdout.flush()
    model = SentenceTransformer(model_name)
    
    print(f"Computing embeddings for {len(df)} papers...")
    sys.stdout.flush()
    
    subfields_list = df['predicted_fieldsOfStudy'].tolist()
    embeddings_list = []
    
    empty_embedding = np.zeros(model.get_sentence_embedding_dimension())
    
    for i in tqdm(range(0, len(subfields_list), batch_size), desc="Embedding papers", unit="batches"):
        batch = subfields_list[i:i+batch_size]
        batch_embeddings = []
        for subfields in batch:
            if not subfields or len(subfields) == 0:
                batch_embeddings.append(empty_embedding.copy())
            else:
                emb = model.encode(subfields, show_progress_bar=False)
                batch_embeddings.append(np.mean(emb, axis=0))
        embeddings_list.extend(batch_embeddings)
    
    df['embedding'] = embeddings_list
    
    paper_vectors = np.stack(df['embedding'].values)
    
    n_samples = len(paper_vectors)
    
    if n_samples > 2000:
        print(f"Reducing to 2000 samples for t-SNE (original: {n_samples})...")
        sys.stdout.flush()
        indices = np.random.RandomState(42).choice(n_samples, 2000, replace=False)
        df = df.iloc[indices].reset_index(drop=True)
        paper_vectors = paper_vectors[indices]
        n_samples = 2000
    
    print("Running dimensionality reduction...")
    sys.stdout.flush()
    
    perplexity = min(30, max(5, n_samples // 10))
    
    tsne = TSNE(
        n_components=3,
        metric='cosine',
        perplexity=perplexity,
        learning_rate='auto',
        max_iter=300,
        random_state=42,
        init='pca'
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
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_json(output_path, orient='records', indent=2, force_ascii=False)
    
    print(f"Saved embeddings to {output_path}")
    sys.stdout.flush()

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract embeddings for 3D visualization from PostgreSQL database"
    )
    
    db = parser.add_argument_group("Database connection")
    db.add_argument("--host", default=os.getenv("PGHOST", "127.0.0.1"), help="Database host")
    db.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")), help="Database port")
    db.add_argument("--user", default=os.getenv("PGUSER", "postgres"), help="Database user")
    db.add_argument("--dbname", default=os.getenv("PGDATABASE", "proj_paper"), help="Database name")
    db.add_argument("--password", default=os.getenv("PGPASSWORD", ""), help="Database password")
    
    opt = parser.add_argument_group("Optimization options")
    opt.add_argument("--max-papers", type=int, default=None, help="Limit number of papers for faster processing (for testing)")
    opt.add_argument("--batch-size", type=int, default=32, help="Batch size for embedding computation")
    
    return parser.parse_args()

def run_embeddings_pipeline(args: argparse.Namespace = None) -> None:
    """Run the complete embeddings extraction pipeline."""
    print("=" * 60)
    print("EMBEDDINGS EXTRACTION PIPELINE")
    print("=" * 60)
    sys.stdout.flush()
    
    if args is None:
        args = parse_args()
    
    if args.password:
        os.environ['PGPASSWORD'] = args.password
    
    start_time = time.time()
    output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'public', 'points_list.json')
    
    df = extract_embeddings_data()
    
    if len(df) > 2000:
        print(f"Large dataset detected ({len(df)} papers). Sampling to 2000 for fast processing...")
        sys.stdout.flush()
        df = df.head(2000)
    
    if args.max_papers and len(df) > args.max_papers:
        print(f"Limiting to {args.max_papers} papers...")
        sys.stdout.flush()
        df = df.head(args.max_papers)
    
    batch_size = args.batch_size if hasattr(args, 'batch_size') and args.batch_size else 64
    
    if len(df) > 0:
        print(f"Final dataset shape: {df.shape}")
        sys.stdout.flush()
        generate_embeddings(df, output_path, batch_size)
    else:
        print("Warning: No valid papers found!")
        sys.stdout.flush()
    
    elapsed = time.time() - start_time
    close_pool()
    
    print(f"\nEmbeddings extraction complete! Time: {elapsed:.1f}s")
    sys.stdout.flush()

if __name__ == "__main__":
    run_embeddings_pipeline()