import streamlit as st
from supabase import create_client, Client

# --- INIZIALIZZAZIONE CENTRALIZZATA ---
# Recuperiamo le credenziali dai segreti di Streamlit
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]

# Creiamo il client che verrà usato da tutte le funzioni del modulo
supabase: Client = create_client(supabase_url, supabase_key)

def db_salva_appunto(user_id, testo, is_public, titolo, materia):
    """
    Salva un nuovo appunto nel database Supabase.
    """
    try:
        return supabase.table("appunti_salvati").insert({
            "user_id": user_id,
            "testo_estratto": testo,
            "is_public": is_public,
            "titolo": titolo,
            "materia": materia
        }).execute()
    except Exception as e:
        st.error(f"🚨 Errore nel salvataggio su database: {e}")
        return None

def db_get_miei_appunti(user_id, solo_privati=False):
    """
    Recupera gli appunti dell'utente. Se solo_privati è True, 
    esclude quelli condivisi con la community.
    """
    try:
        query = supabase.table("appunti_salvati").select("*").eq("user_id", user_id)
        
        if solo_privati:
            query = query.eq("is_public", False)
            
        # Ordiniamo per data (dal più recente) e limitiamo a 25 per l'archivio
        return query.order("created_at", desc=True).limit(25).execute()
    except Exception as e:
        st.error(f"🚨 Errore nel recupero appunti: {e}")
        return None

def db_get_community_appunti(ricerca=""):
    """
    Recupera tutti gli appunti pubblici. 
    Permette di filtrare per titolo tramite una ricerca 'case-insensitive'.
    """
    try:
        query = supabase.table("appunti_salvati").select("*").eq("is_public", True)
        
        if ricerca:
            query = query.ilike("titolo", f"%{ricerca}%")
            
        return query.order("titolo").execute()
    except Exception as e:
        st.error(f"🚨 Errore nella ricerca community: {e}")
        return None
