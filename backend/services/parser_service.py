import fitz  # PyMuPDF
from docx import Document
from openpyxl import load_workbook
import os
import email
from email import policy

def parse_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

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