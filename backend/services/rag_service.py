import chromadb
from sentence_transformers import SentenceTransformer
from backend.config import settings
import uuid

client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_or_create_collection(project_id: str):
    return client.get_or_create_collection(name=f"project_{project_id}")

def split_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def index_document(project_id: str, document_id: str, text: str):
    collection = get_or_create_collection(project_id)
    chunks = split_text(text)
    embeddings = model.encode(chunks).tolist()
    ids = [str(uuid.uuid4()) for _ in chunks]
    collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=ids,
        metadatas=[{"document_id": document_id} for _ in chunks]
    )
    return len(chunks)

def search_documents(project_id: str, query: str, n_results: int = 3) -> list:
    collection = get_or_create_collection(project_id)
    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results
    )
    return results["documents"][0]