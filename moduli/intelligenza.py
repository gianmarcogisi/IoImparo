import streamlit as st
import time
import requests
import urllib.parse
from google import genai

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def genera_testo_gemini(prompt):
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        st.error(f"Errore Gemini: {e}")
        return ""

def chat_professore_gemini(system_prompt, messaggi_chat):
    prompt_completo = system_prompt + "\n\n--- CRONOLOGIA ---\n"
    for msg in messaggi_chat:
        ruolo = "Professore" if msg["ruolo"] == "assistant" else "Studente"
        prompt_completo += f"{ruolo}: {msg['contenuto']}\n"
    prompt_completo += "Professore: "
    return genera_testo_gemini(prompt_completo)

def cerca_immagine_scientifica(t_v, q_v_raw):
    """Il triplo motore di ricerca immagini: PubChem -> Wikipedia -> AI"""
    if not q_v_raw: return None
    q_v_url = urllib.parse.quote(q_v_raw)
    
    # 1. PubChem (Molecole)
    if t_v == 'molecola':
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{q_v_url}/PNG"
        if requests.head(url).status_code == 200: return url

    # 2. Wikipedia (Foto reali)
    wiki_api = f"https://en.wikipedia.org/w/api.php?action=query&titles={q_v_url}&prop=pageimages&format=json&pithumbsize=500&redirects=1"
    try:
        res = requests.get(wiki_api).json()
        pages = res.get("query", {}).get("pages", {})
        for p_id in pages:
            if "thumbnail" in pages[p_id]: return pages[p_id]["thumbnail"]["source"]
    except: pass

    # 3. Pollinations (AI Fallback)
    return f"https://image.pollinations.ai/prompt/{q_v_url}_scientific_illustration?width=512&height=512&nologo=true"

# --- PROMPT (Restaurati con i dettagli precedenti) ---
def get_prompt_mappa(istruzioni):
    return f"Agisci come assistente universitario... [Dividi in [TRASCRIZIONE], [SCHEMA] (Mermaid graph TD), [RIASSUNTO]]... {istruzioni}"

def get_prompt_flashcards(num, testo):
    return f"Crea {num} flashcard JSON: domanda, tipo_visuale, query_visuale, risposta. Testo: {testo[:3000]}"

def get_prompt_esame(argomento):
    return f"Sei il Prof. House spietato. Valuta, dai VOTO: X e fai una nuova domanda difficile. Argomento: {argomento}"
