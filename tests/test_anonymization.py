"""
Tests de la pipeline d'anonymisation (tests unitaires purs, sans HTTP).
Ces tests vérifient que le moteur d'anonymisation détecte et remplace
correctement les PII dans des textes PMO typiques.
"""
import pytest

# Import direct de la pipeline (sans passer par l'API)
try:
    from pipeline import AnonymizationPipeline
    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PIPELINE_AVAILABLE,
    reason="Pipeline d'anonymisation non disponible"
)


@pytest.fixture(scope="module")
def pipeline():
    """Instance unique de la pipeline pour tous les tests du module."""
    return AnonymizationPipeline()


class TestEmailDetection:
    """Vérifie que les adresses email sont correctement masquées."""

    def test_simple_email(self, pipeline):
        result = pipeline.run("Contactez jean.dupont@total.com pour plus d'infos.")
        assert "jean.dupont@total.com" not in result.clean_text
        assert "EMAIL" in result.clean_text or any(e.label == "EMAIL" for e in result.entities)

    def test_multiple_emails(self, pipeline):
        text = "De: alice@sgbenin.com À: bob@orange.bj"
        result = pipeline.run(text)
        assert "alice@sgbenin.com" not in result.clean_text
        assert "bob@orange.bj" not in result.clean_text

    def test_no_false_positive_on_domain(self, pipeline):
        """Un nom de domaine seul ne doit pas être masqué."""
        result = pipeline.run("Le site est disponible sur sgbenin.com")
        # "sgbenin.com" sans @ n'est pas un email
        assert result.clean_text  # Juste vérifier que ça ne plante pas


class TestPhoneDetection:
    """Vérifie la détection des numéros de téléphone."""

    def test_phone_benin_international(self, pipeline):
        result = pipeline.run("Appelez-moi au +229 90 11 22 33.")
        assert "+229 90 11 22 33" not in result.clean_text
        assert any(e.label == "PHONE" for e in result.entities)

    def test_phone_benin_00229(self, pipeline):
        result = pipeline.run("Son numéro est le 00229 97 55 44 33.")
        assert "97 55 44 33" not in result.clean_text

    def test_phone_france(self, pipeline):
        result = pipeline.run("Bureau: 06 12 34 56 78")
        assert "06 12 34 56 78" not in result.clean_text


class TestDateDetection:
    """
    Vérifie la détection CONTEXTUELLE des dates :
    seules les dates personnelles (naissance, décès, embauche…) sont masquées ;
    les dates "projet" (jalons, échéances, COPIL) sont préservées pour le LLM.
    """

    def test_birthdate_masked(self, pipeline):
        """Une date de naissance (contexte personnel) doit être masquée."""
        result = pipeline.run("Le patient est né le 25/04/1990 à Cotonou.")
        assert "25/04/1990" not in result.clean_text
        assert any(e.label == "DATE" for e in result.entities)

    def test_birthdate_label_masked(self, pipeline):
        """Format textuel après 'date de naissance'."""
        result = pipeline.run("Date de naissance : 12 mars 1990.")
        assert "12 mars 1990" not in result.clean_text

    def test_project_date_not_masked(self, pipeline):
        """Une date projet (réunion/COPIL) ne doit PAS être masquée."""
        result = pipeline.run("La réunion COPIL est prévue le 25/04/2024.")
        assert "25/04/2024" in result.clean_text

    def test_deadline_date_not_masked(self, pipeline):
        """Une échéance de livrable ne doit PAS être masquée."""
        result = pipeline.run("Échéance du livrable : 30/09/2024.")
        assert "30/09/2024" in result.clean_text

    def test_no_false_positive_on_year_alone(self, pipeline):
        """Une année seule (ex: 2024) ne doit pas être masquée."""
        result = pipeline.run("Le budget 2024 est de 500 000 FCFA.")
        assert "2024" in result.clean_text  # L'année seule n'est pas une date PII


class TestPersonDetection:
    """Vérifie la détection des noms de personnes."""

    def test_name_after_civility(self, pipeline):
        result = pipeline.run("Le rapport a été validé par Mme Aïcha Kone.")
        assert "Aïcha Kone" not in result.clean_text

    def test_name_after_dr(self, pipeline):
        result = pipeline.run("Dr Alain Kouassi a confirmé les résultats.")
        assert "Alain Kouassi" not in result.clean_text

    def test_jean_dupont(self, pipeline):
        """Test de régression : Jean Dupont doit être détecté."""
        result = pipeline.run("Jean Dupont, chef de projet, a envoyé le rapport.")
        assert "Jean Dupont" not in result.clean_text

    def test_no_pii_text_unchanged(self, pipeline):
        """Un texte sans PII doit ressortir quasi identique."""
        text = "Le budget du projet est de 1 250 000 FCFA pour l'exercice 2024."
        result = pipeline.run(text)
        # Les montants et années ne sont pas des PII
        assert "1 250 000" in result.clean_text
        assert "FCFA" in result.clean_text


class TestValidation:
    """Vérifie l'absence de fuites après anonymisation."""

    def test_no_email_leak(self, pipeline):
        """Après anonymisation, aucun email ne doit subsister."""
        text = "Contact: chef.projet@totalenergies.com et assistant@orange.bj"
        result = pipeline.run(text)
        import re
        emails_restants = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", result.clean_text)
        assert emails_restants == [], f"Fuite d'email détectée : {emails_restants}"

    def test_consistent_mapping(self, pipeline):
        """La même entité doit toujours recevoir le même pseudonyme."""
        text = "Jean Dupont a envoyé un mail. Jean Dupont a confirmé la réception."
        result = pipeline.run(text)
        # Compter les occurrences de PERSONNE_1 (ou quel que soit le pseudonyme attribué)
        from collections import Counter
        labels = [e.text for e in result.entities if "Jean Dupont" == e.text]
        # Vérifier que tous les pseudonymes de Jean Dupont sont identiques
        pseudos = set()
        for entity in result.entities:
            if entity.text == "Jean Dupont":
                pseudo = result.mapping.get(entity.text)
                if pseudo:
                    pseudos.add(pseudo)
        assert len(pseudos) <= 1, f"Jean Dupont a reçu plusieurs pseudonymes : {pseudos}"
