"""
Tests d'authentification : register, login, refresh, logout, /me.
"""
import pytest


class TestHealth:
    """Tests des endpoints de santé (aucune auth requise)."""

    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["message"] == "Agent IA PMO operationnel"

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestRegister:
    """Tests de l'inscription."""

    def test_register_success(self, client):
        r = client.post("/api/auth/register", json={
            "first_name": "Alice",
            "last_name": "Dupont",
            "email": "alice@pmo.bj",
            "password": "SecurePass123!",
            "role": "pmo"
        })
        assert r.status_code == 201
        body = r.json()
        assert "access_token" in body
        assert body["user"]["email"] == "alice@pmo.bj"
        assert "password" not in body["user"]  # Le mot de passe ne doit JAMAIS être renvoyé

    def test_register_duplicate_email(self, client):
        """Une seconde inscription avec le même email doit échouer (409)."""
        payload = {
            "first_name": "Bob",
            "last_name": "Martin",
            "email": "bob.dupont@pmo.bj",
            "password": "AnotherPass456!",
            "role": "pmo"
        }
        client.post("/api/auth/register", json=payload)  # 1ère inscription
        r = client.post("/api/auth/register", json=payload)  # 2ème = doublon
        assert r.status_code == 409

    def test_register_invalid_email(self, client):
        """Une adresse email invalide doit retourner une erreur 422."""
        r = client.post("/api/auth/register", json={
            "first_name": "Charlie",
            "last_name": "Test",
            "email": "pas-un-email",
            "password": "Pass123!",
            "role": "pmo"
        })
        assert r.status_code == 422


class TestLogin:
    """Tests de la connexion."""

    def test_login_success(self, client):
        # Création préalable du compte
        client.post("/api/auth/register", json={
            "first_name": "David",
            "last_name": "Koffi",
            "email": "david.koffi@pmo.bj",
            "password": "LoginPass789!",
            "role": "pmo"
        })
        r = client.post("/api/auth/login", json={
            "email": "david.koffi@pmo.bj",
            "password": "LoginPass789!"
        })
        assert r.status_code == 200
        assert "access_token" in r.json()
        assert r.json()["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        """Un mauvais mot de passe doit retourner 401."""
        client.post("/api/auth/register", json={
            "first_name": "Eve",
            "last_name": "Test",
            "email": "eve@pmo.bj",
            "password": "CorrectPass!",
            "role": "pmo"
        })
        r = client.post("/api/auth/login", json={
            "email": "eve@pmo.bj",
            "password": "WrongPass999!"
        })
        assert r.status_code == 401

    def test_login_unknown_email(self, client):
        """Un email inconnu doit retourner 401 (pas 404, pour ne pas confirmer l'existence du compte)."""
        r = client.post("/api/auth/login", json={
            "email": "nobody@nowhere.com",
            "password": "SomePass123!"
        })
        assert r.status_code == 401


class TestProtectedRoutes:
    """Vérifie que les routes protégées rejettent les requêtes non authentifiées."""

    def test_get_me_without_auth(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_get_me_with_auth(self, client, auth_headers):
        r = client.get("/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "email" in body
        assert "id" in body
        assert "password" not in body  # Sécurité : pas de mot de passe dans la réponse

    def test_list_projects_without_auth(self, client):
        r = client.get("/api/projects/")
        assert r.status_code == 401