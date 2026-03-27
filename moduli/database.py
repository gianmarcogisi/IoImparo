import streamlit as st
from supabase import create_client, Client

# --- INIZIALIZZAZIONE ---
# Recupero chiavi dai secrets (come nel tuo monolito)
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)

# --- COSTANTI REINTEGRATE ---
# La tua lista completa delle materie dal monolito
LISTA_MATERIE = [
    "Chimica Generale ed Inorganica", "Biologia Animale", "Biologia Vegetale", "Fisica", 
    "Matematica ed Informatica", "Anatomia Umana", "Chimica Organica", "Microbiologia", 
    "Fisiologia Umana", "Analisi dei Medicinali I", "Biochimica", "Farmacologia e Farmacoterapia", 
    "Analisi dei Medicinali II", "Patologia Generale", "Chimica Farmaceutica e Tossicologica I",
    "Chimica Farmaceutica e Tossicologica II", "Tecnologia e Legislazione Farmaceutiche", 
    "Tossicologia", "Chimica degli Alimenti", "Farmacognosia", "Farmacia Clinica", 
    "Saggi e Dosaggi dei Farmaci", "Biochimica Applicata", "Fitoterapia", "Igiene"
]

# --- FUNZIONI APPUNTI ---

def db_salva_appunto(user_id, testo, is_public, titolo, materia):
    """Salva un nuovo appunto nel database."""
    try:
        return supabase.table("appunti_salvati").insert({
            "user_id": user_id,
            "testo_estratto": testo,
            "is_public": is_public,
            "titolo": titolo,
            "materia": materia
        }).execute()
    except Exception as e:
        st.error(f"Errore salvataggio DB: {e}")
        return None

def db_get_miei_appunti(user_id, solo_privati=False):
    """Recupera gli appunti dell'utente (Fase 2, 3 e Archivio)."""
    try:
        query = supabase.table("appunti_salvati").select("*").eq("user_id", user_id)
        if solo_privati:
            query = query.eq("is_public", False)
        return query.order("created_at", desc=True).execute()
    except Exception as e:
        st.error(f"Errore recupero appunti: {e}")
        return None

def db_get_community_appunti(ricerca=""):
    """Recupera gli appunti pubblici per la Community."""
    try:
        query = supabase.table("appunti_salvati").select("*").eq("is_public", True)
        if ricerca:
            query = query.ilike("titolo", f"%{ricerca}%")
        return query.order("titolo").execute()
    except Exception as e:
        st.error(f"Errore community: {e}")
        return None

# --- FUNZIONI ARENA (Reintegrate dal Monolito) ---

def db_check_sfide_attive(uid):
    """Controlla se l'utente ha già sfide in corso (per riconnessione)."""
    try:
        res_host = supabase.table("sfide_multiplayer").select("id").eq("host_id", uid).in_("stato", ["waiting", "playing"]).execute()
        res_guest = supabase.table("sfide_multiplayer").select("id").eq("guest_id", uid).eq("stato", "playing").execute()
        return res_host, res_guest
    except:
        return None, None

def db_crea_arena(uid, pin, materia, testo, quiz_json):
    """Inserisce la nuova sfida nel ring."""
    return supabase.table("sfide_multiplayer").insert({
        "pin": pin,
        "materia": materia,
        "host_id": uid,
        "appunti_testo": testo,
        "domande_json": quiz_json,
        "stato": "waiting"
    }).execute()

def db_aggiorna_stato_sfida(sfida_id, dati_aggiornamento):
    """Aggiorna punteggi, ping o stato della sfida."""
    return supabase.table("sfide_multiplayer").update(dati_aggiornamento).eq("id", sfida_id).execute()
