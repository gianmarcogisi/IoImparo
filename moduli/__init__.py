from supabase import create_client, Client
import streamlit as st

# Inizializza qui Supabase
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def db_salva_appunto(...): # incolla qui
def db_get_miei_appunti(...): # incolla qui
