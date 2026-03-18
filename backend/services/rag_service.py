import chromadb
from sentence_transformers import SentenceTransformer
from backend.config import settings
from backend.services.parser_service import parse_document
import uuid
import os

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





def index_folder(project_id: str, folder_path: str) -> dict:
    results = {"success": [], "failed": []}
    supported = [".pdf", ".docx", ".xlsx"]
    
    files = [f for f in os.listdir(folder_path) 
             if os.path.splitext(f)[1].lower() in supported]
    
    print(f"{len(files)} documents trouvés dans le dossier")
    
    for filename in files:
        file_path = os.path.join(folder_path, filename)
        try:
            text = parse_document(file_path)
            document_id = str(uuid.uuid4())
            n = index_document(project_id, document_id, text)
            print(f"✅ {filename} — {n} chunks indexés")
            results["success"].append(filename)
        except Exception as e:
            print(f"❌ {filename} — erreur : {e}")
            results["failed"].append(filename)
    
    return results