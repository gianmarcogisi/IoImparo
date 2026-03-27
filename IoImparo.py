import streamlit as st
import PyPDF2
import json
import time
import random
import base64
import re
from PIL import Image

# --- 📦 IMPORTAZIONE MODULI LOCALI ---
from moduli.database import supabase, db_salva_appunto, db_get_miei_appunti, db_get_community_appunti
from moduli.intelligenza import (
    genera_testo_gemini, chat_professore_gemini, 
    get_prompt_mappa, get_prompt_flashcards, get_prompt_esame,
    cerca_immagine_scientifica, pulisci_codice_mermaid
)
from moduli.creatore_pdf import genera_pdf_scaricabile
from moduli.logica import gestisci_voto_esame, calcola_esito_arena

# --- 1. CONFIGURAZIONE & LISTE ---
NOME_APP = "IoImparo 🎓"
LISTA_MATERIE = [
    "Chimica Generale ed Inorganica", "Anatomia Umana", "Chimica Organica", "Biochimica", 
    "Farmacologia e Farmacoterapia", "Tossicologia", "Igiene", "Microbiologia", "Fisiologia"
]

st.set_page_config(page_title=NOME_APP, page_icon="🎓", layout="wide")
st.markdown("<style>#MainMenu, footer, header {visibility: hidden;}</style>", unsafe_allow_html=True)

# --- 2. GESTIONE SESSIONE ---
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None
if "testo_pulito_studente" not in st.session_state: st.session_state.testo_pulito_studente = ""
if "messaggi_chat" not in st.session_state: st.session_state.messaggi_chat = []
if "errori_totali" not in st.session_state: st.session_state.errori_totali = 0
if "esame_bocciato" not in st.session_state: st.session_state.esame_bocciato = False
if "flashcards" not in st.session_state: st.session_state.flashcards = []
if "indice_flashcard" not in st.session_state: st.session_state.indice_flashcard = 0

# --- 3. LOGIN & SICUREZZA ---
if st.session_state.utente_loggato is None:
    st.title(f"🎓 {NOME_APP}")
    tab_l, tab_r = st.tabs(["🔑 Accedi", "📝 Registrati"])
    with tab_l:
        email = st.text_input("Email", key="login_email")
        pwd = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Entra 🔑", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": pwd})
                st.session_state.utente_loggato = res.user
                st.rerun()
            except: st.error("Credenziali errate.")
    with tab_r:
        n_email = st.text_input("Nuova Email", key="reg_email")
        n_pwd = st.text_input("Nuova Password", type="password", key="reg_pwd")
        if st.button("Crea Account 🚀", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": n_email, "password": n_pwd})
                st.success("Registrato! Ora effettua il login.")
            except Exception as e: st.error(f"Errore: {e}")
    st.stop()

# --- 4. HEADER ---
c_tit, c_prof = st.columns([4, 1])
c_tit.title(f"🎓 Centrale Operativa {NOME_APP}")
with c_prof:
    with st.popover("👤 Area Riservata", use_container_width=True):
        st.write(f"Socio: `{st.session_state.utente_loggato.email}`")
        if st.button("Logout", use_container_width=True):
            st.session_state.utente_loggato = None
            st.rerun()

st.divider()

# --- 5. TABS (RISOLVE IL NAMERROR) ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🗺️ Fase 1: Elabora", "⚡ Fase 2: Flashcard", "🧑‍🏫 Fase 3: Esame", 
    "🥊 Fase 4: Arena", "🏆 Ranked", "🌍 Community", "🗂️ Archivio"
])

# --- TAB 1: ELABORA & PDF (DETTAGLIATO) ---
with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.info("💡 **Consiglio:** Usa *Adobe Scan* per caricare PDF puliti.")
        file_input = st.file_uploader("Scegli PDF (Max 5)", type=['pdf'], accept_multiple_files=True)
        vis = st.radio("Visibilità:", ["🔒 Privato", "🌍 Pubblico"], horizontal=True)
        titolo = st.text_input("Titolo Appunto:")
        materia = st.selectbox("Materia:", LISTA_MATERIE)
        
        if st.button("Spremi Appunti 🪄", type="primary", use_container_width=True, disabled=not titolo):
            if not file_input: st.error("Carica un file!")
            else:
                with st.spinner("🧠 Il Prof. Gemini sta studiando..."):
                    st.session_state.testo_pulito_studente = ""
                    for i, f in enumerate(file_input):
                        reader = PyPDF2.PdfReader(f)
                        testo_pdf = "".join([p.extract_text() for p in reader.pages])
                        resp = genera_testo_gemini([get_prompt_mappa("Analizza."), testo_pdf])
                        st.session_state.testo_pulito_studente += f"\n{resp}"
                    
                    db_salva_appunto(st.session_state.utente_loggato.id, st.session_state.testo_pulito_studente, (vis=="🌍 Pubblico"), titolo, materia)
                    st.balloons()

    with col2:
        if st.session_state.testo_pulito_studente:
            txt = st.session_state.testo_pulito_studente
            try:
                trasc = txt.split("[TRASCRIZIONE]")[1].split("[/TRASCRIZIONE]")[0].strip()
                riass = txt.split("[RIASSUNTO]")[1].split("[/RIASSUNTO]")[0].strip()
                mermaid = pulisci_codice_mermaid(txt.split("[SCHEMA]")[1].split("[/SCHEMA]")[0])
                
                st.markdown("### 📝 Trascrizione")
                st.write(trasc[:500] + "...")
                
                if mermaid:
                    st.markdown("### 🖼️ Schema Concettuale Visivo (Usa il mouse per lo Zoom)")
                    html_mermaid = f"""
                    <div id="graphDiv" class="mermaid" style="width: 100%; height: 500px; background: white; border: 1px solid #ccc;">{mermaid}</div>
                    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
                    <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
                    <script>
                        mermaid.initialize({{ startOnLoad: true }});
                        setTimeout(function() {{
                            var svg = document.querySelector('#graphDiv svg');
                            if(svg) svgPanZoom(svg, {{ zoomEnabled: true, controlIconsEnabled: true, fit: true }});
                        }}, 1000);
                    </script>
                    """
                    st.components.v1.html(html_mermaid, height=520)
                
                pdf = genera_pdf_scaricabile(trasc, mermaid, riass)
                st.download_button("📩 Scarica PDF Elaborato", data=pdf, file_name=f"{titolo}.pdf", mime="application/pdf")
            except: st.write(txt[:1500] + "...")

# --- TAB 2: FLASHCARD (VISIVE) ---
with tab2:
    st.subheader("⚡ Flashcard Dinamiche")
    res_db = db_get_miei_appunti(st.session_state.utente_loggato.id)
    if res_db and res_db.data:
        opzioni = {f"📁 {ap['titolo']} | {ap['materia']}": ap['testo_estratto'] for ap in res_db.data}
        scelta = st.selectbox("Seleziona argomento:", list(opzioni.keys()))
        
        if st.button("Genera Mazzo 🃏", type="primary"):
            with st.spinner("L'IA sta disegnando..."):
                raw = genera_testo_gemini([get_prompt_flashcards(10, opzioni[scelta])])
                try:
                    inizio = raw.find('[')
                    fine = raw.rfind(']') + 1
                    st.session_state.flashcards = json.loads(raw[inizio:fine])
                    st.session_state.indice_flashcard = 0
                    st.rerun()
                except: st.error("Errore nella generazione del mazzo.")

        if st.session_state.flashcards:
            idx = st.session_state.indice_flashcard
            carta = st.session_state.flashcards[idx]
            with st.container(border=True):
                st.write(f"### Carta {idx+1} di {len(st.session_state.flashcards)}")
                st.markdown(f"#### ❓ {carta.get('domanda')}")
                
                # --- MOTORE IMMAGINI REINTEGRATO ---
                q_v = carta.get('query_visuale', '')
                img = cerca_immagine_scientifica(carta.get('tipo_visuale'), q_v)
                if img: st.image(img, width=400, caption="Rappresentazione Visiva")
                
                with st.expander("Gira la carta 🔄"):
                    if q_v: st.info(f"🧪 Soggetto: {q_v}")
                    st.success(f"**Risposta:** {carta.get('risposta')}")
            
            c1, c2, c3 = st.columns(3)
            if c1.button("⬅️ Precedente", disabled=idx==0): 
                st.session_state.indice_flashcard -= 1
                st.rerun()
            if c3.button("Prossima ➡️", disabled=idx==len(st.session_state.flashcards)-1):
                st.session_state.indice_flashcard += 1
                st.rerun()

# --- TAB 3: ESAME (VOTI COLORATI + HOUSE) ---
with tab3:
    st.subheader("🧑‍🏫 Simulazione Esame Orale")
    if res_db and res_db.data:
        es_mappa = {f"📁 {a['titolo']}": a['testo_estratto'] for a in res_db.data}
        arg = st.selectbox("Argomento d'esame:", list(es_mappa.keys()))
        
        if st.button("🔄 Reset Esame"):
            st.session_state.messaggi_chat, st.session_state.errori_totali, st.session_state.esame_bocciato = [], 0, False
            st.rerun()

        for m in st.session_state.messaggi_chat:
            with st.chat_message(m["ruolo"]): st.markdown(m["contenuto"])

        if not st.session_state.esame_bocciato:
            if p_stud := st.chat_input("Rispondi al Prof..."):
                st.session_state.messaggi_chat.append({"ruolo": "user", "contenuto": p_stud})
                with st.chat_message("assistant"):
                    with st.spinner("Il Prof riflette..."):
                        resp = chat_professore_gemini(get_prompt_esame(es_mappa[arg]), st.session_state.messaggi_chat)
                        voto = gestisci_voto_esame(resp, st.session_state)
                        st.markdown(resp)
                        if voto > 0:
                            if voto < 12: st.error(f"🔴 VOTO: {voto}/30 - Disastro! (Errori: {st.session_state.errori_totali}/4)")
                            elif voto < 18: st.warning(f"🟡 VOTO: {voto}/30 - Mediocre! (Errori: {st.session_state.errori_totali}/4)")
                            else: st.success(f"🟢 VOTO: {voto}/30 - Eccellente!")
                        st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": resp})
                        if not st.session_state.esame_bocciato:
                            st.info("⌛ Il Professore sta scrivendo... (5s)")
                            time.sleep(5)
                            st.rerun()
        else: st.error("❌ BOCCIATO! Il professore ti ha cacciato dall'aula.")

# --- TAB 4: ARENA (MULTIPLAYER REINTEGRATO) ---
with tab4:
    st.subheader("🧪 Arena di Farmacia Live")
    # Qui incollerai la tua logica Arena dal monolito, richiamando calcola_esito_arena(is_host, sfida) 
    st.warning("🥊 Logica Arena pronta per l'innesto finale nel modulo logica.py!")

# --- TAB 5, 6, 7: UTILITY ---
with tab5: st.subheader("🏆 Profilo Ranked")
with tab6:
    st.subheader("🌍 Community")
    ric = st.text_input("🔍 Cerca appunti pubblici:")
    com = db_get_community_appunti(ric)
    if com and com.data:
        for a in com.data:
            with st.expander(f"📖 {a['titolo']} ({a['materia']})"):
                st.write(a['testo_estratto'][:500] + "...")
with tab7:
    st.subheader("🗂️ Tuo Archivio")
    pri = db_get_miei_appunti(st.session_state.utente_loggato.id, solo_privati=True)
    if pri and pri.data:
        for p in pri.data:
            st.write(f"📄 {p['titolo']} - {p['created_at'][:10]}")
