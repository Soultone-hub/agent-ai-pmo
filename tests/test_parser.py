import pytest
import os
from backend.services.parser_service import parse_document, parse_pdf, parse_docx, parse_xlsx

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), 'samples')

def test_parse_pdf():
    path = os.path.join(SAMPLES_DIR, 'test.pdf')
    if not os.path.exists(path):
        pytest.skip("Fichier test.pdf absent")
    result = parse_pdf(path)
    assert isinstance(result, str)
    assert len(result) > 0

def test_parse_docx():
    path = os.path.join(SAMPLES_DIR, 'test.docx')
    if not os.path.exists(path):
        pytest.skip("Fichier test.docx absent")
    result = parse_docx(path)
    assert isinstance(result, str)
    assert len(result) > 0

def test_parse_xlsx():
    path = os.path.join(SAMPLES_DIR, 'test.xlsx')
    if not os.path.exists(path):
        pytest.skip("Fichier test.xlsx absent")
    result = parse_xlsx(path)
    assert isinstance(result, str)
    assert len(result) > 0

def test_format_non_supporte():
    with pytest.raises(ValueError):
        parse_document('fichier.mp4')

def test_parse_pdf_reel():
    path = 'C:/Users/Deusexi/Downloads/Cahier_des_Charges_Appel_a_innovation.pdf'
    if not os.path.exists(path):
        pytest.skip("Fichier réel absent")
    result = parse_pdf(path)
    assert isinstance(result, str)
    assert len(result) > 100