import streamlit as st
import time

def gestisci_voto_esame(risposta_prof):
    """
    Estrae il voto dalla risposta del Professore e gestisce 
    il contatore degli errori e lo stato di bocciatura.
    """
    voto = 0
    try:
        # Cerchiamo la stringa "VOTO:" e puliamo il risultato per avere solo il numero
        if "VOTO:" in risposta_prof:
            voto_str = risposta_prof.split("VOTO:")[1].strip()
            # Filtriamo solo i numeri (gestisce voti come '28/30' o '15.')
            numeri = "".join(filter(str.isdigit, voto_str[:3]))
            voto = int(numeri)
    except Exception:
        voto = 0
    
    # --- LOGICA BOCCIATURA ACCUMULATA ---
    # Se il voto è un'insufficienza (sotto 18), aggiungiamo un errore al totale
    if 0 < voto < 18:
        st.session_state.errori_totali += 1
    
    # Se lo studente accumula 4 o più errori totali, scatta la bocciatura
    if st.session_state.errori_totali >= 4:
        st.session_state.esame_bocciato = True
        
    return voto

def calcola_esito_arena(is_host, sfida):
    """
    Determina quali colonne del database aggiornare in base al ruolo 
    del giocatore (Host o Guest) e gestisce i ping di connessione.
    """
    # Identifica le colonne dei punteggi
    col_punti = "punteggio_host" if is_host else "punteggio_guest"
    col_risposte = "risposte_host" if is_host else "risposte_guest"
    
    # Identifica le colonne per il check AFK (Anti-disconnessione)
    mio_ping = "last_ping_host" if is_host else "last_ping_guest"
    suo_ping = "last_ping_guest" if is_host else "last_ping_host"
    
    return col_punti, col_risposte, mio_ping, suo_ping
