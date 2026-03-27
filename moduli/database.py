import streamlit as st
from supabase import create_client, Client

# Inizializzazione centralizzata
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)

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
    """Recupera gli appunti dell'utente loggato."""
    try:
        query = supabase.table("appunti_salvati").select("*").eq("user_id", user_id)
        if solo_privati:
            query = query.eq("is_public", False)
        return query.order("created_at", desc=True).execute()
    except:
        return None

def db_get_community_appunti(ricerca=""):
    """Recupera gli appunti pubblici con filtro ricerca."""
    try:
        query = supabase.table("appunti_salvati").select("*").eq("is_public", True)
        if ricerca:
            query = query.ilike("titolo", f"%{ricerca}%")
        return query.order("titolo").execute()
    except:
        return None
