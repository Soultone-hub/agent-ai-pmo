from backend.services.llm_service import send_to_groq
from backend.services.rag_service import search_documents
import json

def extract_risks(project_id: str, document_text: str) -> dict:
    prompt_template = open('backend/prompts/risk_prompt.txt').read()
    
    context = search_documents(project_id, "risques problemes contraintes difficultes")
    context_text = "\n".join(context)
    
    full_text = f"{document_text[:2000]}\n\nCONTEXTE ADDITIONNEL:\n{context_text}"
    prompt = prompt_template.replace('{document_text}', full_text)
    
    reponse = send_to_groq(prompt)
    
    try:
        return json.loads(reponse)
    except json.JSONDecodeError:
        reponse_clean = reponse.strip()
        if '```json' in reponse_clean:
            reponse_clean = reponse_clean.split('```json')[1].split('```')[0]
        return json.loads(reponse_clean)