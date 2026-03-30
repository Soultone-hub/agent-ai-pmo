import chromadb
import logging
import uuid
import os
from sentence_transformers import SentenceTransformer
from backend.config import settings
from backend.services.parser_service import parse_document

logger = logging.getLogger(__name__)

client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
model = SentenceTransformer('all-MiniLM-L6-v2', cache_folder="./models_cache")


def get_or_create_collection(project_id: str):
    return client.get_or_create_collection(name=f"project_{project_id}")


def split_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def index_document(project_id: str, document_id: str, text: str) -> int:
    collection = get_or_create_collection(project_id)
    chunks = split_text(text)
    if not chunks:
        return 0
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
    count = collection.count()
    if count == 0:
        return []
    n_results = min(n_results, count)
    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results
    )
    docs = results.get("documents", [[]])
    return docs[0] if docs else []


def index_folder(project_id: str, folder_path: str) -> dict:
    results = {"success": [], "failed": []}
    supported = {".pdf", ".docx", ".xlsx"}

    files = [f for f in os.listdir(folder_path)
             if os.path.splitext(f)[1].lower() in supported]

    logger.info(f"{len(files)} documents trouvés dans le dossier")

    for filename in files:
        file_path = os.path.join(folder_path, filename)
        try:
            text = parse_document(file_path)
            document_id = str(uuid.uuid4())
            n = index_document(project_id, document_id, text)
            logger.info(f"{filename} — {n} chunks indexés")
            results["success"].append(filename)
        except Exception as e:
            logger.error(f"{filename} — erreur : {e}")
            results["failed"].append(filename)

    return results




def search_in_document(project_id: str, document_id: str, query: str, n_results: int = 5) -> list:
    """Recherche RAG ciblée sur un seul document via son document_id."""
    collection = get_or_create_collection(project_id)
    count = collection.count()
    if count == 0:
        return []
    n_results = min(n_results, count)
    query_embedding = model.encode([query]).tolist()
    try:
        results = collection.query(
            query_embeddings=query_embedding,
            where={"document_id": document_id},
            n_results=n_results
        )
        docs = results.get("documents", [[]])
        return docs[0] if docs else []
    except Exception as e:
        logger.warning(f"Recherche ciblee echouee pour doc {document_id}, fallback global : {e}")
        return search_documents(project_id, query, n_results)


def search_in_documents(project_id: str, document_ids: list, query: str, n_results_per_doc: int = 3) -> list:
    """Recherche RAG sur plusieurs documents cibles — fusionne les chunks pertinents de chacun."""
    if not document_ids:
        return search_documents(project_id, query, n_results_per_doc)

    all_chunks = []
    for document_id in document_ids:
        chunks = search_in_document(project_id, document_id, query, n_results_per_doc)
        all_chunks.extend(chunks)

    if not all_chunks:
        logger.warning("Aucun chunk trouve dans les documents cibles, fallback global")
        return search_documents(project_id, query, n_results_per_doc)

    return all_chunks