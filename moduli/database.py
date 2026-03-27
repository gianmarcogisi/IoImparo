import streamlit as st
from supabase import create_client, Client

# Inizializzazione Supabase
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def db_salva_appunto(user_id, testo, is_public, titolo, materia):
    return supabase.table("appunti_salvati").insert({
        "user_id": user_id, "testo_estratto": testo, 
        "is_public": is_public, "titolo": titolo, "materia": materia
    }).execute()

def db_get_miei_appunti(user_id):
    return supabase.table("appunti_salvati").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
