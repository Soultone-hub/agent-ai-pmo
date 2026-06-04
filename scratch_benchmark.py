import time
import os
import sys

# Ajouter le chemin racine pour importer correctement
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.parser_service import parse_pdf, parse_docx, parse_xlsx
from backend.services.anonymization_service import anonymize

print("==================================================")
print("   BENCHMARK - RÉSULTATS CONCRETS DU PROTOTYPE   ")
print("==================================================")

# 1. Test des parsers de documents
samples_dir = os.path.join("tests", "samples")
pdf_path = os.path.join(samples_dir, "test.pdf")
docx_path = os.path.join(samples_dir, "test.docx")
xlsx_path = os.path.join(samples_dir, "test.xlsx")

print("\n--- 1. PARSING DES DOCUMENTS (Extraction de Texte) ---")

if os.path.exists(pdf_path):
    start = time.perf_counter()
    pdf_text = parse_pdf(pdf_path)
    end = time.perf_counter()
    print(f"[PDF]  Parsing '{pdf_path}' ({os.path.getsize(pdf_path)/1024:.1f} Ko) en {end - start:.4f} s.")
    print(f"       -> Extrait : {len(pdf_text)} caractères, {len(pdf_text.split())} mots.")
else:
    print(f"[PDF]  Fichier {pdf_path} introuvable.")

if os.path.exists(docx_path):
    start = time.perf_counter()
    docx_text = parse_docx(docx_path)
    end = time.perf_counter()
    print(f"[DOCX] Parsing '{docx_path}' ({os.path.getsize(docx_path)/1024:.1f} Ko) en {end - start:.4f} s.")
    print(f"       -> Extrait : {len(docx_text)} caractères, {len(docx_text.split())} mots.")
else:
    print(f"[DOCX] Fichier {docx_path} introuvable.")

if os.path.exists(xlsx_path):
    start = time.perf_counter()
    xlsx_text = parse_xlsx(xlsx_path)
    end = time.perf_counter()
    print(f"[XLSX] Parsing '{xlsx_path}' ({os.path.getsize(xlsx_path)/1024:.1f} Ko) en {end - start:.4f} s.")
    print(f"       -> Extrait : {len(xlsx_text)} caractères, {len(xlsx_text.split())} mots.")
else:
    print(f"[XLSX] Fichier {xlsx_path} introuvable.")


# 2. Test de l'anonymisation locale
print("\n--- 2. ANONYMISATION LOCALE APDP ---")
test_text = """
Bonjour,
Voici le compte-rendu du projet SIGMA.
Le chef de projet, M. Jean Dupont (email: jean.dupont@orange.bj, tel: +229 97 12 34 56), a validé le budget.
La coordinatrice adjointe est Mme ALABA Sophie (sophie.alaba@sgbenin.com) basée à Cotonou.
Le planning a été approuvé par le Dr Alain Kouassi le 15/06/2023.
Les prochaines étapes seront pilotées par M. Gbaguidi d'ici le 25 août 2024.
Le budget total est de 45 000 000 FCFA.
"""

print(f"Taille du texte test : {len(test_text)} caractères, {len(test_text.split())} mots.")

start = time.perf_counter()
clean_text, mapping = anonymize(test_text)
end = time.perf_counter()

print(f"Temps de traitement de l'anonymisation : {end - start:.4f} s.")
print("\nTexte nettoyé :")
print("--------------------------------------------------")
print(clean_text.strip())
print("--------------------------------------------------")
print("Cartographie d'anonymisation (reverse map) :")
for k, v in mapping.items():
    print(f"  {k} -> {v}")

print("==================================================")
