import chromadb
import logging
import uuid
import os
from sentence_transformers import SentenceTransformer
from backend.config import settings
from backend.services.parser_service import parse_document

# Forcer le mode hors-ligne absolu pour HuggingFace et Transformers
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

logger = logging.getLogger(__name__)

# Désactiver la télémétrie de ChromaDB qui peut bloquer le démarrage sans internet
chroma_settings = chromadb.config.Settings(anonymized_telemetry=False)
client = chromadb.PersistentClient(path=settings.CHROMA_PATH, settings=chroma_settings)

# Résolution dynamique du chemin local absolu du modèle pour contourner les bugs de connexion de transformers
model_name = "paraphrase-multilingual-MiniLM-L12-v2"
model_dir = f"models--sentence-transformers--{model_name}"
snapshots_dir = os.path.join("./models_cache", model_dir, "snapshots")

# Par défaut on essaie avec le nom du modèle (sera utilisé lors du premier téléchargement)
model_path = model_name

# S'il est déjà téléchargé, on trouve le dossier de snapshot local et on pointe directement dessus
if os.path.exists(snapshots_dir):
    snapshots = os.listdir(snapshots_dir)
    if snapshots:
        # On prend le premier snapshot trouvé (son hash)
        model_path = os.path.join(snapshots_dir, snapshots[0])

# Chargement du modèle (100% hors ligne si le model_path est un chemin local)
model = SentenceTransformer(model_path, cache_folder="./models_cache", local_files_only=True)


def get_or_create_collection(project_id: str):
    return client.get_or_create_collection(name=f"project_{project_id}")


def split_text(text: str, chunk_size: int = 1500, overlap: int = 150) -> list:
    """
    Découpage sémantique récursif similaire à RecursiveCharacterTextSplitter.
    Tente de découper par paragraphes, puis par phrases, puis par mots,
    pour respecter la limite de `chunk_size` caractères tout en gardant le sens.
    """
    separators = ["\n\n", "\n", ". ", " ", ""]
    
    def _split(text_to_split: str, current_separators: list) -> list:
        # Trouver le premier séparateur présent dans le texte
        separator = current_separators[-1]
        new_separators = []
        for i, sep in enumerate(current_separators):
            if sep == "" or sep in text_to_split:
                separator = sep
                new_separators = current_separators[i + 1:]
                break
                
        # Diviser le texte
        splits = text_to_split.split(separator) if separator else list(text_to_split)
        
        # Reconstruire les chunks en respectant la taille maximale
        chunks = []
        current_chunk = []
        current_length = 0
        
        for s in splits:
            if not s.strip():
                continue
                
            # Si un segment est toujours trop grand, on le re-divise récursivement
            if len(s) > chunk_size and new_separators:
                if current_chunk:
                    chunks.append(separator.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                chunks.extend(_split(s, new_separators))
                continue
                
            # Test si l'ajout du segment dépasse la taille autorisée
            new_len = current_length + len(s) + (len(separator) if current_chunk else 0)
            if new_len > chunk_size and current_chunk:
                # Sauvegarder le chunk actuel
                chunks.append(separator.join(current_chunk))
                
                # Gérer le chevauchement (overlap)
                overlap_chunk = []
                overlap_len = 0
                for c in reversed(current_chunk):
                    if overlap_len + len(c) <= overlap:
                        overlap_chunk.insert(0, c)
                        overlap_len += len(c) + len(separator)
                    else:
                        break
                current_chunk = overlap_chunk
                current_chunk.append(s)
                current_length = sum(len(c) for c in current_chunk) + len(separator) * (max(0, len(current_chunk) - 1))
            else:
                current_chunk.append(s)
                current_length += len(s) + (len(separator) if current_chunk else 0)
                
        if current_chunk:
            chunks.append(separator.join(current_chunk))
            
        return chunks

    # Lancer le découpage
    final_chunks = _split(text, separators)
    
    # Restauration de la ponctuation pour le séparateur ". "
    if ". " in separators:
        for i in range(len(final_chunks)):
            if not final_chunks[i].endswith(".") and not final_chunks[i].endswith("\n"):
                final_chunks[i] += "."
                
    return final_chunks



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