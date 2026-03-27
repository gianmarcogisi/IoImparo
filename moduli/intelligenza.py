import streamlit as st
import time
from google import genai

# Client centralizzato
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def genera_testo_gemini(prompt):
    max_tentativi = 3
    attesa = 2
    for tentativo in range(max_tentativi):
        try:
            time.sleep(1)
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            return response.text
        except Exception as e:
            if tentativo < max_tentativi - 1 and ("429" in str(e) or "503" in str(e)):
                st.toast(f"Gemini sta pensando... riprovo in {attesa}s", icon="⏳")
                time.sleep(attesa)
                attesa *= 2
            else:
                raise e

def chat_professore_gemini(system_prompt, messaggi_chat):
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
Estrai {num_cards} concetti chiave dal testo fornito e crea delle flashcard in formato JSON puro.
Struttura ESATTA: [{{"domanda": "...", "tipo_visuale": "molecola", "query_visuale": "paracetamol", "risposta": "..."}}]
Testo da usare: {testo_appunti[:3000]}"""

def get_prompt_esame(testo_da_studiare):
    return f"""Sei un Prof. di Farmacia universitario spietato (stile Dr. House). Testo: {testo_da_studiare}
REGOLE TASSATIVE:
1. Se lo studente scrive solo "Iniziamo", ti saluta o fa convenevoli: NON DARE NESSUN VOTO. Fai direttamente la prima domanda per avviare l'esame.
2. Se invece lo studente sta rispondendo a una tua domanda: valuta la risposta.
3. SOLO quando valuti una risposta vera, scrivi su una riga nuova: "VOTO: X" (numero da 1 a 30).
4. Dopo il voto, fai una NUOVA domanda specifica.
5. NON SEMPLIFICARE MAI LE DOMANDE. Nessuna pietà."""
