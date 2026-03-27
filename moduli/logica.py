import st
import time

def gestisci_voto_esame(risposta_prof, st_session):
    """Estrae il voto e calcola lo stato della sessione esame."""
    voto = 0
    try:
        voto_str = risposta_prof.split("VOTO:")[1].strip()
        voto = int("".join(filter(str.isdigit, voto_str[:3])))
    except:
        voto = 0
    
    if voto > 0 and voto < 18:
        st_session.errori_totali += 1
    
    if st_session.errori_totali >= 4:
        st_session.esame_bocciato = True
        
    return voto

def calcola_esito_arena(is_host, sfida):
    col_punti = "punteggio_host" if is_host else "punteggio_guest"
    col_risposte = "risposte_host" if is_host else "risposte_guest"
    return col_punti, col_risposte
def calcola_punti_arena(is_host, sfida):
    """Restituisce le chiavi corrette per aggiornare i punteggi nell'Arena."""
    col_punti = "punteggio_host" if is_host else "punteggio_guest"
    col_risposte = "risposte_host" if is_host else "risposte_guest"
    mio_ping = "last_ping_host" if is_host else "last_ping_guest"
    suo_ping = "last_ping_guest" if is_host else "last_ping_host"
    return col_punti, col_risposte, mio_ping, suo_ping
