import streamlit as st
import time

def gestisci_voto_esame(risposta_prof, session_state):
    """Estrae il voto e calcola lo stato della sessione esame."""
    voto = 0
    try:
        # Estrazione numerica del voto
        voto_str = risposta_prof.split("VOTO:")[1].strip()
        voto = int("".join(filter(str.isdigit, voto_str[:3])))
    except:
        voto = 0
    
    # Aggiornamento contatori
    if voto > 0 and voto < 18:
        session_state.errori_totali += 1
    
    if session_state.errori_totali >= 4:
        session_state.esame_bocciato = True
        
    return voto

def calcola_punti_arena(is_host, sfida):
    """Restituisce le chiavi corrette per aggiornare i punteggi nell'Arena."""
    col_punti = "punteggio_host" if is_host else "punteggio_guest"
    col_risposte = "risposte_host" if is_host else "risposte_guest"
    mio_ping = "last_ping_host" if is_host else "last_ping_guest"
    suo_ping = "last_ping_guest" if is_host else "last_ping_host"
    return col_punti, col_risposte, m_ping, s_ping
