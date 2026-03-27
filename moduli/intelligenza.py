import streamlit as st
import time
import requests
import urllib.parse
import re
from google import genai

# --- INIZIALIZZAZIONE CLIENT ---
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def genera_testo_gemini(prompt_list):
    """Generazione testo con gestione retry per errori 429/503."""
    max_tentativi = 3
    attesa = 2
    for tentativo in range(max_tentativi):
        try:
            time.sleep(1) # Piccolo respiro preventivo
            response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=prompt_list
            )
            return response.text
        except Exception as e:
            if tentativo < max_tentativi - 1 and ("429" in str(e) or "503" in str(e)):
                st.toast(f"⏳ Gemini è carico, riprovo tra {attesa}s...", icon="⚠️")
                time.sleep(attesa)
                attesa *= 2
            else:
                st.error(f"❌ Errore IA: {e}")
                return ""

def chat_professore_gemini(system_prompt, messaggi_chat):
    """Gestisce la chat con il Prof. House."""
    try:
        prompt_completo = system_prompt + "\n\n--- CRONOLOGIA CHAT ---\n"
        for msg in messaggi_chat:
            ruolo = "Professore" if msg["ruolo"] == "assistant" else "Studente"
            prompt_completo += f"{ruolo}: {msg['contenuto']}\n"
            
        prompt_completo += "Professore: "
        return genera_testo_gemini([prompt_completo])
    except Exception as e:
        st.error(f"🚨 Errore nella chat: {e}")
        return "Errore di connessione con il Professore."

def pulisci_codice_mermaid(codice):
    """
    Pulizia ESTREMA del codice Mermaid per evitare che la scatola rimanga bianca.
    """
    # 1. Rimuove accenti e tag markdown
    mappa_pulizia = str.maketrans("àèéìòùÀÈÉÌÒÙ", "aeeiouAEEIOU")
    c = codice.translate(mappa_pulizia).replace("```mermaid", "").replace("```", "").strip()
    
    # 2. Rimuove caratteri che fanno crashare il renderer Javascript
    c = c.replace("(", "-").replace(")", "")
    c = c.replace("<", " min ").replace(">", " mag ")
    c = c.replace(";", "")
    c = c.replace('"', "") # Via le virgolette doppie
    c = c.replace("'", "") # Via gli apostrofi (killer numero 1 di Mermaid)
    
    # 3. Formattazione spazi e righe
    c = re.sub(r'\n+', '\n', c)
    
    # 4. Assicurazione sulla vita: deve sempre iniziare con graph TD
    if not c.startswith("graph TD"):
        c = "graph TD\n" + c
        
    return c

def cerca_immagine_scientifica(tipo_visuale, query_visuale):
    """Motore di ricerca immagini a 3 livelli (PubChem -> Wiki -> AI)"""
    q_v_raw = str(query_visuale).strip()
    if not q_v_raw: return None
    q_v_url = urllib.parse.quote(q_v_raw)

    if tipo_visuale == 'molecola':
        url_pubchem = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{q_v_url}/PNG"
        try:
            if requests.head(url_pubchem, timeout=3).status_code == 200:
                return url_pubchem
        except: pass

    wiki_api = f"https://en.wikipedia.org/w/api.php?action=query&titles={q_v_url}&prop=pageimages&format=json&pithumbsize=500&redirects=1"
    try:
        res = requests.get(wiki_api, timeout=3).json()
        for p_info in res.get("query", {}).get("pages", {}).values():
            if "thumbnail" in p_info:
                return p_info["thumbnail"]["source"]
    except: pass

    frase_prompt = f"{q_v_raw} medical scientific illustration clean background"
    q_v_ai = urllib.parse.quote(frase_prompt)
    return f"https://image.pollinations.ai/prompt/{q_v_ai}?width=512&height=512&nologo=true"

# --- ARMERIA DEI PROMPT (POTENZIATI PER LA LUNGHEZZA E LA SICUREZZA) ---

def get_prompt_mappa(istruzioni_trascrizione):
    return f"""Agisci come il miglior professore e assistente universitario del mondo. 
Dividi la risposta ESATTAMENTE usando questi tag:

[TRASCRIZIONE]
{istruzioni_trascrizione}
Devi estrarre e riscrivere OGNI SINGOLO DETTAGLIO. Crea un testo lunghissimo ed esaustivo.
[/TRASCRIZIONE]

[SCHEMA]
Genera ESCLUSIVAMENTE codice Mermaid.js valido.
REGOLE FONDAMENTALI:
1. Inizia SEMPRE con: graph TD
2. Usa solo nodi con parentesi quadre. Esempio: A[Titolo] --> B[Sottotitolo]
3. DIVIETO ASSOLUTO DI USARE: accenti, apostrofi, virgolette, parentesi tonde.
4. Genera una mappa complessa con almeno 15-20 nodi.
[/SCHEMA]

[RIASSUNTO]
Scrivi un riassunto discorsivo ESTREMAMENTE LUNGO, completo e dettagliato. Non omettere nessuna informazione vitale. Usa il grassetto per le parole chiave.
[/RIASSUNTO]"""

def get_prompt_flashcards(num_cards, testo_appunti):
    return f"""Agisci come il miglior professore universitario. 
Estrai {num_cards} concetti chiave e crea flashcard JSON.
Struttura: [{{"domanda": "...", "tipo_visuale": "molecola", "query_visuale": "paracetamol", "risposta": "..."}}]
Testo: {testo_appunti[:3000]}"""

def get_prompt_esame(testo_da_studiare):
    return f"""Sei un Prof. di Farmacia universitario spietato (stile Dr. House). Testo: {testo_da_studiare}
1. Se lo studente scrive solo "Iniziamo", fai solo la prima domanda (no voto).
2. Valuta le risposte: se corretta sii ironico, se errata sii cinico.
3. Scrivi SEMPRE 'VOTO: X' (1-30) su una riga nuova dopo il commento.
4. Fai una NUOVA domanda specifica. No pietà."""
