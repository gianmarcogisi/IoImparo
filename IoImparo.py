import streamlit as st
import os
from google import genai
from PIL import Image
import PyPDF2
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
from supabase import create_client, Client

# --- 1. SICUREZZA E CONFIGURAZIONE ---
api_key = os.getenv("GEMINI_API_KEY")
# --- CONFIGURAZIONE SUPABASE ---
# NON incollare l'URL qui! Usa il nome della chiave che hai messo nei Secrets
supabase_url = st.secrets["SUPABASE_URL"] 
supabase_key = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(supabase_url, supabase_key)
    raise KeyError(_missing_key_error_message(key))
# --- GESTIONE SESSIONE UTENTE ---
if "utente_loggato" not in st.session_state:
    st.session_state.utente_loggato = None

# --- SIDEBAR: LOGIN E REGISTRAZIONE ---
with st.sidebar:
    st.image("https://img.icons8.com/fluent/100/000000/graduation-cap.png", width=100)
    st.title("Area Riservata")
    
    if st.session_state.utente_loggato is None:
        scelta_auth = st.radio("Cosa vuoi fare?", ["Accedi", "Registrati"])
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        if scelta_auth == "Registrati":
            if st.button("Crea Account 🚀"):
                try:
                    res = supabase.auth.sign_up({"email": email, "password": password})
                    st.success("Ti abbiamo inviato un'email di conferma! Controlla la posta (anche spam).")
                except Exception as e:
                    st.error(f"Errore registrazione: {e}")
        
        else: # Login
            if st.button("Entra nell'Arena 🔑"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.utente_loggato = res.user
                    st.success(f"Bentornato!")
                    st.rerun() # Ricarica per sbloccare l'app
                except Exception as e:
                    st.error("Email o Password errati.")
    else:
        st.write(f"Socio: **{st.session_state.utente_loggato.email}**")
        if st.button("Esci 🚪"):
            supabase.auth.sign_out()
            st.session_state.utente_loggato = None
            st.rerun()

# --- IL MURO DI PROTEZIONE ---
if st.session_state.utente_loggato is None:
    st.warning("⚠️ Per usare IoImparo devi prima accedere o registrarti dalla barra laterale!")
    st.stop() # Blocca l'esecuzione di tutto quello che c'è sotto!

# DA QUI IN POI C'È IL TUO CODICE DELLE SCHEDE (TAB1, TAB2, TAB3...)

# Nome ufficiale dell'App!
NOME_APP = "IoImparo 🎓"
st.set_page_config(page_title=NOME_APP, page_icon="🎓", layout="wide")

if not api_key:
    st.error("⚠️ Manca la chiave API nel file .env!")
    st.stop()

client = genai.Client(api_key=api_key)

# --- 2. LA MEMORIA (Session State) ---
if "testo_pulito_studente" not in st.session_state:
    st.session_state.testo_pulito_studente = ""
if "riassunto_pdf" not in st.session_state:
    st.session_state.riassunto_pdf = ""
if "messaggi_chat" not in st.session_state:
    st.session_state.messaggi_chat = []

# --- FUNZIONE MAGICA: Generatore di PDF ---
# Prende il testo generato dall'IA e lo trasforma in un file PDF scaricabile
def genera_pdf_scaricabile(testo):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    
    # Titolo del documento
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, f"Riassunto Ordinato - {NOME_APP}")
    
    # Corpo del testo (gestione di base delle linee lunghe)
    c.setFont("Helvetica", 10)
    text_object = c.beginText(100, 720)
    lines = testo.split('\n')
    for line in lines:
        # Una logica di base per non far andare il testo fuori dal foglio
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

# --- 3. INTESTAZIONE GRAFICA ---
st.title(f"🎓 Benvenuto in {NOME_APP}")
st.markdown("La tua centrale operativa per trasformare appunti disordinati in un 30 e lode.")
st.divider()

# --- 4. I TABS (Riorganizzati secondo la visione del CEO) ---
tab1, tab2, tab3 = st.tabs([
    "🗺️ Fase 1: Elabora & Scarica PDF", 
    "⚡ Fase 2: Flashcard Automatiche", 
    "🧑‍🏫 Fase 3: Simulatore d'Esame"
])

# ==========================================
# SCHEDA 1: ELABORA (Trascrivi, Schematizza, PDF)
# ==========================================
with tab1:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("📥 Carica il Materiale")
        st.markdown("Scegli il tipo di appunti che vuoi caricare:")
        
        # IL TRUCCO UX: Il bivio per i telefoni
        tipo_file = st.radio("Formato:", ["📄 Documento PDF", "📸 Foto del Quaderno"], horizontal=True)
        
        # Mostriamo il caricatore giusto in base alla scelta
        if tipo_file == "📄 Documento PDF":
            file_input = st.file_uploader("👉 Clicca su 'Browse files' qui sotto per scegliere il PDF", type=['pdf'], key="elab_pdf")
        else:
            file_input = st.file_uploader("👉 Clicca su 'Browse files' qui sotto per scattare la foto", type=['png', 'jpg', 'jpeg'], key="elab_foto")
            
        bottone_elabora = st.button("Trascrivi, Schematizza & Riassumi 🪄", use_container_width=True)
    with col2:
        st.subheader("📄 Il tuo Materiale Pulito")
        if bottone_elabora and file_input is not None:
            with st.spinner("Decifrando e riordinando..."):
                try:
                    contenuti = []
                    # Prompt potente e strutturato
                    prompt_elab = """
                    Sei un assistente allo studio brillante. Analizza questo materiale (può essere testo o un'immagine di un quaderno scritto a mano).
                    Esegui i seguenti compiti in modo ordinato:
                    1. **TRASCRIZIONE**: Se è un'immagine, trascrivi fedelmente tutto il testo scritto a mano. Se è testo, correggi eventuali errori.
                    2. **SCHEMA LOGICO**: Crea uno schema puntato (usando grassetti per i concetti chiave) che riassuma la struttura dell'argomento.
                    3. **RIASSUNTO COMPLETO**: Scrivi un riassunto discorsivo, chiaro e dettagliato di tutti i concetti trattati.
                    Usa un tono professionale e formatta il testo in modo impeccabile.
                    """
                    contenuti.append(prompt_elab)

                    testo_da_salvare = ""
                    if file_input.type in ["image/png", "image/jpeg", "image/jpg"]:
                        immagine = Image.open(file_input)
                        contenuti.append(immagine)
                        testo_da_salvare = "Materiale basato su foto del quaderno caricata dall'utente."
                    elif file_input.type == "application/pdf":
                        lettore = PyPDF2.PdfReader(file_input)
                        for pagina in lettore.pages:
                            testo_da_salvare += pagina.extract_text() + "\n"
                        contenuti.append(testo_da_salvare)

                    # --- CHIAMATA A GEMINI ---
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=contenuti
                    )
                    
                    st.success("Elaborazione completata!")
                    st.session_state.testo_pulito_studente = response.text
                    
                    # Generiamo il PDF scaricabile!
                    st.session_state.riassunto_pdf = genera_pdf_scaricabile(response.text)
                    
                    st.markdown(response.text)
                    st.balloons()
                except Exception as e:
                    st.error(f"⚠️ Errore nei circuiti: {e}")
        
        # Se abbiamo elaborato, mostriamo il pulsante di download del PDF!
        if st.session_state.riassunto_pdf:
            st.divider()
            st.download_button(
                label="📩 Scarica il Riassunto Formattato in PDF",
                data=st.session_state.riassunto_pdf,
                file_name="riassunto_ioimparo.pdf",
                mime="application/pdf",
                use_container_width=True
            )

# ==========================================
# SCHEDA 2: FLASHCARD
# ==========================================
with tab2:
    st.subheader("⚡ Le tue Flashcard Automatiche")
    if st.session_state.testo_pulito_studente == "":
        st.warning("⚠️ Per generare le flashcard devi prima elaborare gli appunti nella Fase 1!")
    else:
        # Bottone per generare le flashcard
        if st.button("Genera Mazzo Flashcard Domanda/Risposta 🚀"):
            with st.spinner("Spremitura concetti in corso..."):
                try:
                    prompt_flash = f"Basandoti su questo testo, crea 5 Flashcard (Domanda e Risposta) per lo studio mnemonico dei concetti più difficili: {st.session_state.testo_pulito_studente}"
                    
                    response_flash = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt_flash
                    )
                    st.info(response_flash.text)
                except Exception as e:
                    st.error(f"⚠️ Errore: {e}")

# ==========================================
# SCHEDA 3: SIMULATORE D'ESAME
# ==========================================
with tab3:
    st.subheader("🧑‍🏫 Il Professore Virtuale")
    if st.session_state.testo_pulito_studente == "":
        st.warning("⚠️ Per iniziare l'esame devi prima elaborare gli appunti nella Fase 1!")
    else:
        st.markdown("Scrivi **'Iniziamo'** per far partire l'interrogazione sul materiale pulito.")
        
        # Mostriamo lo storico della chat
        for messaggio in st.session_state.messaggi_chat:
            with st.chat_message(messaggio["ruolo"]):
                st.markdown(messaggio["contenuto"])

        input_utente = st.chat_input("Tua risposta...")
        if input_utente:
            st.chat_message("user").markdown(input_utente)
            st.session_state.messaggi_chat.append({"ruolo": "user", "contenuto": input_utente})
            
            with st.chat_message("assistant"):
                with st.spinner("Il prof valuta..."):
                    try:
                        # Prompt del Prof esigente
                        prompt_prof = f"""
                        Sei un professore universitario esigente ma giusto.
                        Basati ESCLUSIVAMENTE su questo materiale pulito: {st.session_state.testo_pulito_studente[:4000]}
                        
                        Storico conversazione:
                        {str(st.session_state.messaggi_chat)}
                        
                        Se sta rispondendo a una tua domanda, dagli un voto da 1 a 30, correggi errori e fai una NUOVA domanda.
                        """
                        response_prof = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=prompt_prof
                        )
                        st.markdown(response_prof.text)
                        st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": response_prof.text})
                    except Exception as e:
                        st.error(f"⚠️ Errore: {e}")
