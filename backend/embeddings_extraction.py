import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import sys
import re
import html
import ast
from sqlalchemy import create_engine
import umap
from tqdm import tqdm

# -------------------------
# 1. Load data from PostgreSQL Database
# -------------------------
def load_data_from_db(db_uri: str) -> pd.DataFrame:
    """Đọc dữ liệu trực tiếp từ PostgreSQL thông qua Schema Core."""
    print("Connecting to the database...")
    try:
        engine = create_engine(db_uri)
        
        # Lấy thông tin bài báo và gộp danh sách tác giả ngay trên database
        query = """
        SELECT 
            p.paper_id AS "paperId",
            p.title,
            p.predicted_fields AS "predicted_fieldsOfStudy",
            p.main_fields,
            p.pdf_urls,
            string_agg(DISTINCT a.name, ', ') AS authors
        FROM core.papers p
        LEFT JOIN core.paper_authors pa ON p.paper_id = pa.paper_id
        LEFT JOIN core.authors a ON pa.author_id = a.author_id
        GROUP BY 
            p.paper_id, 
            p.title, 
            p.predicted_fields, 
            p.main_fields, 
            p.pdf_urls;
        """
        
        print("Executing query and fetching data...")
        df = pd.read_sql(query, engine)
        print(f"Loaded {len(df)} papers from the database.")
        
        # Lọc bỏ bài báo không có tác giả
        df = df.dropna(subset=['authors'])
        print(f"Valid papers with authors: {len(df)}")
        
        return df

    except Exception as e:
        print(f"Database error: {e}")
        sys.exit(1)

# Thay đổi DATABASE_URL theo cấu hình thực tế của bạn
DB_URI = os.getenv("DATABASE_URL", "postgresql://postgres:Quangtrung1234!@localhost:5433/proj_paper")
df = load_data_from_db(DB_URI)

if len(df) == 0:
    print("Warning: No valid papers found in the database!")
    sys.exit(0)

# -------------------------
# 2. Data Cleaning & Parsing
# -------------------------
print("Cleaning and parsing data...")

def clean_scientific_text(text: str) -> str:
    """Làm sạch văn bản khoa học, giữ lại các thuật ngữ cần thiết."""
    if not isinstance(text, str): return ""
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
    return text.strip()

df['title'] = df['title'].apply(clean_scientific_text)

def parse_subfields(x, main_field=None):
    """Parse JSONB list từ PostgreSQL."""
    subfields = []
    if isinstance(x, str):
        try:
            lst = ast.literal_eval(x)
            if isinstance(lst, list): subfields = [str(s) for s in lst]
        except: pass
    elif isinstance(x, list):
        subfields = [str(s) for s in x]

    if main_field is not None:
        if isinstance(main_field, str):
            try:
                lst = ast.literal_eval(main_field)
                if isinstance(lst, list):
                    for field in lst: subfields.insert(0, str(field))
            except: pass
        elif isinstance(main_field, list):
            for field in reversed(main_field):
                subfields.insert(0, str(field))
    return subfields

def concat_strings(x):
    if isinstance(x, str):
        try:
            lst = ast.literal_eval(x)
            if isinstance(lst, list): return ", ".join(str(s) for s in lst)
        except: return ""
    elif isinstance(x, list):
        return ", ".join(str(s) for s in x)
    return ""

df['Subfields'] = df['predicted_fieldsOfStudy'].apply(concat_strings)
df['fields'] = df.apply(lambda row: parse_subfields(row['main_fields']), axis=1)
df['predicted_fieldsOfStudy'] = df.apply(
    lambda row: parse_subfields(row['predicted_fieldsOfStudy'], main_field=row['main_fields']), 
    axis=1
)
df['pdf_urls'] = df['pdf_urls'].apply(concat_strings)

def split_fields(field_list):
    if not isinstance(field_list, list) or len(field_list) == 0: return "", [] 
    main = field_list[0]
    related = concat_strings(field_list[1:] if len(field_list) > 1 else [])
    return main, related

df['original_field'], df['related_fields'] = zip(*df['fields'].apply(split_fields))

# -------------------------
# 3. Model Embedding (Optimized with Batch Processing)
# -------------------------
print("Loading Embedding Model...")
model = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")

print("Extracting unique subfields for batch embedding...")
all_subfields = set()
for fields in df['predicted_fieldsOfStudy']:
    if isinstance(fields, list):
        all_subfields.update(fields)

unique_subfields = list(all_subfields)
print(f"Found {len(unique_subfields)} unique subfields. Generating embeddings...")

# Sinh embedding cho tập unique subfields
unique_embeddings = model.encode(unique_subfields, batch_size=256, show_progress_bar=True)

# Khởi tạo Dictionary map
embedding_dict = {subfield: emb for subfield, emb in zip(unique_subfields, unique_embeddings)}
zero_vector = np.zeros(model.get_sentence_embedding_dimension())

def get_mean_embedding(subfields):
    if not subfields: return zero_vector
    vectors = [embedding_dict[f] for f in subfields if f in embedding_dict]
    if not vectors: return zero_vector
    return np.mean(vectors, axis=0)

tqdm.pandas(desc="Mapping embeddings back to papers")
df['embedding'] = df['predicted_fieldsOfStudy'].progress_apply(get_mean_embedding)

paper_vectors = np.stack(df['embedding'].values)

# -------------------------
# 4. UMAP Dimensionality Reduction (3D)
# -------------------------
print("Running UMAP dimensionality reduction (Target: 3D)...")
# Cấu hình UMAP
reducer = umap.UMAP(
    n_components=3,         # Giảm xuống 3 chiều cho trực quan hóa 3D
    metric='cosine',        # Cosine distance phù hợp nhất với text embeddings
    n_neighbors=15,         # Kích thước vùng lân cận cục bộ (local neighborhood)
    min_dist=0.1,           # Khoảng cách tối thiểu giữa các điểm để tránh chồng lấn
    random_state=42,        # Giữ kết quả cố định qua các lần chạy
    n_jobs=-1               # Sử dụng đa luồng CPU
)

embeddings_3d = reducer.fit_transform(paper_vectors)

# Gán tọa độ thực
df['x'] = embeddings_3d[:, 0]
df['y'] = embeddings_3d[:, 1]
df['z'] = embeddings_3d[:, 2]

# Thêm nhiễu ngẫu nhiên (Jitter) để phân tách các điểm trùng lặp
rng = np.random.default_rng(seed=42)
JITTER_SCALE = 0.3
df['x_vis'] = df['x'] + rng.normal(scale=JITTER_SCALE, size=len(df))
df['y_vis'] = df['y'] + rng.normal(scale=JITTER_SCALE, size=len(df))
df['z_vis'] = df['z'] + rng.normal(scale=JITTER_SCALE, size=len(df))

# -------------------------
# 5. Data Export
# -------------------------
print("Exporting data for website visualization...")
# Xóa các cột không cần thiết cho frontend để giảm dung lượng file
columns_to_drop = ["embedding", "x", "y", "z", "predicted_fieldsOfStudy", "main_fields", "fields"]
df = df.drop(columns=columns_to_drop)

output_path = "../points_list.json"
os.makedirs(os.path.dirname(output_path), exist_ok=True)

# orient='records' tạo định dạng danh sách các object chuẩn [{}, {}] cho Javascript
df.to_json(output_path, orient='records', force_ascii=False) 
print(f"Thành công! Dữ liệu đã được xuất ra: {output_path}")