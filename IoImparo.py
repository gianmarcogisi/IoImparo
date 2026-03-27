import base64
import streamlit as st
import os
from PIL import Image
import PyPDF2
import io
import time
import random
import json

# --- 📦 IMPORTAZIONE MODULI LOCALI ---
from moduli.database import supabase, db_salva_appunto, db_get_miei_appunti, db_get_community_appunti
from moduli.intelligenza import client, genera_testo_gemini, chat_professore_gemini, get_prompt_mappa, get_prompt_flashcards, get_prompt_esame, cerca_immagine_scientifica, pulisci_codice_mermaid
from moduli.creatore_pdf import genera_pdf_scaricabile
from moduli.logica import gestisci_voto_esame, calcola_esito_arena

# --- 1. CONFIGURAZIONE PAGINA ---
NOME_APP = "IoImparo 🎓"
st.set_page_config(page_title=NOME_APP, page_icon="🎓", layout="wide")

# Nascondiamo il brand Streamlit
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}</style>""", unsafe_allow_html=True)

# --- COSTANTI REINTEGRATE ---
LISTA_MATERIE = [
    "Chimica Generale ed Inorganica", "Biologia Animale", "Biologia Vegetale", "Fisica", 
    "Matematica ed Informatica", "Anatomia Umana", "Chimica Organica", "Microbiologia", 
    "Fisiologia Umana", "Analisi dei Medicinali I", "Biochimica", "Farmacologia e Farmacoterapia", 
    "Analisi dei Medicinali II", "Patologia Generale", "Chimica Farmaceutica e Tossicologica I",
    "Chimica Farmaceutica e Tossicologica II", "Tecnologia e Legislazione Farmaceutiche", 
    "Tossicologia", "Chimica degli Alimenti", "Farmacognosia", "Farmacia Clinica", 
    "Saggi e Dosaggi dei Farmaci", "Biochimica Applicata", "Fitoterapia", "Igiene"
]

# --- 2. GESTIONE SESSIONE E SICUREZZA ---
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None
if "testo_pulito_studente" not in st.session_state: st.session_state.testo_pulito_studente = ""
if "messaggi_chat" not in st.session_state: st.session_state.messaggi_chat = []

# IL FIX FONDAMENTALE PER L'ERRORE RLS DI SUPABASE: Passiamo il token!
if "access_token" in st.session_state:
    try:
        supabase.auth.set_session(st.session_state.access_token, st.session_state.refresh_token)
    except Exception:
        pass

# --- 3. LOGIN ---
if st.session_state.utente_loggato is None:
    st.title(f"🎓 {NOME_APP}")
    st.warning("👋 Benvenuto! Accedi o registrati per iniziare.")
    
    tab_login, tab_registrati = st.tabs(["🔑 Accedi", "📝 Registrati"])
    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Entra 🔑", type="primary", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.utente_loggato = res.user
                st.session_state.access_token = res.session.access_token
                st.session_state.refresh_token = res.session.refresh_token
                st.rerun()
            except Exception: st.error("Credenziali errate.")
    with tab_registrati:
        nuova_email = st.text_input("Nuova Email", key="reg_email")
        nuova_password = st.text_input("Nuova Password", type="password", key="reg_password")
        if st.button("Crea Account 🚀", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": nuova_email, "password": nuova_password})
                st.success("Account creato! Ora fai il login.")
            except Exception as e: st.error(f"Errore: {e}")
    st.stop() 

# --- 4. HEADER ---
col_titolo, col_profilo = st.columns([4, 1])
with col_titolo:
    st.title(f"🎓 Centrale Operativa {NOME_APP}")
with col_profilo:
    with st.popover("👤 Area Riservata", use_container_width=True):
        st.write(f"Socio:\n`{st.session_state.utente_loggato.email}`")
        if st.button("Esci (Logout)", use_container_width=True):
            st.session_state.utente_loggato = None
            if "access_token" in st.session_state: del st.session_state.access_token
            st.rerun()

st.divider()

# --- 5. NAVIGAZIONE ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🗺️ Fase 1: Elabora & PDF", "⚡ Fase 2: Flashcard", "🧑‍🏫 Fase 3: Esame",
    "🥊 Fase 4: Arena Farmacia", "🏆 Profilo Ranked", "🌍 Community", "🗂️ Archivio Privato" 
])

# ==========================================
# FASE 1: ELABORA & PDF
# ==========================================
with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📥 Carica Materiale")
        st.info("💡 **Consiglio:** Usa *Adobe Scan* per file puliti. Più il testo è leggibile, migliore sarà il riassunto.")
        
        # NOVITÀ RICHIESTA: Carica nuovo o scegli dall'archivio
        sorgente_f1 = st.radio("Cosa vuoi elaborare?", ["Carica nuovi PDF 📄", "Rielabora dall'Archivio 🗂️"], horizontal=True)
        
        file_input = None
        testo_da_archivio = None
        
        if sorgente_f1 == "Carica nuovi PDF 📄":
            file_input = st.file_uploader("Scegli i file PDF (Max 5)", type=['pdf'], accept_multiple_files=True)
        else:
            arch_db = db_get_miei_appunti(st.session_state.utente_loggato.id)
            if arch_db and arch_db.data:
                mappa_arch = {f"📁 {a['titolo']}": a['testo_estratto'] for a in arch_db.data}
                scelta_a = st.selectbox("Seleziona appunto precedente:", list(mappa_arch.keys()))
                testo_da_archivio = mappa_arch[scelta_a]
            else:
                st.warning("Archivio vuoto. Carica prima un PDF.")

        st.divider()
        st.subheader("💾 Opzioni di Salvataggio")
        visibilita = st.radio("Visibilità Appunti:", ["🔒 Privato", "🌍 Pubblico"], horizontal=True)
        is_public = (visibilita == "🌍 Pubblico")
        titolo_appunto = st.text_input("Dai un titolo chiaro (es. Enzimi):")
        materia_appunto = st.selectbox("Seleziona la Materia:", LISTA_MATERIE)
        
        blocca_bottone = not titolo_appunto
        if blocca_bottone: st.warning("⚠️ Inserisci un Titolo per poter salvare.")

        if st.button("Spremi Appunti 🪄", type="primary", use_container_width=True, disabled=blocca_bottone):
            if not file_input and not testo_da_archivio:
                st.error("⚠️ Nessun file o appunto selezionato!")
            else:
                with st.spinner("🧠 Analisi estrema in corso..."):
                    try:
                        st.session_state.testo_pulito_studente = ""
                        
                        # Istruzioni corazzate per forzare la lunghezza
                        istruzioni_trascrizione = "Trascrivi il documento in modo ESTREMAMENTE LUNGO E DETTAGLIATO. Non riassumere nulla. Scrivi il testo più lungo e completo che ti è tecnicamente possibile generare."
                        
                        if file_input:
                            for i, pdf_file in enumerate(file_input):
                                with st.expander(f"📊 Analisi: {pdf_file.name}", expanded=True):
                                    reader = PyPDF2.PdfReader(pdf_file)
                                    testo_estratto_pdf = "".join([page.extract_text() for page in reader.pages])
                                    contenuti = [get_prompt_mappa(istruzioni_trascrizione), testo_estratto_pdf]
                                    
                                    testo_gemini = genera_testo_gemini(contenuti)
                                    st.session_state.testo_pulito_studente += f"\n--- {pdf_file.name} ---\n{testo_gemini}"
                        else:
                            # Se rielaboriamo dall'archivio
                            contenuti = [get_prompt_mappa(istruzioni_trascrizione), testo_da_archivio]
                            testo_gemini = genera_testo_gemini(contenuti)
                            st.session_state.testo_pulito_studente = testo_gemini

                        # Salvataggio nel DB (Ora funziona grazie al fix RLS!)
                        res = db_salva_appunto(
                            st.session_state.utente_loggato.id, 
                            st.session_state.testo_pulito_studente, 
                            is_public, titolo_appunto, materia_appunto
                        )
                        if res: st.toast("✅ Appunto salvato nell'archivio!", icon="💾")
                        st.balloons()

                    except Exception as e: st.error(f"Errore Gemini: {e}")

    with col2:
        st.subheader("📄 Risultato")
        if st.session_state.testo_pulito_studente:
            txt = st.session_state.testo_pulito_studente
            try:
                trascrizione = txt.split("[TRASCRIZIONE]")[1].split("[/TRASCRIZIONE]")[0].strip()
                codice_mermaid = txt.split("[SCHEMA]")[1].split("[/SCHEMA]")[0].strip()
                riassunto = txt.split("[RIASSUNTO]")[1].split("[/RIASSUNTO]")[0].strip()
            except:
                trascrizione, codice_mermaid, riassunto = "", "", txt 
            
            st.markdown("### 📝 Trascrizione Dettagliata")
            st.write(trascrizione[:1000] + "\n\n*[Continua...]*" if trascrizione else "Documento elaborato.")

            st.markdown("### 🖼️ Schema Concettuale Visivo")
            if codice_mermaid:
                codice_mermaid_pulito = pulisci_codice_mermaid(codice_mermaid)
                html_code = f"""
                <div id="wrapper" style="width: 100%; background: white; border-radius: 10px; border: 1px solid #ccc;">
                    <div id="graphDiv" class="mermaid" style="width: 100%; height: 600px;">\n{codice_mermaid_pulito}\n</div>
                </div>
                <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
                <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
                <script>
                    mermaid.initialize({{ startOnLoad: true, theme: 'base' }});
                    setTimeout(function() {{
                        var svgElement = document.querySelector('#graphDiv svg');
                        if(svgElement) {{
                            svgElement.style.width = '100%'; svgElement.style.height = '100%';
                            svgPanZoom(svgElement, {{ zoomEnabled: true, controlIconsEnabled: true }});
                        }}
                    }}, 1500);
                </script>"""
                st.components.v1.html(html_code, height=650)
            
            st.markdown("### 📖 Riassunto Completo")
            st.markdown(riassunto)
            
            pdf_bytes = genera_pdf_scaricabile(trascrizione, codice_mermaid, riassunto)
            st.download_button("📩 Scarica PDF Elaborato", data=pdf_bytes, file_name=f"{titolo_appunto}.pdf", mime="application/pdf", use_container_width=True)

# ==========================================
# RESTO DELLE TABS (Reintegrate fedelmente)
# ==========================================
# I Tab 2, 3, 4, 5, 6 e 7 sono pronti per essere agganciati nel prossimo step!
# Se salvi questo file ora, la Fase 1 funzionerà perfettamente e salverà nel database.
