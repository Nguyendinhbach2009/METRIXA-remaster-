import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import sys
import re
import html
import ast
from sqlalchemy import create_engine
from sklearn.manifold import TSNE

# -------------------------
# 1. Load data from PostgreSQL Database
# -------------------------
def load_data_from_db(db_uri: str) -> pd.DataFrame:
    """Load data directly from PostgreSQL using the core schema."""
    print("Connecting to the database...")
    try:
        engine = create_engine(db_uri)
        
        # Truy vấn kết hợp thông tin bài báo và nhóm các tác giả thành chuỗi string
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
        print(f"Summary: Loaded {len(df)} papers from the database.")
        
        # Lọc bỏ các bài báo không có tác giả (nếu đó là logic mong muốn của bạn trước đây)
        df = df.dropna(subset=['authors'])
        print(f"Valid papers with authors: {len(df)}")
        
        return df

    except Exception as e:
        print(f"Database error: {e}")
        sys.exit(1)

# Cấu hình Database URI (nên sử dụng biến môi trường trong thực tế)
# Format: postgresql://[user]:[password]@[host]:[port]/[database_name]
DB_URI = os.getenv("DATABASE_URL", "postgresql://postgres:Quangtrung1234!@localhost:5433/proj_paper")

df = load_data_from_db(DB_URI)

if len(df) == 0:
    print("Warning: No valid papers found in the database!")
    sys.exit(0)

# -------------------------
# 2. Data Cleaning & Parsing
# -------------------------
def clean_scientific_text(text: str) -> str:
    """
    Clean text while preserving essential scientific content.
    """
    if not isinstance(text, str):
        return ""

    text = html.unescape(text)
    text = re.sub(r"\$[^$]*\$", " ", text)              # Inline math
    text = re.sub(r"\\\[.*?\\\]", " ", text)            # Display math
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
    """
    Xử lý linh hoạt do dữ liệu trả về từ PostgreSQL JSONB thường đã là object list.
    """
    subfields = []
    
    if isinstance(x, str):
        try:
            lst = ast.literal_eval(x)
            if isinstance(lst, list):
                subfields = [str(s) for s in lst]
        except:
            pass
    elif isinstance(x, list):
        subfields = [str(s) for s in x]

    # Prepend the main field at the start if given
    if main_field is not None:
        if isinstance(main_field, str):
            try:
                lst = ast.literal_eval(main_field)
                if isinstance(lst, list):
                    for field in lst:
                        subfields.insert(0, str(field))
            except:
                pass
        elif isinstance(main_field, list):
            for field in reversed(main_field): # Dùng reversed để giữ đúng thứ tự khi insert(0)
                subfields.insert(0, str(field))

    return subfields

def concat_strings(x):
    if isinstance(x, str):
        try:
            lst = ast.literal_eval(x)
            if isinstance(lst, list):
                return ", ".join(str(s) for s in lst)
        except:
            return ""
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
    if not isinstance(field_list, list) or len(field_list) == 0:
        return "", [] 

    main = field_list[0]
    related_list = field_list[1:] if len(field_list) > 1 else []
    related = concat_strings(related_list)
    return main, related

df['original_field'], df['related_fields'] = zip(*df['fields'].apply(split_fields))

# -------------------------
# 3. Model Embedding
# -------------------------
print("Loading Embedding Model...")
model = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")

def embed_subfields(subfields):
    if not subfields:
        return np.zeros(model.get_sentence_embedding_dimension())
    embeddings = model.encode(subfields)
    return np.mean(embeddings, axis=0)

from tqdm import tqdm
import numpy as np

print("Extracting unique subfields...")
# 1. Trích xuất tất cả các subfields duy nhất từ toàn bộ dataset
all_subfields = set()
for fields in df['predicted_fieldsOfStudy']:
    if isinstance(fields, list):
        all_subfields.update(fields)

unique_subfields = list(all_subfields)
print(f"Found {len(unique_subfields)} unique subfields out of 191k papers.")

# 2. Sinh embedding theo lô (Batch Processing) 
# Tham số show_progress_bar=True sẽ hiển thị thanh tải tiến độ trực quan
print("Generating Embeddings for unique subfields...")
unique_embeddings = model.encode(
    unique_subfields, 
    batch_size=256, # Tăng lên 512 hoặc 1024 nếu có GPU VRAM lớn
    show_progress_bar=True
)

# 3. Tạo Hash Map (Dictionary) để tra cứu O(1)
print("Mapping embeddings back to papers...")
embedding_dict = {
    subfield: emb for subfield, emb in zip(unique_subfields, unique_embeddings)
}

dim_size = model.get_sentence_embedding_dimension()
zero_vector = np.zeros(dim_size)

# 4. Hàm ánh xạ và tính trung bình (rất nhanh vì chỉ tra cứu Dict và dùng Numpy)
def get_mean_embedding(subfields):
    if not subfields:
        return zero_vector
    
    # Lấy vector cho từng subfield từ Dictionary
    vectors = [embedding_dict[f] for f in subfields if f in embedding_dict]
    
    if not vectors:
        return zero_vector
        
    return np.mean(vectors, axis=0)

# Kích hoạt thanh tiến trình cho Pandas apply
tqdm.pandas(desc="Calculating mean vectors")
df['embedding'] = df['predicted_fieldsOfStudy'].progress_apply(get_mean_embedding)

paper_vectors = np.stack(df['embedding'].values)
print(f"Finished generating paper vectors. Shape: {paper_vectors.shape}")
# -------------------------
# 4. t-SNE Dimensionality Reduction
# -------------------------
print("Running t-SNE...")
tsne = TSNE(
    n_components=3,
    metric='cosine',
    perplexity=20,
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

# -------------------------
# 5. Export Data
# -------------------------
df = df.drop(columns=["embedding", "x", "y", "z", "predicted_fieldsOfStudy", "main_fields", "fields"])

output_path = "/home/dtth/proj_paper/website/public/points_list.json"
os.makedirs(os.path.dirname(output_path), exist_ok=True)

df.to_json(output_path, orient='records') 
print(f"Data successfully exported to {output_path}")