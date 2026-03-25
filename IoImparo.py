import streamlit as st
import os
from google import genai
from PIL import Image
import PyPDF2
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
from supabase import create_client, Client
import time
from groq import Groq # <-- NUOVA LIBRERIA
import random
import json # Ci serve per gestire le domande del quiz

# --- 1. CONFIGURAZIONE PAGINA ---
NOME_APP = "IoImparo 🎓"
st.set_page_config(page_title=NOME_APP, page_icon="🎓", layout="wide")

# --- 2. SICUREZZA E CHIAVI ---
api_key = st.secrets["GEMINI_API_KEY"]
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]
groq_api_key = st.secrets["GROQ_API_KEY"] # <-- CHIAVE GROQ

# Inizializziamo i client
supabase: Client = create_client(supabase_url, supabase_key)
client = genai.Client(api_key=api_key)
groq_client = Groq(api_key=groq_api_key) # <-- CLIENT GROQ

# Mostra il pass VIP al DB
if "access_token" in st.session_state:
    try:
        supabase.auth.set_session(st.session_state.access_token, st.session_state.refresh_token)
    except Exception:
        pass 

# --- IL CENTRALINO MULTI-MODELLO (La Magia) ---
def genera_testo_con_fallback(prompt):
    """Prova con Gemini, se fallisce passa a Groq (Llama 3) in automatico"""
    try:
        # Tentativo 1: Gemini (Veloce e gratis)
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        # Se i server Google sono esplosi (503) o hai finito la quota (429)
        if "503" in str(e) or "429" in str(e):
            st.toast("Google è intasato. Attivo i server di scorta (Llama 3)... 🚀", icon="🦙")
            # Tentativo 2: Groq (Llama 3 8B - Velocissimo)
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-8b-8192",
            )
            return chat_completion.choices[0].message.content
        else:
            # Se è un altro tipo di errore, lo mostra
            raise e
# ---------------------------------------------

# --- 3. GESTIONE SESSIONE UTENTE ---
if "utente_loggato" not in st.session_state:
    st.session_state.utente_loggato = None
if "testo_pulito_studente" not in st.session_state:
    st.session_state.testo_pulito_studente = ""
if "riassunto_pdf" not in st.session_state:
    st.session_state.riassunto_pdf = None
if "messaggi_chat" not in st.session_state:
    st.session_state.messaggi_chat = []

# --- 4. IL MURO DI PROTEZIONE & LOGIN ---
if st.session_state.utente_loggato is None:
    st.title(f"🎓 {NOME_APP}")
    st.warning("👋 Benvenuto! Per iniziare a studiare, accedi o registrati qui sotto.")
    
    tab_login, tab_registrati = st.tabs(["🔑 Accedi", "📝 Registrati"])
    
    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Entra nell'Arena 🔑", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.utente_loggato = res.user
                st.session_state.access_token = res.session.access_token
                st.session_state.refresh_token = res.session.refresh_token
                st.rerun()
            except Exception as e:
                st.error("Credenziali errate.")
                
    with tab_registrati:
        nuova_email = st.text_input("Nuova Email", key="reg_email")
        nuova_password = st.text_input("Nuova Password", type="password", key="reg_password")
        if st.button("Crea Account 🚀", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": nuova_email, "password": nuova_password})
                st.success("Account creato! Ora puoi fare il login.")
            except Exception as e:
                st.error(f"Errore: {e}")
    st.stop() 

# --- 5. SIDEBAR: PROFILO ---
with st.sidebar:
    st.image("https://img.icons8.com/fluent/100/000000/graduation-cap.png", width=100)
    st.title("Area Riservata")
    st.write(f"Socio: **{st.session_state.utente_loggato.email}**")
    if st.button("Esci (Logout)"):
        st.session_state.utente_loggato = None
        st.rerun()

# --- 6. FUNZIONE PDF ---
def genera_pdf_scaricabile(testo):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, f"Riassunto Ordinato - {NOME_APP}")
    c.setFont("Helvetica", 10)
    text_object = c.beginText(100, 720)
    for line in testo.split('\n'):
        if len(line) > 90:
            subline = ""
            for word in line.split(' '):
                if len(subline + " " + word) < 90: subline += " " + word
                else:
                    text_object.textLine(subline.strip())
                    subline = word
            text_object.textLine(subline.strip())
        else: text_object.textLine(line)
    c.drawText(text_object)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# --- 7. INTERFACCIA PRINCIPALE ---
st.title(f"🎓 Centrale Operativa {NOME_APP}")
st.divider()

# --- AGGIORNA LA RIGA DEI TABS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "🗺️ Fase 1: Elabora & PDF", 
    "⚡ Fase 2: Flashcard", 
    "🧑‍🏫 Fase 3: Esame",
    "🥊 Fase 4: Arena Farmacia"
])

with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📥 Carica Materiale")
        tipo_file = st.radio("Formato:", ["📄 PDF", "📸 Foto"], horizontal=True)
        file_input = st.file_uploader("Scegli file", type=['pdf'] if tipo_file == "📄 PDF" else ['png', 'jpg', 'jpeg'], key="file_up")
        bottone_elabora = st.button("Spremi Appunti 🪄", use_container_width=True)

    with col2:
        st.subheader("📄 Risultato")
        if bottone_elabora and file_input is not None:
            if file_input.size > 10 * 1024 * 1024:
                st.error("🚨 File troppo grande. Max 10 MB.")
                st.stop()
            if "ultimo_utilizzo" not in st.session_state: st.session_state.ultimo_utilizzo = 0
            if time.time() - st.session_state.ultimo_utilizzo < 30:
                st.warning("⏱️ Attendi 30 secondi tra un caricamento e l'altro.")
                st.stop()
            st.session_state.ultimo_utilizzo = time.time()

            with st.spinner("Lavorando con Gemini Vision..."):
                try:
                    contenuti = ["""Agisci come il miglior assistente universitario del mondo. Analizza il materiale fornito e scrivi un documento diviso ESATTAMENTE in queste 3 sezioni ben visibili:

--- SEZIONE 1: TRASCRIZIONE ---
(Se ti ho fornito un'immagine, trascrivi fedelmente tutto il testo che vedi. Se è un PDF testuale, scrivi semplicemente: 'Documento digitale riconosciuto').

--- SEZIONE 2: SCHEMA CONCETTUALE ---
(Crea uno schema a punti dettagliato, estraendo i concetti chiave e le definizioni più importanti).

--- SEZIONE 3: RIASSUNTO COMPLETO ---
(Scrivi un riassunto discorsivo, chiaro e approfondito per studiare).
"""]
                    
                    if file_input.type == "application/pdf":
                        reader = PyPDF2.PdfReader(file_input)
                        contenuti.append("".join([page.extract_text() for page in reader.pages]))
                    else: contenuti.append(Image.open(file_input))

                    response = client.models.generate_content(model='gemini-2.5-flash', contents=contenuti)
                    st.session_state.testo_pulito_studente = response.text
                    st.session_state.riassunto_pdf = genera_pdf_scaricabile(response.text)
                    
                    try:
                        supabase.table("appunti_salvati").insert({
                            "user_id": st.session_state.utente_loggato.id,
                            "testo_estratto": st.session_state.testo_pulito_studente
                        }).execute()
                        st.toast("💾 Salvato nel database!", icon="✅")
                    except Exception as e: st.error(f"Errore DB: {e}")
                    
                    st.markdown(response.text)
                    st.balloons()
                except Exception as e:
                    if "503" in str(e): st.warning("⏳ Server Google intasati. Riprova tra poco!")
                    else: st.error(f"Errore: {e}")
        
        if st.session_state.riassunto_pdf:
            st.download_button("📩 Scarica PDF", data=st.session_state.riassunto_pdf, file_name="riassunto.pdf", mime="application/pdf")

with tab2:
    if st.session_state.testo_pulito_studente:
        if st.button("Genera Flashcard 🚀"):
            try:
                # USIAMO IL CENTRALINO!
                testo_flashcard = genera_testo_con_fallback(f"Crea 5 flashcard domanda/risposta da qui: {st.session_state.testo_pulito_studente}")
                st.info(testo_flashcard)
            except Exception as e:
                st.error(f"Errore generazione: {e}")
    else: st.warning("Carica prima qualcosa in Fase 1!")

with tab3:
    if st.session_state.testo_pulito_studente:
        st.markdown("Scrivi **'Iniziamo'** per far partire l'interrogazione.")
        for m in st.session_state.messaggi_chat:
            with st.chat_message(m["ruolo"]): st.markdown(m["contenuto"])
        
        inp = st.chat_input("Rispondi al prof... (Max 500 caratteri)", max_chars=500)
        if inp:
            st.chat_message("user").markdown(inp)
            st.session_state.messaggi_chat.append({"ruolo": "user", "contenuto": inp})
            
            
with tab4:
    st.subheader("🧪 Benvenuto nell'Arena di Farmacia")
    st.write("Sfida un collega in tempo reale su un argomento specifico!")

    scelta_arena = st.radio("Cosa vuoi fare?", ["Crea Sfida 🏗️", "Unisciti a Sfida ⚔️"], horizontal=True)

    if scelta_arena == "Crea Sfida 🏗️":
materia = st.selectbox("Seleziona l'esame della sfida:", [
            # Primo Anno
            "Chimica Generale ed Inorganica", "Biologia Animale", "Biologia Vegetale", 
            "Fisica", "Matematica ed Informatica", "Anatomia Umana",
            # Secondo Anno
            "Chimica Organica", "Microbiologia", "Fisiologia Umana", "Analisi dei Medicinali I",
            # Terzo Anno
            "Biochimica", "Farmacologia e Farmacoterapia", "Analisi dei Medicinali II", 
            "Patologia Generale", "Chimica Farmaceutica e Tossicologica I",
            # Quarto Anno
            "Chimica Farmaceutica e Tossicologica II", "Tecnologia e Legislazione Farmaceutiche", 
            "Tossicologia", "Chimica degli Alimenti", "Farmacognosia",
            # Quinto Anno e Opzionali
            "Farmacia Clinica", "Saggi e Dosaggi dei Farmaci", "Biochimica Applicata", 
            "Fitoterapia", "Igiene"
        ])
        
        file_sfida = st.file_uploader("Carica il materiale della sfida", type=['pdf', 'jpg', 'png'], key="file_arena")
        
        if st.button("Genera Arena 🏟️") and file_sfida:
            with st.spinner("L'IA sta preparando il ring..."):
                # 1. Estraiamo il testo (usiamo Gemini per la vista)
                contenuti = ["Estrai tutto il testo per una sfida tra studenti:"]
                if file_sfida.type == "application/pdf":
                    reader = PyPDF2.PdfReader(file_sfida)
                    testo_arena = "".join([page.extract_text() for page in reader.pages])
                else:
                    testo_arena = Image.open(file_sfida)
                
                # 2. Generiamo le domande in formato JSON (per essere leggibili dal codice)
                prompt_quiz = f"""Genera 3 domande a risposta multipla su questo testo di {materia}.
                Rispondi SOLO con un formato JSON così:
                [
                  {{"domanda": "...", "opzioni": ["A", "B", "C"], "corretta": "A"}},
                  ...
                ]
                Testo: {testo_arena[:2000]}"""
                
                quiz_raw = genera_testo_con_fallback(prompt_quiz)
                
                # Pulizia del testo se l'IA aggiunge chiacchiere (succede con Llama)
                quiz_pulito = quiz_raw.strip().replace("```json", "").replace("```", "")
                
                # 3. Creiamo il PIN e salviamo su Supabase
                nuovo_pin = str(random.randint(1000, 9999))
                try:
                    supabase.table("sfide_multiplayer").insert({
                        "pin": nuovo_pin,
                        "materia": materia,
                        "host_id": st.session_state.utente_loggato.id,
                        "appunti_testo": str(testo_arena)[:3000],
                        "domande_json": json.loads(quiz_pulito),
                        "stato": "waiting"
                    }).execute()
                    st.success(f"🔥 Arena Creata! Dai questo PIN al tuo collega: **{nuovo_pin}**")
                    st.info("Resta in questa pagina, l'app si aggiornerà quando il tuo avversario entrerà.")
                except Exception as e:
                    st.error(f"Errore creazione arena: {e}")

    else: # --- UNISCITI A SFIDA ---
        pin_inserito = st.text_input("Inserisci il PIN di 4 cifre:")
        if st.button("Entra nel Ring 🥊"):
            try:
                # Cerchiamo la sfida
                sfida = supabase.table("sfide_multiplayer").select("*").eq("pin", pin_inserito).eq("stato", "waiting").execute()
                
                if sfida.data:
                    id_sfida = sfida.data[0]['id']
                    # Ci registriamo come Guest e cambiamo stato
                    supabase.table("sfide_multiplayer").update({
                        "guest_id": st.session_state.utente_loggato.id,
                        "stato": "playing"
                    }).eq("id", id_sfida).execute()
                    st.success("✅ Sei dentro! Preparati alla prima domanda...")
                    st.rerun()
                else:
                    st.error("PIN non trovato o sfida già iniziata.")
            except Exception as e:
                st.error(f"Errore: {e}")
                prompt_prof = f"""Sei un professore universitario rigoroso. 
Devi interrogare lo studente basandoti ESCLUSIVAMENTE su questi appunti: 
{st.session_state.testo_pulito_studente[:3000]}

REGOLE TASSATIVE:
1. Fai UNA SOLA domanda alla volta. Sii estremamente sintetico e attinente al testo.
2. ASSOLUTAMENTE NON chiedere collegamenti con argomenti esterni e NON fare salti logici strani.
3. Se lo studente sta rispondendo a una tua domanda, PRIMA valuta la sua risposta dandogli un voto da 1 a 30 (trentesimi), correggi in una riga l'eventuale errore, e POI fai la domanda successiva.

Storico Chat: {st.session_state.messaggi_chat}"""
            
            try:
                # USIAMO IL CENTRALINO!
                risposta_prof = genera_testo_con_fallback(prompt_prof)
                with st.chat_message("assistant"): st.markdown(risposta_prof)
                st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": risposta_prof})
            except Exception as e:
                st.error(f"Errore Chat: {e}")
            else:
                st.warning("Carica prima qualcosa in Fase 1!")
