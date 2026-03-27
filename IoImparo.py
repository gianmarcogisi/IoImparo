import streamlit as st
import PyPDF2
import json
import time
import random
import base64
from PIL import Image

# --- 📦 L'ARMERIA MODULARE ---
from moduli.database import supabase, db_salva_appunto, db_get_miei_appunti, db_get_community_appunti
from moduli.intelligenza import genera_testo_gemini, chat_professore_gemini, get_prompt_mappa, get_prompt_flashcards, get_prompt_esame
from moduli.creatore_pdf import genera_pdf_scaricabile
from moduli.logica import gestisci_voto_esame, calcola_punti_arena

# --- 1. CONFIGURAZIONE & STILE ---
st.set_page_config(page_title="IoImparo 🎓", page_icon="🎓", layout="wide")
st.markdown("""<style>#MainMenu, footer, header {visibility: hidden;}</style>""", unsafe_allow_html=True)

# --- 2. INIZIALIZZAZIONE SESSIONE ---
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None
if "testo_pulito_studente" not in st.session_state: st.session_state.testo_pulito_studente = ""
if "messaggi_chat" not in st.session_state: st.session_state.messaggi_chat = []
if "errori_totali" not in st.session_state: st.session_state.errori_totali = 0
if "esame_bocciato" not in st.session_state: st.session_state.esame_bocciato = False

# --- 3. SISTEMA DI ACCESSO ---
if st.session_state.utente_loggato is None:
    st.title("🎓 Benvenuto in IoImparo")
    t_login, t_reg = st.tabs(["🔑 Accedi", "📝 Registrati"])
    with t_login:
        em = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.button("Entra", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password({"email": em, "password": pw})
                st.session_state.utente_loggato = res.user
                st.rerun()
            except: st.error("Accesso fallito.")
    with t_reg:
        nem = st.text_input("Nuova Email")
        npw = st.text_input("Nuova Password", type="password")
        if st.button("Crea Account", use_container_width=True):
            try:
                supabase.auth.sign_up({"email": nem, "password": npw})
                st.success("Registrato! Ora effettua l'accesso.")
            except Exception as e: st.error(f"Errore: {e}")
    st.stop()

# --- 4. DASHBOARD HEADER ---
c1, c2 = st.columns([4, 1])
c1.title(f"🎓 Centrale Operativa")
with c2:
    with st.popover("👤 Profilo", use_container_width=True):
        st.write(f"Utente: {st.session_state.utente_loggato.email}")
        if st.button("Esci"):
            st.session_state.utente_loggato = None
            st.rerun()

# --- 5. NAVIGAZIONE TABS ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🗺️ Fase 1: Elabora", "⚡ Fase 2: Flashcard", "🧑‍🏫 Fase 3: Esame", 
    "🥊 Fase 4: Arena", "🏆 Ranked", "🌍 Community", "🗂️ Archivio"
])

# --- TAB 1: ELABORAZIONE PDF ---
with tab1:
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.subheader("📥 Upload")
        files = st.file_uploader("Carica PDF (Max 5)", type=['pdf'], accept_multiple_files=True)
        titolo = st.text_input("Titolo Appunti")
        materia = st.selectbox("Materia", ["Farmacologia", "Chimica", "Anatomia", "Biochimica", "Igiene"])
        pubblico = st.checkbox("Condividi con la Community")
        
        if st.button("🪄 Elabora", type="primary", use_container_width=True) and titolo:
            if files:
                with st.spinner("🧠 Gemini sta studiando i tuoi file..."):
                    testo_totale = ""
                    for f in files:
                        reader = PyPDF2.PdfReader(f)
                        testo_estratto = "".join([p.extract_text() for p in reader.pages])
                        risultato = genera_testo_gemini([get_prompt_mappa("Analizza."), testo_estratto])
                        testo_totale += f"\n{risultato}"
                    
                    st.session_state.testo_pulito_studente = testo_totale
                    db_salva_appunto(st.session_state.utente_loggato.id, testo_totale, pubblico, titolo, materia)
                    st.balloons()
            else: st.warning("Inserisci almeno un file!")

    with col_b:
        st.subheader("📄 Anteprima")
        if st.session_state.testo_pulito_studente:
            st.markdown(st.session_state.testo_pulito_studente[:2000] + "...")

# --- TAB 2: FLASHCARD ---
with tab2:
    st.subheader("⚡ Flashcard Intelligenti")
    miei_appunti = db_get_miei_appunti(st.session_state.utente_loggato.id)
    if miei_appunti and miei_appunti.data:
        opzioni = {f"📁 {a['titolo']}": a['testo_estratto'] for a in miei_appunti.data}
        scelta = st.selectbox("Seleziona argomento", list(opzioni.keys()))
        
        if st.button("🃏 Genera Mazzo"):
            with st.spinner("Creazione carte in corso..."):
                raw_cards = genera_testo_gemini(get_prompt_flashcards(10, opzioni[scelta]))
                try:
                    inizio = raw_cards.find('[')
                    fine = raw_cards.rfind(']') + 1
                    st.session_state.flashcards = json.loads(raw_cards[inizio:fine])
                    st.session_state.indice_flashcard = 0
                    st.rerun()
                except: st.error("Errore nel formato delle carte. Riprova.")

        if "flashcards" in st.session_state and st.session_state.flashcards:
            idx = st.session_state.indice_flashcard
            carta = st.session_state.flashcards[idx]
            with st.container(border=True):
                st.write(f"Carta {idx+1} di {len(st.session_state.flashcards)}")
                st.markdown(f"### {carta['domanda']}")
                with st.expander("Gira la carta 🔄"):
                    st.success(carta['risposta'])
            
            c1, c2, c3 = st.columns(3)
            if c1.button("⬅️ Precedente", disabled=idx==0): 
                st.session_state.indice_flashcard -= 1
                st.rerun()
            if c3.button("Prossima ➡️", disabled=idx==len(st.session_state.flashcards)-1):
                st.session_state.indice_flashcard += 1
                st.rerun()

# --- TAB 3: ESAME ORALE ---
with tab3:
    st.subheader("🧑‍🏫 Esame con il Prof. House")
    miei_esami = db_get_miei_appunti(st.session_state.utente_loggato.id)
    if miei_esami and miei_esami.data:
        esame_opzioni = {f"📁 {a['titolo']}": a['testo_estratto'] for a in miei_esami.data}
        argomento = st.selectbox("Cosa interroghiamo oggi?", list(esame_opzioni.keys()))
        
        if st.button("🔄 Ricomincia Esame"):
            st.session_state.messaggi_chat, st.session_state.errori_totali, st.session_state.esame_bocciato = [], 0, False
            st.rerun()

        for m in st.session_state.messaggi_chat:
            with st.chat_message(m["ruolo"]): st.markdown(m["contenuto"])

        if not st.session_state.esame_bocciato:
            if risp_studente := st.chat_input("Rispondi qui..."):
                st.session_state.messaggi_chat.append({"ruolo": "user", "contenuto": risp_studente})
                with st.chat_message("assistant"):
                    prompt_prof = get_prompt_esame(esame_opzioni[argomento])
                    r_prof = chat_professore_gemini(prompt_prof, st.session_state.messaggi_chat)
                    voto = gestisci_voto_esame(r_prof, st.session_state)
                    
                    st.markdown(r_prof)
                    if voto > 0:
                        if voto < 18: st.error(f"🔴 Voto: {voto}/30 (Errori: {st.session_state.errori_totali}/4)")
                        else: st.success(f"🟢 Voto: {voto}/30")
                    
                    st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": r_prof})
                    if not st.session_state.esame_bocciato:
                        time.sleep(5)
                        st.rerun()
        else: st.error("❌ BOCCIATO. Il professore ti ha cacciato dall'aula.")

# --- TAB 4: ARENA MULTIPLAYER ---
with tab4:
    st.subheader("🧪 Arena di Farmacia")
    
    # Riconnessione Automatica
    if "id_sfida" not in st.session_state:
        uid = st.session_state.utente_loggato.id
        check = supabase.table("sfide_multiplayer").select("id").or_(f"host_id.eq.{uid},guest_id.eq.{uid}").in_("stato", ["waiting", "playing"]).execute()
        if check.data: st.session_state.id_sfida = check.data[0]['id']

    if "id_sfida" not in st.session_state:
        mode = st.radio("Scegli:", ["Crea Sfida 🏗️", "Unisciti ⚔️"], horizontal=True)
        if mode == "Crea Sfida 🏗️":
            materia_sfida = st.selectbox("Materia Arena", ["Chimica", "Farmacologia", "Tossicologia"])
            if st.button("Genera PIN"):
                pin = str(random.randint(1000, 9999))
                res = supabase.table("sfide_multiplayer").insert({
                    "pin": pin, "materia": materia_sfida, "host_id": st.session_state.utente_loggato.id, "stato": "waiting"
                }).execute()
                st.session_state.id_sfida = res.data[0]['id']
                st.rerun()
        else:
            pin_in = st.text_input("Inserisci PIN Arena")
            if st.button("Entra"):
                res = supabase.table("sfide_multiplayer").select("*").eq("pin", pin_in).eq("stato", "waiting").execute()
                if res.data:
                    supabase.table("sfide_multiplayer").update({"guest_id": st.session_state.utente_loggato.id, "stato": "playing"}).eq("id", res.data[0]['id']).execute()
                    st.session_state.id_sfida = res.data[0]['id']
                    st.rerun()
    else:
        # Logica di Gioco Live
        sfida = supabase.table("sfide_multiplayer").select("*").eq("id", st.session_state.id_sfida).execute().data[0]
        if sfida['stato'] == 'waiting':
            st.warning(f"⏳ PIN Arena: {sfida['pin']} | In attesa dello sfidante...")
            time.sleep(3)
            st.rerun()
        elif sfida['stato'] == 'playing':
            is_host = (st.session_state.utente_loggato.id == sfida['host_id'])
            col_p, col_r, m_ping, s_ping = calcola_punti_arena(is_host, sfida)
            
            # Aggiornamento Ping (AFK Check)
            supabase.table("sfide_multiplayer").update({m_ping: time.time()}).eq("id", sfida['id']).execute()
            
            st.metric("Punteggio Host", sfida['punteggio_host'])
            st.metric("Punteggio Guest", sfida['punteggio_guest'])
            
            if st.button("Esci dall'Arena"):
                supabase.table("sfide_multiplayer").update({"stato": "finished"}).eq("id", sfida['id']).execute()
                del st.session_state.id_sfida
                st.rerun()

# --- TAB 5, 6, 7: UTILITY ---
with tab5:
    st.subheader("🏆 Classifica Ranked")
    st.write("Dati in fase di calcolo...")

with tab6:
    st.subheader("🌍 Community")
    cerca = st.text_input("Cerca materiale pubblico")
    res_c = db_get_community_appunti(cerca)
    if res_c and res_c.data:
        for a in res_c.data:
            with st.expander(f"📖 {a['titolo']} ({a['materia']})"):
                st.markdown(a['testo_estratto'][:500] + "...")

with tab7:
    st.subheader("🗂️ Tuo Archivio")
    miei_p = db_get_miei_appunti(st.session_state.utente_loggato.id, solo_privati=True)
    if miei_p and miei_p.data:
        for p in miei_p.data:
            st.write(f"📄 {p['titolo']} - {p['created_at'][:10]}")
