import streamlit as st
from supabase import create_client, Client

# Inizializzazione centralizzata
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

def db_salva_appunto(user_id, testo, is_public, titolo, materia):
    try:
        return supabase.table("appunti_salvati").insert({
            "user_id": user_id,
            "testo_estratto": testo,
            "is_public": is_public,
            "titolo": titolo,
            "materia": materia
        }).execute()
    except Exception as e:
        st.error(f"Errore DB: {e}")
        return None

def db_get_miei_appunti(user_id, solo_privati=False):
    query = supabase.table("appunti_salvati").select("*").eq("user_id", user_id)
    if solo_privati:
        query = query.eq("is_public", False)
    return query.order("created_at", desc=True).execute()

def db_get_community_appunti(ricerca=""):
    query = supabase.table("appunti_salvati").select("*").eq("is_public", True)
    if ricerca:
        query = query.ilike("titolo", f"%{ricerca}%")
    return query.order("titolo").execute()
