import requests
import streamlit as st

API_BASE_URL = "http://localhost:8000"

class APIClient:

    def __init__(self):
        self.base_url = API_BASE_URL
        self.session = requests.Session()

    def _handle_response(self, response: requests.Response):
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            st.error(f"Erreur API : {response.status_code} — {response.json().get('detail', str(e))}")
            return None
        except Exception as e:
            st.error(f"Erreur inattendue : {str(e)}")
            return None

    def upload_document(self, project_id: str, file) -> dict:
        response = self.session.post(
            f"{self.base_url}/api/documents/upload",
            params={"project_id": project_id},
            files={"file": (file.name, file.getvalue(), file.type)}
        )
        return self._handle_response(response)

    def list_documents(self, project_id: str) -> list:
        response = self.session.get(
            f"{self.base_url}/api/documents/",
            params={"project_id": project_id}
        )
        result = self._handle_response(response)
        return result.get("documents", []) if result else []

    def analyze_document(self, document_id: str) -> dict:
        response = self.session.post(
            f"{self.base_url}/api/documents/analyze",
            params={"document_id": document_id}
        )
        return self._handle_response(response)

    def delete_document(self, document_id: str) -> bool:
        response = self.session.delete(
            f"{self.base_url}/api/documents/{document_id}"
        )
        result = self._handle_response(response)
        return result is not None

    def extract_risks(self, project_id: str, document_id: str) -> dict:
        response = self.session.post(
            f"{self.base_url}/api/risks/extract",
            params={"project_id": project_id, "document_id": document_id}
        )
        return self._handle_response(response)

    def get_risks(self, project_id: str) -> dict:
        response = self.session.get(
            f"{self.base_url}/api/risks/{project_id}"
        )
        return self._handle_response(response)

    def generate_copil(self, project_id: str, document_id: str) -> dict:
        response = self.session.post(
            f"{self.base_url}/api/copil/generate",
            params={"project_id": project_id, "document_id": document_id}
        )
        return self._handle_response(response)

    def get_copil(self, project_id: str) -> dict:
        response = self.session.get(
            f"{self.base_url}/api/copil/{project_id}"
        )
        return self._handle_response(response)

    def extract_kpis(self, project_id: str, document_id: str) -> dict:
        response = self.session.post(
            f"{self.base_url}/api/kpi/extract",
            params={"project_id": project_id, "document_id": document_id}
        )
        return self._handle_response(response)

    def get_kpis(self, project_id: str) -> dict:
        response = self.session.get(
            f"{self.base_url}/api/kpi/{project_id}"
        )
        return self._handle_response(response)

    def get_kpi_score(self, project_id: str) -> dict:
        response = self.session.get(
            f"{self.base_url}/api/kpi/{project_id}/score"
        )
        return self._handle_response(response)

    def send_chat_message(self, project_id: str, message: str) -> dict:
        response = self.session.post(
            f"{self.base_url}/api/chat/message",
            json={"project_id": project_id, "message": message}
        )
        return self._handle_response(response)

    def get_chat_history(self, project_id: str) -> dict:
        response = self.session.get(
            f"{self.base_url}/api/chat/history/{project_id}"
        )
        return self._handle_response(response)

    def reset_chat(self, project_id: str) -> bool:
        response = self.session.delete(
            f"{self.base_url}/api/chat/reset/{project_id}"
        )
        result = self._handle_response(response)
        return result is not None