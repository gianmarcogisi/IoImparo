import streamlit as st
from google import genai

# Inizializziamo il client qui dentro
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def get_prompt_mappa(istruzioni_trascrizione):
    return f"Agisci come assistente... [INCOLLA QUI IL PROMPT DELLA MAPPA]"

def get_prompt_flashcards(num_cards, testo_appunti):
    return f"Crea {num_cards} flashcard... [INCOLLA QUI IL PROMPT DELLE CARTE]"

def get_prompt_esame(testo_da_studiare):
    return f"Sei il Prof. House... [INCOLLA QUI IL PROMPT DEL PROF]"

def genera_testo_gemini(prompt):
    # Incolla qui la tua vecchia funzione genera_testo_gemini
    response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
    return response.text
