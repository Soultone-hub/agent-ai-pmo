from groq import Groq
from backend.config import settings

client = Groq(api_key=settings.GROQ_API_KEY)

def send_to_groq(prompt: str, system_prompt: str = "Tu es un assistant expert en gestion de projets strategiques.") -> str:
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2048
        )
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"Erreur Groq : {str(e)}")