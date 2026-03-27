import streamlit as st
import time
import requests
import urllib.parse
import re
from google import genai

# --- INIZIALIZZAZIONE CLIENT ---
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def genera_testo_gemini(prompt):
    """
    Motore di generazione identico al monolito: 
    include 3 tentativi e gestione specifica errori 429/503.
    """
    max_tentativi = 3
    attesa = 2
    for tentativo in range(max_tentativi):
        try:
            time.sleep(1) 
            response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=prompt
            )
            return response.text
        except Exception as e:
            if tentativo < max_tentativi - 1 and ("429" in str(e) or "503" in str(e)):
                st.toast(f"Gemini sta pensando... riprovo in {attesa}s", icon="⏳")
                time.sleep(attesa)
                attesa *= 2
            else:
                raise e

def chat_professore_gemini(system_prompt, messaggi_chat):
    """
    Gestisce la chat del professore con la cronologia esatta del monolito.
    """
    try:
        prompt_completo = system_prompt + "\n\n--- CRONOLOGIA CHAT ---\n"
        for msg in messaggi_chat:
            ruolo = "Professore" if msg["ruolo"] == "assistant" else "Studente"
            prompt_completo += f"{ruolo}: {msg['contenuto']}\n"
            
        prompt_completo += "Professore: "
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_completo)
        return response.text
    except Exception as e:
        raise e

def pulisci_codice_mermaid(codice_mermaid):
    """
    VERSIONE INTEGRALE: Contiene tutte le sostituzioni di pulizia 
    estratte dalla Fase 1 del file IoImparoMonolitico.py.
    """
    mappa_pulizia = str.maketrans("àèéìòùÀÈÉÌÒÙ", "aeeiouAEEIOU")
    c = codice_mermaid.translate(mappa_pulizia).replace("```mermaid", "").replace("```", "").strip()
    
    # Pulizia avanzata per la compatibilità del renderer
    c = c.replace("(", "-").replace(")", "")
    c = c.replace("-->", "FRECCIA_SALVA")
    c = c.replace("<", " min ").replace(">", " mag ")
    c = c.replace("FRECCIA_SALVA", "-->")
    c = c.replace(";", "")
    
    # Regex per la formattazione dei nodi e dei grafici
    c = re.sub(r'(graph\s+TD)\s+', r'\1\n', c, flags=re.IGNORECASE)
    c = re.sub(r'\]\s+(?=[A-Za-z0-9_]+\s*(?:\[|-))', ']\n', c)
    c = re.sub(r'\n+', '\n', c)
    c = c.replace("] ", "]\n")
    return c

def cerca_immagine_scientifica(tipo_visuale, query_visuale):
    """
    Il motore a cascata completo con i timeout di 3 secondi del monolito.
    """
    q_v_raw = str(query_visuale).strip()
    if not q_v_raw: return None
    q_v_url = urllib.parse.quote(q_v_raw)

    # LIVELLO 1: PubChem (Molecole)
    if tipo_visuale == 'molecola':
        url_pubchem = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{q_v_url}/PNG"
        try:
            if requests.head(url_pubchem, timeout=3).status_code == 200:
                return url_pubchem
        except: pass

    # LIVELLO 2: Wikipedia (Scienza)
    wiki_api = f"https://en.wikipedia.org/w/api.php?action=query&titles={q_v_url}&prop=pageimages&format=json&pithumbsize=500&redirects=1"
    try:
        res = requests.get(wiki_api, timeout=3).json()
        for p_info in res.get("query", {}).get("pages", {}).values():
            if "thumbnail" in p_info:
                return p_info["thumbnail"]["source"]
    except: pass

    # LIVELLO 3: Pollinations AI (Rappresentazione medica)
    frase_prompt = f"{q_v_raw} medical scientific illustration clean background"
    q_v_ai = urllib.parse.quote(frase_prompt)
    return f"https://image.pollinations.ai/prompt/{q_v_ai}?width=512&height=512&nologo=true"

# --- PROMPT REINTEGRATI (TESTI ORIGINALI) ---

def get_prompt_mappa(istruzioni_trascrizione):
    return f"""Agisci come il miglior assistente universitario del mondo. 
Dividi la risposta ESATTAMENTE usando questi tag:

[TRASCRIZIONE]
{istruzioni_trascrizione}
[/TRASCRIZIONE]

[SCHEMA]
Genera ESCLUSIVAMENTE codice Mermaid.js valido (formato graph TD).
REGOLE TASSATIVE:
1. Sviluppa in VERTICALE. Max 2 frecce per ogni nodo.
2. Sintassi: A["Titolo: descrizione breve"] --> B["Titolo: descrizione"]
3. NO accenti (usa e invece di è), NO virgolette doppie interne, NO parentesi.
4. Tutto il testo di un nodo deve stare su una singola riga.
[/SCHEMA]

[RIASSUNTO]
Scrivi un riassunto discorsivo, chiaro, con le parole chiave in grassetto.
[/RIASSUNTO]"""

def get_prompt_flashcards(num_cards, testo_appunti):
    return f"""Agisci come il miglior professore universitario. 
Estrai {num_cards} concetti chiave dal testo fornito e crea delle flashcard in formato JSON puro (senza markdown `json`).
Struttura ESATTA: [{{"domanda": "...", "tipo_visuale": "molecola", "query_visuale": "paracetamol", "risposta": "..."}}]
Tipi visuali permessi: "molecola" (usa il nome inglese), "immagine" (breve query inglese), "nessuno" (lascia vuoto).
Testo da usare: {testo_appunti[:3000]}"""

def get_prompt_esame(testo_da_studiare):
    return f"""Sei un Prof. di Farmacia universitario spietato (stile Dr. House). Testo: {testo_da_studiare}
    
REGOLE TASSATIVE:
1. Se lo studente scrive solo "Iniziamo", ti saluta o fa convenevoli: NON DARE NESSUN VOTO. Fai direttamente la prima domanda per avviare l'esame.
2. Se invece lo studente sta rispondendo a una tua domanda: valuta la risposta. Se corretta, sii ironico. Se errata, sii cinico e cattivo.
3. SOLO quando valuti una risposta vera, scrivi su una riga nuova: "VOTO: X" (numero da 1 a 30).
4. Dopo il voto, fai una NUOVA domanda specifica, colpendolo sui dettagli.
5. NON SEMPLIFICARE MAI LE DOMANDE. Nessuna pietà."""
