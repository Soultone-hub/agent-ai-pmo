import pytest
from backend.services.rag_service import index_document, search_documents, split_text, get_or_create_collection

TEST_PROJECT_ID = "test_rag_projet"
TEST_DOC_ID = "test_doc_001"
TEST_TEXT = """
Ceci est un document de test pour valider le pipeline RAG.
Le projet comporte plusieurs risques majeurs dont un retard de planning.
Les KPI principaux sont le taux d'avancement et le budget consommé.
Le COPIL se réunit chaque mois pour faire le point sur l'avancement.
"""

def test_split_text():
    chunks = split_text(TEST_TEXT, chunk_size=10, overlap=2)
    assert isinstance(chunks, list)
    assert len(chunks) > 0

def test_split_text_overlap():
    chunks = split_text("un deux trois quatre cinq six sept huit neuf dix onze douze", chunk_size=5, overlap=2)
    assert len(chunks) > 1

def test_index_document():
    n = index_document(TEST_PROJECT_ID, TEST_DOC_ID, TEST_TEXT)
    assert isinstance(n, int)
    assert n > 0

def test_search_documents():
    index_document(TEST_PROJECT_ID, TEST_DOC_ID, TEST_TEXT)
    results = search_documents(TEST_PROJECT_ID, "risques planning")
    assert isinstance(results, list)
    assert len(results) > 0
    assert any("risque" in r.lower() or "planning" in r.lower() for r in results)

def test_search_retourne_3_resultats():
    index_document(TEST_PROJECT_ID, TEST_DOC_ID, TEST_TEXT)
    results = search_documents(TEST_PROJECT_ID, "KPI avancement", n_results=3)
    assert len(results) <= 3

def test_collection_creee():
    collection = get_or_create_collection(TEST_PROJECT_ID)
    assert collection is not None
    assert collection.count() >= 0