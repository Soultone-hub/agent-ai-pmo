"""
benchmark_pipeline.py — Benchmark de performance de la pipeline d'anonymisation.

Mesure le taux de détection sur des cas réels du contexte PMO Bénin.
Lance avec : python benchmark_pipeline.py

Sortie : rapport détaillé + taux global de réussite.
"""

import sys
import os

# Lancer depuis : c:\agent-ia-pmo\backend_FastAPI\agent-ia-pmo
# ex : .\venv\Scripts\python.exe pipeline\benchmark_pipeline.py
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pipeline import AnonymizationPipeline
from pipeline.config import PipelineConfig, DetectorConfig

# Pipeline sans spaCy (mode offline-first)
_config = PipelineConfig(
    detector=DetectorConfig(spacy_model="__nonexistent__")
)
pipeline = AnonymizationPipeline(config=_config)


# ─────────────────────────────────────────────────────────────────────────────
# Jeux de test — (description, texte_brut, liste_de_valeurs_à_masquer)
# ─────────────────────────────────────────────────────────────────────────────

TEST_CASES = [

    # ── Emails ───────────────────────────────────────────────────────────────
    ("Email simple",
     "Contactez jean.dupont@example.com pour plus d'informations.",
     ["jean.dupont@example.com"]),

    ("Email béninois",
     "Responsable : koffi.amoussa@gouv.bj — Téléphone disponible en cas d'urgence.",
     ["koffi.amoussa@gouv.bj"]),

    ("Deux emails dans un texte",
     "alice@project.bj et bob.manager@bceao.int sont en copie.",
     ["alice@project.bj", "bob.manager@bceao.int"]),

    # ── Téléphones ────────────────────────────────────────────────────────────
    ("Téléphone France",
     "Appelez le 06 12 34 56 78 pour confirmer.",
     ["06 12 34 56 78"]),

    ("Téléphone Bénin international",
     "Contact : +229 01 23 45 67",
     ["+229 01 23 45 67"]),

    ("Téléphone Bénin local 8 chiffres",
     "Mobile : 97 12 34 56",
     ["97 12 34 56"]),

    ("Téléphone Côte d'Ivoire",
     "Référent CI : +225 07 12 34 56 78",
     ["+225 07 12 34 56 78"]),

    ("Téléphone Sénégal",
     "Partenaire Dakar : +221 77 123 45 67",
     ["+221 77 123 45 67"]),

    # ── Noms propres africains ────────────────────────────────────────────────
    ("Nom avec composant tout-majuscule",
     "Le chef de projet AMOUSSA Soultone a validé le livrable.",
     ["AMOUSSA Soultone"]),

    ("Nom inversé (prénom puis NOM)",
     "Rédigé par : Jean KOFFI, Coordinateur PMO.",
     ["Jean KOFFI"]),

    ("Nom avec tiret",
     "Responsable : DOMINGO-GBAGUIDI Rodrigue",
     ["DOMINGO-GBAGUIDI Rodrigue"]),

    ("Deux noms dans un texte",
     "SOUKPE Barnabé et AHOSSOU Marie-Claire sont présents.",
     ["SOUKPE Barnabé", "AHOSSOU Marie-Claire"]),

    # ── IBAN ─────────────────────────────────────────────────────────────────
    ("IBAN France",
     "Virement sur le compte FR7630006000011234567890189.",
     ["FR7630006000011234567890189"]),

    ("IBAN Bénin",
     "IBAN bénéficiaire : BJ89BJ0090150000000001234567",
     ["BJ89BJ0090150000000001234567"]),

    # ── IFU béninois ─────────────────────────────────────────────────────────
    ("IFU après libellé",
     "IFU : 1234567890123 — Société enregistrée au Bénin.",
     ["1234567890123"]),

    ("IFU dans une phrase",
     "L'entreprise (IFU: 9876543210123) a soumis sa candidature.",
     ["9876543210123"]),

    # ── RCCM ─────────────────────────────────────────────────────────────────
    ("RCCM standard",
     "Immatriculée sous RB/COT/2021/B/1234 au registre de commerce.",
     ["RB/COT/2021/B/1234"]),

    ("RCCM format BJ",
     "RCCM : BJ/RCCM/COT/2022/B/5678",
     ["BJ/RCCM/COT/2022/B/5678"]),

    # ── Cartes bancaires ──────────────────────────────────────────────────────
    ("Carte bancaire valide (Luhn)",
     "Paiement effectué avec la carte 4539 1488 0343 6467.",
     ["4539 1488 0343 6467"]),

    # ── Adresse IP ────────────────────────────────────────────────────────────
    ("Adresse IP v4",
     "Accès depuis 192.168.1.100 détecté à 14h32.",
     ["192.168.1.100"]),

    # ── Dates de naissance (contexte personnel) ───────────────────────────────
    ("Date au format JJ/MM/AAAA",
     "Né le 15/06/1982 à Cotonou.",
     ["15/06/1982"]),

    ("Date textuelle",
     "Date de naissance : 24 avril 1975.",
     ["24 avril 1975"]),

    # ── Cas combinés ─────────────────────────────────────────────────────────
    ("Fiche contact complète",
     "Nom : GBAGUIDI Roméo\nEmail : romeo.gbaguidi@pmo.bj\nTél : +229 01 97 12 34\nIFU : 1234567890123",
     ["GBAGUIDI Roméo", "romeo.gbaguidi@pmo.bj", "+229 01 97 12 34", "1234567890123"]),

    ("Document PMO réaliste",
     (
         "RAPPORT DE SYNTHÈSE — Projet Infrastructure Numérique\n"
         "Chef de projet : SOUKPE Barnabé (soukpe@gouv.bj)\n"
         "Budget global : 450 000 000 FCFA\n"
         "Taux d'avancement : 67%\n"
         "Contact : +229 01 23 45 67\n"
         "Date de mise à jour : 15/04/2026\n"
         "Signataire : AHOSSOU Marie-Claire\n"
     ),
     ["SOUKPE Barnabé", "soukpe@gouv.bj", "+229 01 23 45 67", "AHOSSOU Marie-Claire"]),

    # ── Cas négatifs (aucune PII — le texte ne doit PAS être modifié) ────────
    ("Texte PMO sans PII",
     "Le budget total du projet est de 500 000 FCFA pour le T3 2026.",
     []),  # liste vide = rien à masquer

    ("Section de rapport sans PII",
     "Phase 2 — Déploiement : 3 jalons planifiés, taux de réalisation 87%.",
     []),

    ("Termes techniques seuls",
     "COPIL du 15/04/2026 : validation des livrables Phase 1 et Phase 2.",
     []),   # La date 15/04/2026 EST une PII — résultat attendu : vide SI on ne masque pas les dates
             # Ajustement : on accepte que les dates soient masquées (c'est correct)
]


# ─────────────────────────────────────────────────────────────────────────────
# Moteur de benchmark
# ─────────────────────────────────────────────────────────────────────────────

def run_benchmark():
    total_entities = 0
    detected = 0
    false_positives = 0
    results = []

    RESET  = "\033[0m"
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    BOLD   = "\033[1m"

    print(f"\n{BOLD}{'─'*70}{RESET}")
    print(f"{BOLD}  BENCHMARK PIPELINE D'ANONYMISATION — Contexte PMO Bénin{RESET}")
    print(f"{BOLD}{'─'*70}{RESET}\n")

    for i, (description, text, expected_pii) in enumerate(TEST_CASES, 1):
        result = pipeline.run(text)
        clean  = result.clean_text

        # Cas négatif : texte sans PII — on vérifie juste qu'il n'y a pas de faux positifs
        # (sauf les dates qui peuvent légitimement être masquées dans ce contexte)
        if not expected_pii:
            # Faux positifs = termes PMO techniques masqués à tort
            pmo_terms = ["Budget", "Phase", "COPIL", "Jalon", "FCFA",
                         "livrable", "taux", "avancement", "réalisation"]
            fp_found = [t for t in pmo_terms if t not in clean and t.lower() in text.lower()]
            if fp_found:
                false_positives += len(fp_found)
                status = f"{RED}✗ FAUX POSITIF{RESET}"
                detail = f"Termes PMO effacés à tort : {fp_found}"
            else:
                status = f"{GREEN}✓ OK (aucun FP){RESET}"
                detail = "Aucune PII ni faux positif"
            print(f"  [{i:02d}] {description}")
            print(f"        {status} — {detail}")
            results.append(("NEG", description, True, fp_found))
            print()
            continue

        # Cas positif : vérifier que chaque PII attendue est bien masquée
        case_ok = True
        missed = []
        for pii in expected_pii:
            total_entities += 1
            if pii not in clean:
                detected += 1
                icon = f"{GREEN}✓{RESET}"
            else:
                missed.append(pii)
                case_ok = False
                icon = f"{RED}✗{RESET}"
            print(f"  [{i:02d}] {description}")
            print(f"        {icon} PII attendue : {pii!r}")

        if missed:
            print(f"        {RED}→ Non masquées : {missed}{RESET}")
        print()
        results.append(("POS", description, case_ok, missed))

    # ── Synthèse ──────────────────────────────────────────────────────────────
    if total_entities > 0:
        recall = detected / total_entities * 100
    else:
        recall = 100.0

    pos_cases = [r for r in results if r[0] == "POS"]
    neg_cases = [r for r in results if r[0] == "NEG"]
    cases_ok  = sum(1 for r in pos_cases if r[2])
    total_pos = len(pos_cases)
    case_rate = cases_ok / total_pos * 100 if total_pos > 0 else 100.0

    print(f"{BOLD}{'─'*70}{RESET}")
    print(f"{BOLD}  RÉSULTATS GLOBAUX{RESET}")
    print(f"{'─'*70}")
    print(f"  Entités PII détectées     : {detected}/{total_entities}  ({recall:.1f}%)")
    print(f"  Cas positifs réussis      : {cases_ok}/{total_pos}  ({case_rate:.1f}%)")
    print(f"  Faux positifs PMO         : {false_positives}")

    overall = (recall * 0.7 + case_rate * 0.3)
    color = GREEN if overall >= 95 else YELLOW if overall >= 80 else RED
    print(f"\n  {BOLD}Taux global de réussite   : {color}{overall:.1f}%{RESET}")

    if overall >= 95:
        print(f"  {GREEN}🎯 OBJECTIF ATTEINT (≥ 95%){RESET}")
    elif overall >= 80:
        print(f"  {YELLOW}⚠  Objectif non atteint — améliorations nécessaires{RESET}")
    else:
        print(f"  {RED}✗  Pipeline insuffisante{RESET}")

    print(f"{'─'*70}\n")

    return overall


if __name__ == "__main__":
    score = run_benchmark()
    sys.exit(0 if score >= 95 else 1)
