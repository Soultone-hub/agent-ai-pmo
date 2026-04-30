import fitz  # PyMuPDF
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation
import os
import email
from email import policy

def parse_pdf(file_path: str) -> str:
    try:
        import pymupdf4llm
        # Extrait tout le PDF directement au format Markdown (garde les tableaux et la structure !)
        md_text = pymupdf4llm.to_markdown(file_path)
        return md_text
    except Exception as e:
        # Fallback de sécurité (pour Python 3.14 où networkx/pymupdf4llm plante à l'importation)
        import fitz
        doc = fitz.open(file_path)
        text_parts = []
        
        for page in doc:
            # 1. Extraction manuelle et propre des tableaux (Native PyMuPDF)
            tables = page.find_tables()
            if tables:
                for table in tables:
                    table_data = table.extract()
                    if not table_data or len(table_data) < 2: 
                        continue
                        
                    md_table = "\n\n"
                    for i, row in enumerate(table_data):
                        # Nettoyage des cellules (retrait des retours à la ligne internes)
                        clean_row = [str(cell).replace("\n", " ").strip() if cell else "" for cell in row]
                        md_table += "| " + " | ".join(clean_row) + " |\n"
                        # Ajout du séparateur Markdown après l'en-tête
                        if i == 0:
                            md_table += "|" + "|".join(["---" for _ in row]) + "|\n"
                    text_parts.append(md_table + "\n")
            
            # 2. Extraction du reste du texte de la page
            text_parts.append(page.get_text())
            
        return "\n".join(text_parts)

def parse_docx(file_path: str) -> str:
    doc = Document(file_path)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def parse_xlsx(file_path: str) -> str:
    wb = load_workbook(file_path)
    text = ""
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        text += f"Feuille: {sheet}\n"
        for row in ws.iter_rows(values_only=True):
            row_text = " | ".join([str(cell) for cell in row if cell is not None])
            if row_text:
                text += row_text + "\n"
    return text

def parse_pptx(file_path: str) -> str:
    """Extrait le texte de toutes les diapositives d'un fichier PPTX."""
    prs = Presentation(file_path)
    text = ""
    for slide_num, slide in enumerate(prs.slides, start=1):
        text += f"\n--- Diapositive {slide_num} ---\n"
        for shape in slide.shapes:
            # Titre et contenus texte
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = para.text.strip()
                    if line:
                        text += line + "\n"
            # Tables
            if shape.has_table:
                for row in shape.table.rows:
                    row_text = " | ".join(
                        cell.text.strip() for cell in row.cells if cell.text.strip()
                    )
                    if row_text:
                        text += row_text + "\n"
        # Notes du présentateur
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                text += f"[Notes] {notes}\n"
    return text


def parse_document(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return parse_pdf(file_path)
    elif ext == ".docx":
        return parse_docx(file_path)
    elif ext == ".xlsx":
        return parse_xlsx(file_path)
    elif ext == ".eml":
        return parse_eml(file_path)
    elif ext == ".pptx":
        return parse_pptx(file_path)
    elif ext == ".ppt":
        raise ValueError("Le format .ppt (PowerPoint ancien) n'est pas supporté. Convertissez en .pptx.")
    else:
        raise ValueError(f"Format non supporté: {ext}")
    

def parse_eml(file_path: str) -> str:
    with open(file_path, 'rb') as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    
    text = f"De: {msg['from']}\n"
    text += f"À: {msg['to']}\n"
    text += f"Sujet: {msg['subject']}\n"
    text += f"Date: {msg['date']}\n\n"
    
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                text += part.get_content()
    else:
        text += msg.get_content()
    
    return text