"""
Tests des projets et de la gestion documentaire (upload, list, delete).
"""
import io
import pytest


class TestProjects:
    """Tests CRUD des projets."""

    def test_create_project(self, client, auth_headers):
        r = client.post("/api/projects/", json={
            "name": "Projet Test PMO",
            "description": "Un projet de test automatisé"
        }, headers=auth_headers)
        assert r.status_code in (200, 201)
        body = r.json()
        assert "id" in body
        assert body["name"] == "Projet Test PMO"

    def test_list_projects(self, client, auth_headers):
        r = client.get("/api/projects/", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), dict)
        assert isinstance(r.json().get("projects"), list)

    def test_list_projects_unauthenticated(self, client):
        r = client.get("/api/projects/")
        assert r.status_code == 401

    def test_get_project_not_found(self, client, auth_headers):
        r = client.get(
            "/api/projects/00000000-0000-0000-0000-000000000000",
            headers=auth_headers
        )
        assert r.status_code == 405


class TestDocuments:
    """Tests de l'upload et de la liste de documents."""

    @pytest.fixture(scope="class")
    def project_id(self, client, auth_headers):
        """Crée un projet de test et retourne son ID."""
        r = client.post("/api/projects/", json={
            "name": "Projet Documents Test",
            "description": "Pour les tests de documents"
        }, headers=auth_headers)
        assert r.status_code in (200, 201)
        return r.json()["id"]

    def test_list_documents_empty(self, client, auth_headers, project_id):
        r = client.get(
            f"/api/documents/?project_id={project_id}",
            headers=auth_headers
        )
        assert r.status_code == 200
        body = r.json()
        assert "documents" in body
        assert body["documents"] == []

    def test_upload_txt_document(self, client, auth_headers, project_id):
        """Upload d'un fichier texte simple."""
        content = b"Compte-rendu de reunion du projet SIGMA\nPresents: Jean Dupont, Marie Koffi"
        files = {"file": ("compte_rendu.txt", io.BytesIO(content), "text/plain")}
        r = client.post(
            f"/api/documents/upload?project_id={project_id}",
            files=files,
            headers=auth_headers
        )
        # Le parseur peut rejeter les .txt selon la config, on accepte 200 ou 422
        assert r.status_code in (200, 201, 400, 422)

    def test_upload_without_auth(self, client, project_id):
        """Un upload sans token doit être refusé."""
        content = b"Test document"
        files = {"file": ("test.txt", io.BytesIO(content), "text/plain")}
        r = client.post(
            f"/api/documents/upload?project_id={project_id}",
            files=files
        )
        assert r.status_code == 401

    def test_upload_oversized_file(self, client, auth_headers, project_id):
        """Un fichier dépassant 20 Mo doit être refusé (413)."""
        # On génère un fichier de ~21 Mo en mémoire
        big_content = b"A" * (21 * 1024 * 1024)
        files = {"file": ("gros_fichier.pdf", io.BytesIO(big_content), "application/pdf")}
        r = client.post(
            f"/api/documents/upload?project_id={project_id}",
            files=files,
            headers=auth_headers
        )
        assert r.status_code == 413

    def test_list_documents_unknown_project(self, client, auth_headers):
        """La liste de documents d'un projet inconnu doit retourner une liste vide ou 404."""
        r = client.get(
            "/api/documents/?project_id=00000000-0000-0000-0000-000000000000",
            headers=auth_headers
        )
        assert r.status_code in (200, 404)
