import streamlit as st
import time
import requests
import urllib.parse
import re
from google import genai

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def genera_testo_gemini(prompt_list):
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_list)
        return response.text
    except Exception as e:
        st.error(f"Errore AI: {e}")
        return ""

def chat_professore_gemini(system_prompt, messaggi_chat):
    prompt_completo = system_prompt + "\n\n--- CRONOLOGIA ---\n"
    for msg in messaggi_chat:
        ruolo = "Professore" if msg["ruolo"] == "assistant" else "Studente"
        prompt_completo += f"{ruolo}: {msg['contenuto']}\n"
    prompt_completo += "Professore: "
    return genera_testo_gemini([prompt_completo])

def pulisci_codice_mermaid(codice):
    mappa = str.maketrans("àèéìòùÀÈÉÌÒÙ", "aeeiouAEEIOU")
    c = codice.translate(mappa).replace("```mermaid", "").replace("```", "").strip()
    c = c.replace("(", "-").replace(")", "").replace("<", " min ").replace(">", " mag ").replace(";", "")
    return re.sub(r'\n+', '\n', c)

def cerca_immagine_scientifica(tipo, query):
    if not query: return None
    q = urllib.parse.quote(str(query).strip())
    
    if tipo == 'molecola':
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{q}/PNG"
        try:
            if requests.head(url, timeout=2).status_code == 200: return url
        except: pass

    wiki = f"https://en.wikipedia.org/w/api.php?action=query&titles={q}&prop=pageimages&format=json&pithumbsize=500&redirects=1"
    try:
        res = requests.get(wiki, timeout=2).json()
        for p in res.get("query", {}).get("pages", {}).values():
            if "thumbnail" in p: return p["thumbnail"]["source"]
    except: pass

    return f"https://image.pollinations.ai/prompt/{q}_medical_illustration?width=512&height=512&nologo=true"

# PROMPTS
def get_prompt_mappa(testo): return f"Agisci come assistente... [TRASCRIZIONE], [SCHEMA], [RIASSUNTO]... {testo}"
def get_prompt_flashcards(n, t): return f"Crea {n} flashcard JSON... {t[:3000]}"
def get_prompt_esame(t): return f"Sei il Prof. House spietato... {t}"
