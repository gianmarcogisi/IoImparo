import streamlit as st

def gestisci_voto_esame(risposta_prof, session_state):
    voto = 0
    try:
        voto_str = risposta_prof.split("VOTO:")[1].strip()
        voto = int("".join(filter(str.isdigit, voto_str[:3])))
    except: voto = 0
    
    if 0 < voto < 18: session_state.errori_totali += 1
    if session_state.errori_totali >= 4: session_state.esame_bocciato = True
    return voto

def calcola_esito_arena(is_host):
    return ("punteggio_host", "risposte_host") if is_host else ("punteggio_guest", "risposte_guest")
