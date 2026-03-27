import streamlit as st
import PyPDF2
import json
import time
import random
import base64
from PIL import Image

# --- 📦 IMPORTAZIONE MODULI (L'Armeria Modulare) ---
from moduli.database import supabase, db_salva_appunto, db_get_miei_appunti, db_get_community_appunti
from moduli.intelligenza import (
    genera_testo_gemini, chat_professore_gemini, 
    get_prompt_mappa, get_prompt_flashcards, get_prompt_esame,
    cerca_immagine_scientifica, pulisci_codice_mermaid
)
from moduli.creatore_pdf import genera_pdf_scaricabile
from moduli.logica import gestisci_voto_esame, calcola_esito_arena

# --- 1. CONFIGURAZIONE & STILE ---
NOME_APP = "IoImparo 🎓"
LISTA_MATERIE = [
    "Chimica Generale ed Inorganica", "Anatomia Umana", "Chimica Organica", 
    "Biochimica", "Farmacologia e Farmacoterapia", "Tossicologia", "Igiene"
]

st.set_page_config(page_title=NOME_APP, page_icon="🎓", layout="wide")
st.markdown("<style>#MainMenu, footer, header {visibility: hidden;}</style>", unsafe_allow_html=True)

# --- 2. GESTIONE SESSIONE ---
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None
if "testo_pulito_studente" not in st.session_state: st.session_state.testo_pulito_studente = ""
if "messaggi_chat" not in st.session_state: st.session_state.messaggi_chat = []
if "errori_totali" not in st.session_state: st.session_state.errori_totali = 0
if "esame_bocciato" not in st.session_state: st.session_state.esame_bocciato = False

# --- 3. SISTEMA DI LOGIN ---
if st.session_state.utente_loggato is None:
    st.title(f"🎓 {NOME_APP}")
    tab_l, tab_r = st.tabs(["🔑 Accedi", "📝 Registrati"])
    with tab_l:
        email = st.text_input("Email", key="l_email")
        pwd = st.text_input("Password", type="password", key="l_pwd")
        if st.button("Entra 🔑", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": pwd})
                st.session_state.utente_loggato = res.user
                st.rerun()
            except: st.error("Credenziali non valide.")
    with tab_r:
        n_email = st.text_input("Nuova Email", key="r_email")
        n_pwd = st.text_input("Nuova Password", type="password", key="r_pwd")
        if st.button("Crea Account 🚀", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": n_email, "password": n_pwd})
                st.success("Account creato! Ora effettua l'accesso.")
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

# --- 5. NAVIGAZIONE TABS ---
t1, t2, t3, t4, t5, t6, t7 = st.tabs([
    "🗺️ Fase 1: Elabora", "⚡ Fase 2: Flashcard", "🧑‍🏫 Fase 3: Esame", 
    "🥊 Fase 4: Arena", "🏆 Ranked", "🌍 Community", "🗂️ Archivio"
])

# --- TAB 1: ELABORA & PDF ---
with t1:
    col_u, col_r = st.columns([1, 2])
    with col_u:
        st.subheader("📥 Carica Materiale")
        st.info("💡 **Consiglio:** Carica PDF puliti per risultati migliori.")
        file_input = st.file_uploader("Scegli PDF (Max 5)", type=['pdf'], accept_multiple_files=True)
        vis = st.radio("Visibilità:", ["🔒 Privato", "🌍 Pubblico"], horizontal=True)
        titolo = st.text_input("Titolo Appunto (es. Enzimi):")
        materia = st.selectbox("Materia:", LISTA_MATERIE)
        
        if st.button("Spremi Appunti 🪄", type="primary", use_container_width=True, disabled=not titolo):
            if not file_input: st.error("Carica un file!")
            else:
                with st.spinner("🧠 Analisi in corso..."):
                    st.session_state.testo_pulito_studente = ""
                    for i, f in enumerate(file_input):
                        reader = PyPDF2.PdfReader(f)
                        testo_pdf = "".join([p.extract_text() for p in reader.pages])
                        resp = genera_testo_gemini([get_prompt_mappa("Analizza."), testo_pdf])
                        st.session_state.testo_pulito_studente += f"\n{resp}"
                    
                    db_salva_appunto(st.session_state.utente_loggato.id, st.session_state.testo_pulito_studente, (vis=="🌍 Pubblico"), titolo, materia)
                    st.balloons()

    with col_r:
        st.subheader("📄 Anteprima")
        if st.session_state.testo_pulito_studente:
            txt = st.session_state.testo_pulito_studente
            try:
                trasc = txt.split("[TRASCRIZIONE]")[1].split("[/TRASCRIZIONE]")[0].strip()
                riass = txt.split("[RIASSUNTO]")[1].split("[/RIASSUNTO]")[0].strip()
                mermaid = pulisci_codice_mermaid(txt.split("[SCHEMA]")[1].split("[/SCHEMA]")[0])
                
                st.markdown("### 📝 Trascrizione")
                st.write(trasc[:500] + "...")
                
                if mermaid:
                    st.markdown("### 🖼️ Schema Interattivo")
                    st.mermaid(mermaid) # Se usi streamlit-mermaid, altrimenti usa l'HTML custom che avevi
                
                pdf = genera_pdf_scaricabile(trasc, mermaid, riass)
                st.download_button("📩 Scarica PDF Elaborato", data=pdf, file_name=f"{titolo}.pdf", mime="application/pdf")
            except: st.write(txt[:2000] + "...")

# --- TAB 2: FLASHCARD ---
with t2:
    st.subheader("⚡ Flashcard Visive")
    appunti_db = db_get_miei_appunti(st.session_state.utente_loggato.id)
    if appunti_db and appunti_db.data:
        mappa = {f"📁 {a['titolo']}": a['testo_estratto'] for a in appunti_db.data}
        scelta = st.selectbox("Scegli argomento:", list(mappa.keys()), key="sel_f2")
        
        if st.button("Genera Mazzo 🃏", type="primary"):
            with st.spinner("L'IA sta disegnando..."):
                raw = genera_testo_gemini([get_prompt_flashcards(10, mappa[scelta])])
                st.session_state.flashcards = json.loads(raw[raw.find('['):raw.rfind(']')+1])
                st.session_state.indice_flashcard = 0
                st.rerun()

        if "flashcards" in st.session_state:
            idx = st.session_state.indice_flashcard
            carta = st.session_state.flashcards[idx]
            with st.container(border=True):
                st.write(f"### Carta {idx+1} di {len(st.session_state.flashcards)}")
                st.markdown(f"#### ❓ {carta['domanda']}")
                img = cerca_immagine_scientifica(carta.get('tipo_visuale'), carta.get('query_visuale'))
                if img: st.image(img, width=400)
                with st.expander("Gira la carta 🔄"):
                    st.success(f"**Risposta:** {carta['risposta']}")
            
            c1, c2, c3 = st.columns(3)
            if c1.button("⬅️", disabled=idx==0): 
                st.session_state.indice_flashcard -= 1
                st.rerun()
            if c3.button("➡️", disabled=idx==len(st.session_state.flashcards)-1):
                st.session_state.indice_flashcard += 1
                st.rerun()

# --- TAB 3: ESAME ---
with t3:
    st.subheader("🧑‍🏫 Esame Orale con il Prof. House")
    if appunti_db and appunti_db.data:
        es_mappa = {f"📁 {a['titolo']}": a['testo_estratto'] for a in appunti_db.data}
        s_esame = st.selectbox("Materia d'esame:", list(es_mappa.keys()), key="sel_f3")
        
        if st.button("🔄 Reset Esame"):
            st.session_state.messaggi_chat, st.session_state.errori_totali, st.session_state.esame_bocciato = [], 0, False
            st.rerun()

        for m in st.session_state.messaggi_chat:
            with st.chat_message(m["ruolo"]): st.markdown(m["contenuto"])

        if not st.session_state.esame_bocciato:
            if p_stud := st.chat_input("Rispondi..."):
                st.session_state.messaggi_chat.append({"ruolo": "user", "contenuto": p_stud})
                with st.chat_message("assistant"):
                    resp = chat_professore_gemini(get_prompt_esame(es_mappa[s_esame]), st.session_state.messaggi_chat)
                    voto = gestisci_voto_esame(resp, st.session_state)
                    st.markdown(resp)
                    if voto > 0:
                        if voto < 18: st.error(f"🔴 VOTO: {voto}/30 (Errori: {st.session_state.errori_totali}/4)")
                        elif voto < 24: st.warning(f"🟡 VOTO: {voto}/30")
                        else: st.success(f"🟢 VOTO: {voto}/30")
                    st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": resp})
                    if not st.session_state.esame_bocciato:
                        time.sleep(5)
                        st.rerun()
        else: st.error("❌ BOCCIATO! Il professore ti ha cacciato dall'aula.")

# --- TAB 4: ARENA ---
with tab4:
    st.subheader("🧪 Arena di Farmacia Live")
    # Qui inserisci la tua logica Arena che usa supabase.table("sfide_multiplayer")
    # e richiama calcola_esito_arena() dal modulo logica.

# --- TAB 6: COMMUNITY ---
with tab6:
    st.subheader("🌍 Community")
    cerca = st.text_input("🔍 Cerca appunti pubblici:")
    res_c = db_get_community_appunti(cerca)
    if res_c and res_c.data:
        for a in res_c.data:
            with st.expander(f"📖 {a['titolo']} ({a['materia']})"):
                st.write(a['testo_estratto'][:500] + "...")

# --- TAB 7: ARCHIVIO ---
with tab7:
    st.subheader("🗂️ Tuo Archivio Privato")
    privati = db_get_miei_appunti(st.session_state.utente_loggato.id, solo_privati=True)
    if privati and privati.data:
        for p in privati.data:
            st.write(f"📄 {p['titolo']} - {p['created_at'][:10]}")
