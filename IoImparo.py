import streamlit as st
import os
from google import genai
from PIL import Image
import PyPDF2
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
from supabase import create_client, Client

# --- 1. CONFIGURAZIONE PAGINA (Deve essere la prima istruzione Streamlit) ---
NOME_APP = "IoImparo 🎓"
st.set_page_config(page_title=NOME_APP, page_icon="🎓", layout="wide")

# --- 2. SICUREZZA E CHIAVI ---
# Recuperiamo tutto dai Secrets di Streamlit
api_key = st.secrets["GEMINI_API_KEY"]
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]

# Inizializziamo i client
supabase: Client = create_client(supabase_url, supabase_key)
client = genai.Client(api_key=api_key)

# --- 3. GESTIONE SESSIONE UTENTE ---
if "utente_loggato" not in st.session_state:
    st.session_state.utente_loggato = None
if "testo_pulito_studente" not in st.session_state:
    st.session_state.testo_pulito_studente = ""
if "riassunto_pdf" not in st.session_state:
    st.session_state.riassunto_pdf = None
if "messaggi_chat" not in st.session_state:
    st.session_state.messaggi_chat = []

# --- 4. IL MURO DI PROTEZIONE & LOGIN CENTRALE ---
if st.session_state.utente_loggato is None:
    st.title(f"🎓 {NOME_APP}")
    st.warning("👋 Benvenuto! Per iniziare a studiare, accedi o registrati qui sotto.")
    st.info("Con IoImparo puoi trasformare foto dei quaderni in PDF, generare flashcard e sfidare il Professore AI.")
    
    # Le due schede centrali per il mobile
    tab_login, tab_registrati = st.tabs(["🔑 Accedi", "📝 Registrati"])
    
    with tab_login:
        st.subheader("Bentornato nell'Arena!")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Entra nell'Arena 🔑", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.utente_loggato = res.user
                # AGGIUNGI QUESTE DUE RIGHE: Salviamo i Pass VIP in tasca
                st.session_state.access_token = res.session.access_token
                st.session_state.refresh_token = res.session.refresh_token
                st.rerun()
            except Exception as e:
                st.error("Credenziali errate.")
                
    with tab_registrati:
        st.subheader("Crea un nuovo account")
        nuova_email = st.text_input("Email", key="reg_email")
        nuova_password = st.text_input("Password", type="password", key="reg_password")
        
        if st.button("Crea Account 🚀", use_container_width=True):
            try:
                res = supabase.auth.sign_up({"email": nuova_email, "password": nuova_password})
                st.success("Account creato! Ora puoi fare il login (se hai lasciato attiva la conferma email, controlla la posta).")
            except Exception as e:
                st.error(f"Errore: {e}")

    # ST.STOP() È FONDAMENTALE QUI: impedisce di caricare il resto del sito se non sei loggato
    st.stop() 

# --- 5. SIDEBAR: PROFILO UTENTE (Visibile solo se loggato) ---
with st.sidebar:
    st.image("https://img.icons8.com/fluent/100/000000/graduation-cap.png", width=100)
    st.title("Area Riservata")
    st.write(f"Socio: **{st.session_state.utente_loggato.email}**")
    
    if st.button("Esci (Logout)"):
        st.session_state.utente_loggato = None
        st.rerun()

# --- 6. FUNZIONE GENERATORE PDF (Tutta la tua formattazione originale) ---
def genera_pdf_scaricabile(testo):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, f"Riassunto Ordinato - {NOME_APP}")
    c.setFont("Helvetica", 10)
    text_object = c.beginText(100, 720)
    lines = testo.split('\n')
    for line in lines:
        if len(line) > 90:
            words = line.split(' ')
            subline = ""
            for word in words:
                if len(subline + " " + word) < 90:
                    subline += " " + word
                else:
                    text_object.textLine(subline.strip())
                    subline = word
            text_object.textLine(subline.strip())
        else:
            text_object.textLine(line)
    c.drawText(text_object)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# --- 7. INTERFACCIA PRINCIPALE (SBLOCCATA DOPO LOGIN) ---
st.title(f"🎓 Centrale Operativa {NOME_APP}")
st.divider()

tab1, tab2, tab3 = st.tabs([
    "🗺️ Fase 1: Elabora & PDF", 
    "⚡ Fase 2: Flashcard", 
    "🧑‍🏫 Fase 3: Esame"
])

with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📥 Carica Materiale")
        tipo_file = st.radio("Formato:", ["📄 PDF", "📸 Foto"], horizontal=True)
        if tipo_file == "📄 PDF":
            file_input = st.file_uploader("Scegli il PDF", type=['pdf'], key="p")
        else:
            file_input = st.file_uploader("Scatta/Scegli foto", type=['png', 'jpg', 'jpeg'], key="f")
        
        bottone_elabora = st.button("Spremi Appunti 🪄", use_container_width=True)

    with col2:
        st.subheader("📄 Risultato")
        if bottone_elabora and file_input is not None:
            with st.spinner("Lavorando..."):
                try:
                    contenuti = ["""Analizza questo materiale. 
                    1. TRASCRIZIONE: se immagine, trascrivi il testo. 
                    2. SCHEMA: crea uno schema a punti. 
                    3. RIASSUNTO: scrivi un riassunto chiaro."""]
                    
                    if file_input.type == "application/pdf":
                        reader = PyPDF2.PdfReader(file_input)
                        testo = ""
                        for page in reader.pages:
                            testo += page.extract_text()
                        contenuti.append(testo)
                    else:
                        contenuti.append(Image.open(file_input))

                    response = client.models.generate_content(model='gemini-2.5-flash', contents=contenuti)
                    st.session_state.testo_pulito_studente = response.text
                    st.session_state.riassunto_pdf = genera_pdf_scaricabile(response.text)
                    # --- SALVATAGGIO IN CASSAFORTE (SUPABASE) ---
                    try:
                        # Prepariamo i dati: chi è l'utente e qual è il testo
                        dati_da_salvare = {
                            "user_id": st.session_state.utente_loggato.id,
                            "testo_estratto": st.session_state.testo_pulito_studente
                        }
                        # Li spariamo nel database appena creato
                        supabase.table("appunti_salvati").insert(dati_da_salvare).execute()
                        # Un piccolo avviso per far capire all'utente che è tutto salvato
                        st.toast("💾 Appunti salvati nel tuo database segreto!", icon="✅")
                    except Exception as errore_db:
                        st.error(f"Errore nel salvataggio su Supabase: {errore_db}")
                    # ----------------------------------------------
                    st.markdown(response.text)
                    st.balloons()
                except Exception as e:
                    st.error(f"Errore: {e}")
        
        if st.session_state.riassunto_pdf:
            st.download_button("📩 Scarica PDF", data=st.session_state.riassunto_pdf, file_name="riassunto.pdf", mime="application/pdf")

with tab2:
    if st.session_state.testo_pulito_studente:
        if st.button("Genera Flashcard 🚀"):
            res = client.models.generate_content(model='gemini-2.5-flash', contents=f"Crea 5 flashcard domanda/risposta da qui: {st.session_state.testo_pulito_studente}")
            st.info(res.text)
    else:
        st.warning("Carica prima qualcosa in Fase 1!")

with tab3:
    if st.session_state.testo_pulito_studente:
        st.markdown("Scrivi **'Iniziamo'** per l'interrogazione.")
        for m in st.session_state.messaggi_chat:
            with st.chat_message(m["ruolo"]): st.markdown(m["contenuto"])
        
        inp = st.chat_input("Rispondi al prof...")
        if inp:
            st.chat_message("user").markdown(inp)
            st.session_state.messaggi_chat.append({"ruolo": "user", "contenuto": inp})
            prompt = f"Sei un prof. Appunti: {st.session_state.testo_pulito_studente[:3000]}. Chat: {st.session_state.messaggi_chat}. Fai una domanda o valuta con voto."
            res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            with st.chat_message("assistant"): st.markdown(res.text)
            st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": res.text})
    else:
        st.warning("Carica prima qualcosa in Fase 1!")
