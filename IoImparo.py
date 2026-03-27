import base64
import streamlit as st
import os
from PIL import Image
import PyPDF2
import io
import time
import random
import json
import urllib.parse
import requests

# --- 📦 IMPORTAZIONE MODULI LOCALI ---
from moduli.database import supabase, db_salva_appunto, db_get_miei_appunti, db_get_community_appunti
from moduli.intelligenza import genera_testo_gemini, chat_professore_gemini, get_prompt_mappa, get_prompt_flashcards, get_prompt_esame, cerca_immagine_scientifica, pulisci_codice_mermaid
from moduli.creatore_pdf import genera_pdf_scaricabile
from moduli.logica import gestisci_voto_esame, calcola_esito_arena

# --- 1. CONFIGURAZIONE PAGINA ---
NOME_APP = "IoImparo 🎓"
st.set_page_config(page_title=NOME_APP, page_icon="🎓", layout="wide")

st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}</style>""", unsafe_allow_html=True)

# --- COSTANTI ---
LISTA_MATERIE = [
    "Chimica Generale ed Inorganica", "Biologia Animale", "Biologia Vegetale", "Fisica", 
    "Matematica ed Informatica", "Anatomia Umana", "Chimica Organica", "Microbiologia", 
    "Fisiologia Umana", "Analisi dei Medicinali I", "Biochimica", "Farmacologia e Farmacoterapia", 
    "Analisi dei Medicinali II", "Patologia Generale", "Chimica Farmaceutica e Tossicologica I",
    "Chimica Farmaceutica e Tossicologica II", "Tecnologia e Legislazione Farmaceutiche", 
    "Tossicologia", "Chimica degli Alimenti", "Farmacognosia", "Farmacia Clinica", 
    "Saggi e Dosaggi dei Farmaci", "Biochimica Applicata", "Fitoterapia", "Igiene"
]

# --- 2. GESTIONE SESSIONE ---
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None
if "testo_pulito_studente" not in st.session_state: st.session_state.testo_pulito_studente = ""
if "messaggi_chat" not in st.session_state: st.session_state.messaggi_chat = []

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
                            contenuti = [get_prompt_mappa(istruzioni_trascrizione), testo_da_archivio]
                            testo_gemini = genera_testo_gemini(contenuti)
                            st.session_state.testo_pulito_studente = testo_gemini

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
# FASE 2: FLASHCARD
# ==========================================
with tab2:
    st.subheader("⚡ Flashcard Visive & Dinamiche")
    
    if "flashcards" not in st.session_state: st.session_state.flashcards = []
    if "indice_flashcard" not in st.session_state: st.session_state.indice_flashcard = 0
    
    opzioni_appunti = {}
    if st.session_state.testo_pulito_studente:
        opzioni_appunti["✨ Appunti Fase 1"] = st.session_state.testo_pulito_studente
    res_db = db_get_miei_appunti(st.session_state.utente_loggato.id)
    if res_db and res_db.data:
        for ap in res_db.data:
            etichetta = f"📁 {ap['titolo']} | {ap['materia']}"
            opzioni_appunti[etichetta] = ap['testo_estratto']
        
    if not opzioni_appunti:
        st.warning("⚠️ Carica qualcosa in Fase 1 o nell'Archivio!")
    else:
        scelta_titolo = st.selectbox("📚 Argomento:", list(opzioni_appunti.keys()), key="sel_f2")
        testo_f2 = opzioni_appunti[scelta_titolo]

        col_f1, col_f2 = st.columns([2, 1])
        with col_f1: num_cards = st.slider("Numero carte:", 5, 30, 10)
        with col_f2:
            st.write("")
            if st.button("Genera Mazzo Visivo 🃏", type="primary", use_container_width=True, key="cards_gen_btn"):
                with st.spinner(f"⏳ Il Prof. Gemini sta studiando '{scelta_titolo.split('|')[0]}' per te..."):
                    
                    prompt_flash = get_prompt_flashcards(num_cards, testo_f2)

                    try:
                        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_flash)
                        testo = res.text
                        
                        inizio = testo.find('[')
                        fine = testo.rfind(']') + 1
                        
                        if inizio == -1 or fine <= 0:
                            st.error("L'IA non ha generato un array JSON.")
                            st.code(testo)
                        else:
                            st.session_state.flashcards = json.loads(testo[inizio:fine])
                            st.session_state.indice_flashcard = 0
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Errore tecnico IA: {str(e)}")

        if st.session_state.flashcards:
            idx = st.session_state.indice_flashcard
            carta = st.session_state.flashcards[idx]
            
            with st.container(border=True):
                st.write(f"### Carta {idx+1} di {len(st.session_state.flashcards)}")
                st.markdown(f"#### ❓ {carta.get('domanda')}")
                
                q_v_raw = str(carta.get('nome_molecola_inglese_pubchem', carta.get('query_visuale', ''))).strip()
                img_url = cerca_immagine_scientifica(carta.get('tipo_visuale'), q_v_raw)
                if img_url: st.image(img_url, width=400)
                
                with st.expander("Gira la Carta 🔄"):
                    if q_v_raw:
                        st.info(f"🧪 **Soggetto:** {q_v_raw}")
                    
                    st.success(f"**Risposta:** {carta.get('risposta')}")

            c1, c2, c3 = st.columns(3)
            if c1.button("⬅️", disabled=idx==0): 
                st.session_state.indice_flashcard -= 1
                st.rerun()
            if c3.button("➡️", disabled=idx==len(st.session_state.flashcards)-1):
                st.session_state.indice_flashcard += 1
                st.rerun()

# ==========================================
# FASE 3: ESAME ORALE
# ==========================================
with tab3:
    st.subheader("🧑‍🏫 Simulazione Esame Orale")
    
    if "errori_totali" not in st.session_state: st.session_state.errori_totali = 0
    if "esame_bocciato" not in st.session_state: st.session_state.esame_bocciato = False

    opzioni_esame = {}
    if st.session_state.testo_pulito_studente:
        opzioni_esame["✨ Appunti Fase 1"] = st.session_state.testo_pulito_studente
    res_db = db_get_miei_appunti(st.session_state.utente_loggato.id)
    if res_db and res_db.data:
        for ap in res_db.data:
            etichetta = f"📁 {ap['titolo']} | {ap['materia']}"
            opzioni_esame[etichetta] = ap['testo_estratto']

    if opzioni_esame:
        scelta_e = st.selectbox("Argomento esame:", list(opzioni_esame.keys()), key="sel_e")
        
        if st.button("🔄 Reset Esame"):
            st.session_state.messaggi_chat = []
            st.session_state.errori_totali = 0
            st.session_state.esame_bocciato = False
            st.rerun()

        for msg in st.session_state.messaggi_chat:
            with st.chat_message(msg["ruolo"]): st.markdown(msg["contenuto"])

        if len(st.session_state.messaggi_chat) == 0:
            msg_i = "Buongiorno. Mi dica tutto quello che sa. Scriva 'Iniziamo' se ha fegato."
            st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": msg_i})
            st.rerun()

        if not st.session_state.esame_bocciato:
            if p_studente := st.chat_input("Rispondi... (Il libretto non dimentica)"):
                st.session_state.messaggi_chat.append({"ruolo": "user", "contenuto": p_studente})
                
                with st.chat_message("assistant"):
                    with st.spinner("Il Prof. annota le tue mancanze..."):
                        sys_p = get_prompt_esame(opzioni_esame[scelta_e])
                        r_prof = chat_professore_gemini(sys_p, st.session_state.messaggi_chat)    
                        
                        voto = gestisci_voto_esame(r_prof)
                        
                        if voto > 0:
                            if st.session_state.esame_bocciato:
                                st.session_state.esame_bocciato = True
                                msg_bocciato = f"🔴 VOTO: {voto}/30. Quarto errore totale. La sua preparazione fa acqua da tutte le parti. Prenda il suo libretto, è **BOCCIATO**. E chiuda la porta uscendo!"
                                st.error(msg_bocciato)
                                st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": msg_bocciato})
                                time.sleep(4)
                                st.rerun()
                            else:
                                commento = r_prof.split("VOTO:")[0]
                                nuova_d = r_prof.split(str(voto))[1] if str(voto) in r_prof else ""

                                st.markdown(commento)
                                if voto < 18: st.error(f"🔴 VOTO: {voto}/30 - Insufficiente!")
                                elif voto < 24: st.warning(f"🟡 VOTO: {voto}/30 - Poteva fare di meglio.")
                                else: st.success(f"🟢 VOTO: {voto}/30 - Eccellente!")
                                
                                st.markdown(f"**Prossima Domanda:** {nuova_d}")
                                st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": r_prof})
                                
                                st.info("⌛ Il Professore ti scruta in silenzio... (5s)")
                                time.sleep(5)
                                st.rerun()
                        else:
                            st.markdown(r_prof)
                            st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": r_prof})
                            st.rerun()
        else:
            st.error("❌ ESAME FALLITO. Il professore ti ha bocciato. Ripresentati al prossimo appello (Premi 'Reset Esame').")

# ==========================================
# FASE 4: ARENA FARMACIA
# ==========================================
with tab4:
    st.subheader("🧪 Arena di Farmacia")

    if "id_sfida_attiva" not in st.session_state:
        uid = st.session_state.utente_loggato.id
        res_host = supabase.table("sfide_multiplayer").select("id").eq("host_id", uid).in_("stato", ["waiting", "playing"]).execute()
        res_guest = supabase.table("sfide_multiplayer").select("id").eq("guest_id", uid).eq("stato", "playing").execute()
        
        if res_host.data:
            st.session_state.id_sfida_attiva = res_host.data[0]['id']
            st.toast("Bentornato nell'Arena! Ti abbiamo ricollegato in automatico.", icon="🔌")
        elif res_guest.data:
            st.session_state.id_sfida_attiva = res_guest.data[0]['id']
            st.toast("Bentornato nell'Arena! Ti abbiamo ricollegato in automatico.", icon="🔌")

    if "id_sfida_attiva" not in st.session_state:
        scelta_arena = st.radio("Cosa vuoi fare?", ["Crea Sfida 🏗️", "Unisciti a Sfida ⚔️"], horizontal=True)

        if scelta_arena == "Crea Sfida 🏗️":
            materia = st.selectbox("Seleziona l'esame:", LISTA_MATERIE)
            file_sfida = st.file_uploader("Carica materiale", type=['pdf', 'jpg', 'png'], key="file_arena")
            
            if st.button("Genera Arena 🏟️", type="primary") and file_sfida:
                with st.spinner("Preparando il ring (10 domande)..."):
                    try:
                        contenuti = ["Estrai tutto il testo per una sfida tra studenti:"]
                        if file_sfida.type == "application/pdf":
                            reader = PyPDF2.PdfReader(file_sfida)
                            testo_arena = "".join([page.extract_text() for page in reader.pages])
                        else: testo_arena = Image.open(file_sfida)
                            
                        prompt_quiz = f"""Genera esattamente 10 domande su questo testo di {materia}: le prime 5 a risposta multipla e le successive 5 a risposta aperta.
Rispondi SOLO ed ESCLUSIVAMENTE con un array JSON avente questa struttura esatta:
[
  {{"tipo": "multipla", "domanda": "...", "opzioni": ["A", "B", "C", "D"], "corretta": "A"}},
  {{"tipo": "aperta", "domanda": "..."}}
]
Devono essere 10 elementi in totale (5 multipla, 5 aperta). Nessun testo prima o dopo l'array JSON.
Testo: {str(testo_arena)[:3000]}"""
                        
                        quiz_raw = genera_testo_gemini([prompt_quiz])
                        quiz_pulito = quiz_raw.strip().replace("```json", "").replace("```", "")
                        
                        nuovo_pin = str(random.randint(1000, 9999))
                        res_insert = supabase.table("sfide_multiplayer").insert({
                            "pin": nuovo_pin,
                            "materia": materia,
                            "host_id": st.session_state.utente_loggato.id,
                            "appunti_testo": str(testo_arena)[:3000],
                            "domande_json": json.loads(quiz_pulito),
                            "stato": "waiting"
                        }).execute()
                        
                        st.session_state.id_sfida_attiva = res_insert.data[0]['id']
                        st.success(f"🔥 Arena Creata! Dai questo PIN: {nuovo_pin}")
                        time.sleep(2)
                        st.rerun()
                    except Exception as e: st.error(f"Errore creazione arena (forse il testo era strano): {e}")

        else:
            pin_inserito = st.text_input("Inserisci il PIN di 4 cifre:")
            if st.button("Entra nel Ring 🥊", type="primary"):
                res_sfida = supabase.table("sfide_multiplayer").select("*").eq("pin", pin_inserito).eq("stato", "waiting").execute()
                if res_sfida.data:
                    id_sfida = res_sfida.data[0]['id']
                    supabase.table("sfide_multiplayer").update({"guest_id": st.session_state.utente_loggato.id, "stato": "playing"}).eq("id", id_sfida).execute()
                    
                    st.session_state.id_sfida_attiva = id_sfida
                    st.success("✅ Sei dentro! Preparati...")
                    time.sleep(1)
                    st.rerun()
                else: st.error("PIN non trovato o sfida già iniziata.")

    else:
        res_live = supabase.table("sfide_multiplayer").select("*").eq("id", st.session_state.id_sfida_attiva).execute()
        
        if res_live.data:
            sfida = res_live.data[0]
            
            if sfida['stato'] == 'waiting':
                st.warning(f"⏳ PIN: {sfida['pin']} | In attesa dello sfidante...")
                if st.button("Annulla Sfida", type="secondary"): 
                    supabase.table("sfide_multiplayer").update({"stato": "finished"}).eq("id", sfida['id']).execute()
                    del st.session_state.id_sfida_attiva
                    st.rerun()
                else:
                    with st.spinner("Cerco lo sfidante... (La pagina si aggiorna da sola)"):
                        time.sleep(3) 
                        st.rerun()    
            
            elif sfida['stato'] == 'playing':
                st.divider()
                
                is_host = (st.session_state.utente_loggato.id == sfida['host_id'])
                colonna_punteggio, colonna_risposte, mio_ping_col, suo_ping_col = calcola_esito_arena(is_host, sfida)
                
                adesso = time.time()
                supabase.table("sfide_multiplayer").update({mio_ping_col: adesso}).eq("id", sfida['id']).execute()
                
                suo_ping = sfida.get(suo_ping_col, 0)
                if suo_ping > 0 and (adesso - suo_ping) > 300: 
                    st.error("🚨 L'avversario è fuggito o si è disconnesso da oltre 5 minuti!")
                    if st.button("Reclama Vittoria a Tavolino 🏆", type="primary"):
                        supabase.table("sfide_multiplayer").update({
                            "stato": "finished",
                            colonna_punteggio: 300
                        }).eq("id", sfida['id']).execute()
                        st.balloons()
                        st.success("Hai vinto a tavolino per abbandono dell'avversario!")
                        time.sleep(3)
                        st.rerun()
                    st.stop() 
                
                risposte_date = sfida.get(colonna_risposte, [])
                if risposte_date is None: risposte_date = []
                indice = len(risposte_date)
                
                col1, col2 = st.columns(2)
                col1.metric("🔴 Punteggio Host", f"{sfida['punteggio_host']} / 300")
                col2.metric("🔵 Punteggio Sfidante", f"{sfida['punteggio_guest']} / 300")
                
                st.info(f"🏟️ ARENA: {sfida['materia']} | PIN: {sfida['pin']}")
                
                domande = sfida['domande_json']
                
                if indice < len(domande):
                    d = domande[indice]
                    st.subheader(f"Domanda {indice + 1} di 10")
                    st.markdown(f"### {d['domanda']}")
                    
                    if d.get("tipo") == "multipla":
                        scelta = st.radio("Scegli la risposta corretta:", d.get('opzioni', []), key=f"radio_{indice}")
                        if st.button("Conferma Risposta ✅", key=f"btn_m_{indice}"):
                            
                            scelta_str = str(scelta).strip().lower()
                            corretta_str = str(d.get('corretta', '')).strip().lower()
                            
                            is_esatta = (scelta_str == corretta_str) or (corretta_str in scelta_str) or (scelta_str in corretta_str)
                            punti_vinti = 30 if is_esatta else 0
                            
                            if punti_vinti == 30: st.success("🎯 Esatto! +30 punti")
                            else: st.error(f"❌ Sbagliato! La corretta era: {d.get('corretta')}")
                                
                            nuovo_totale = sfida[colonna_punteggio] + punti_vinti
                            risposte_date.append(punti_vinti) 
                            
                            supabase.table("sfide_multiplayer").update({
                                colonna_punteggio: nuovo_totale,
                                colonna_risposte: risposte_date 
                            }).eq("id", sfida['id']).execute()
                            
                            time.sleep(2)
                            st.rerun()

                    else:
                        risposta = st.text_area("Scrivi la tua risposta:", key=f"text_{indice}")
                        if st.button("Consegna al Prof 📝", key=f"btn_a_{indice}"):
                            with st.spinner("Il professore sta correggendo..."):
                                prompt_voto = [f"""Valuta questa risposta: '{risposta}'. 
Domanda: '{d['domanda']}'. 
Appunti: {sfida['appunti_testo'][:2000]}.
REGOLE: Scrivi un commento sarcastico alla Dr. House. Ricorda di impersonare un professore di Farmacia Poi vai a capo e scrivi esattamente "VOTO: X" (dove X è un numero da 1 a 30)."""]
                                try:
                                    risposta_prof = genera_testo_gemini(prompt_voto).strip()
                                    
                                    if "VOTO:" in risposta_prof:
                                        parti = risposta_prof.split("VOTO:")
                                        commento_prof = parti[0].strip()
                                        voto_str = parti[1].strip()
                                    else:
                                        commento_prof = risposta_prof
                                        voto_str = risposta_prof 
                                        
                                    numeri_estratti = ''.join(filter(str.isdigit, voto_str))
                                    voto = int(numeri_estratti) if numeri_estratti else 1 
                                    if voto > 30: voto = 30
                                except: 
                                    commento_prof = "Il tuo livello di ignoranza ha fatto crashare il mio cervello."
                                    voto = 1
                                
                                st.markdown(f"**🧑‍🏫 Il Prof dice:**\n> *{commento_prof}*")
                                
                                messaggio_voto = f"🎓 Voto finale: {voto}/30"
                                if voto < 12: st.error(messaggio_voto)
                                elif 12 <= voto <= 17: st.warning(messaggio_voto)
                                else: st.success(messaggio_voto)

                                nuovo_totale = sfida[colonna_punteggio] + voto
                                risposte_date.append(voto)
                                
                                supabase.table("sfide_multiplayer").update({
                                    colonna_punteggio: nuovo_totale,
                                    colonna_risposte: risposte_date
                                }).eq("id", sfida['id']).execute()
                                
                                time.sleep(4)
                                st.rerun()
                else:
                    st.balloons()
                    st.success("🏁 Sfida terminata! Controlla il punteggio in alto per vedere chi ha vinto!")
                    if st.button("Esci dall'Arena"):
                        del st.session_state.id_sfida_attiva
                        st.rerun()

# ==========================================
# FASE 5: PROFILO RANKED
# ==========================================
with tab5:
    st.subheader("🏆 Il Tuo Profilo Ranked")
    st.write("Spremi appunti e vinci sfide nell'Arena per scalare le classifiche dell'Ateneo!")
    
    with st.spinner("Calcolo delle statistiche in corso..."):
        try:
            res_appunti = supabase.table("appunti_salvati").select("*").eq("user_id", st.session_state.utente_loggato.id).execute()
            appunti_creati = len(res_appunti.data)
            
            res_host = supabase.table("sfide_multiplayer").select("punteggio_host, punteggio_guest").eq("host_id", st.session_state.utente_loggato.id).execute()
            res_guest = supabase.table("sfide_multiplayer").select("punteggio_host, punteggio_guest").eq("guest_id", st.session_state.utente_loggato.id).execute()
            
            punti_da_host = sum([x.get('punteggio_host', 0) for x in res_host.data])
            punti_da_guest = sum([x.get('punteggio_guest', 0) for x in res_guest.data])
            sfide_giocate = len(res_host.data) + len(res_guest.data)
            punti_totali = punti_da_host + punti_da_guest
            
            vittorie = 0
            for sfida in res_host.data:
                if sfida.get('punteggio_host', 0) > sfida.get('punteggio_guest', 0): vittorie += 1
            for sfida in res_guest.data:
                if sfida.get('punteggio_guest', 0) > sfida.get('punteggio_host', 0): vittorie += 1
            
            gradi_arena = [
                (100, "Novizio Speziale", "🌱"), (300, "Apprendista Alchimista", "🧪"),
                (600, "Assistente di Laboratorio", "⚗️"), (1000, "Studente di Farmacia", "📚"),
                (1500, "Dottore Magistrale", "🎓"), (2200, "Farmacista Clinico", "⚕️"),
                (3000, "Ricercatore Universitario", "🔬"), (4000, "Tossicologo Esperto", "☠️"),
                (5500, "Chimico Farmaceutico", "💊"), (7500, "Direttore di Laboratorio", "🏛️")
            ]
            rank_arena, icona_arena, prox_arena = "Scienziato Supremo", "🧬", punti_totali
            for limite, nome, icona in gradi_arena:
                if punti_totali < limite:
                    rank_arena, icona_arena, prox_arena = nome, icona, limite
                    break
            
            gradi_riassunti = [
                (3, "Matricola Smarrita", "🎒"), (10, "Evidenziatore Seriale", "🖍️"),
                (20, "Divoratore di Dispense", "📄"), (35, "Macchina da Riassunti", "⚙️"),
                (50, "Topo da Biblioteca", "🐁"), (75, "Archiviologo Supremo", "🗄️"),
                (100, "Discepolo di Galeno", "📜"), (150, "Mente Fotografica", "📸"),
                (200, "Saggio dell'Ateneo", "🦉"), (300, "Oracolo della Sapienza", "🔮")
            ]
            rank_riassunti, icona_riassunti, prox_riassunti = "Divinità Accademica", "👑", appunti_creati
            for limite, nome, icona in gradi_riassunti:
                if appunti_creati < limite:
                    rank_riassunti, icona_riassunti, prox_riassunti = nome, icona, limite
                    break

            st.divider()
            
            col_rank1, col_rank2 = st.columns(2)
            
            with col_rank1:
                st.markdown(f"### {icona_arena} Grado Arena: **{rank_arena}**")
                if rank_arena != "Scienziato Supremo":
                    st.progress(min(punti_totali / prox_arena, 1.0))
                    st.caption(f"Punti: {punti_totali}/{prox_arena} - Te ne mancano {prox_arena - punti_totali} per il prossimo grado!")
                else:
                    st.progress(1.0)
                    st.caption(f"Punti: {punti_totali} - Livello Massimo Raggiunto!")
                    
            with col_rank2:
                st.markdown(f"### {icona_riassunti} Grado Studio: **{rank_riassunti}**")
                if rank_riassunti != "Divinità Accademica":
                    st.progress(min(appunti_creati / prox_riassunti, 1.0))
                    st.caption(f"Riassunti: {appunti_creati}/{prox_riassunti} - Te ne mancano {prox_riassunti - appunti_creati} per il prossimo grado!")
                else:
                    st.progress(1.0)
                    st.caption(f"Riassunti: {appunti_creati} - Livello Massimo Raggiunto!")

            st.divider()
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(label="Punti Arena Totali", value=punti_totali, delta="Competitivo")
            c2.metric(label="Riassunti Generati", value=appunti_creati, delta="Secchione")
            c3.metric(label="Sfide Giocate", value=sfide_giocate)
            
            winrate = int((vittorie / sfide_giocate) * 100) if sfide_giocate > 0 else 0
            c4.metric(label="Sfide Vinte 🏆", value=vittorie, delta=f"{winrate}% Win Rate")

        except Exception as e:
            st.error(f"Errore nel caricamento del profilo: {e}")

# ==========================================
# FASE 6: COMMUNITY
# ==========================================
with tab6:
    st.subheader("🌍 Community IoImparo - Portale Scambio Appunti")
    st.write("Pubblica i tuoi riassunti migliori e cerca tra quelli degli altri studenti!")
    
    col_pubblica, col_esplora = st.columns([1, 2])
    
    with col_pubblica:
        st.markdown("### 📤 Pubblica i tuoi Appunti")
        st.info("Scegli un appunto dal tuo archivio privato e rendilo pubblico per aiutare la community!")
        
        miei_appunti = supabase.table("appunti_salvati").select("id, created_at, testo_estratto, titolo").eq("user_id", st.session_state.utente_loggato.id).eq("is_public", False).execute()
        
        if miei_appunti.data:
            scelta_pubblica = st.selectbox("Scegli appunto da pubblicare:", miei_appunti.data, format_func=lambda x: f"{x['titolo']} ({x['created_at'][:10]})")
            titolo_input = st.text_input("Modifica il Titolo (opzionale):", value=scelta_pubblica['titolo'])
            materia_input = st.text_input("Inserisci la Materia:")
            
            if st.button("Rendi Pubblico 🌍", type="primary") and materia_input:
                supabase.table("appunti_salvati").update({
                    "is_public": True,
                    "titolo": titolo_input,
                    "materia": materia_input
                }).eq("id", scelta_pubblica['id']).execute()
                st.success("Appunti pubblicati! Ora tutti possono vederli.")
                time.sleep(1)
                st.rerun()
        else:
            st.warning("Non hai appunti privati da pubblicare. Creane uno nella Fase 1!")

    with col_esplora:
        st.markdown("### 🔍 Esplora l'Archivio Pubblico")
        ricerca = st.text_input("Cerca per titolo o materia...", placeholder="Es. Anatomia, Chimica...")
        
        query_community = supabase.table("appunti_salvati").select("*").eq("is_public", True)
        if ricerca:
            query_community = query_community.ilike("titolo", f"%{ricerca}%")
            
        appunti_pubblici = query_community.order("titolo").execute()
        
        if appunti_pubblici.data:
            st.write(f"Trovati {len(appunti_pubblici.data)} appunti pubblici:")
            for ap in appunti_pubblici.data:
                with st.expander(f"📖 {ap['titolo']} | 🧬 {ap['materia']}"):
                    st.caption("Anteprima del testo:")
                    
                    testo_salvato = ap['testo_estratto']
                    try:
                        t_trasc = testo_salvato.split("[TRASCRIZIONE]")[1].split("[/TRASCRIZIONE]")[0].strip()
                        t_schem = testo_salvato.split("[SCHEMA]")[1].split("[/SCHEMA]")[0].strip()
                        t_riass = testo_salvato.split("[RIASSUNTO]")[1].split("[/RIASSUNTO]")[0].strip()
                    except:
                        t_trasc, t_schem, t_riass = "", "", testo_salvato
                        
                    anteprima = t_riass[:500] if t_riass else t_trasc[:500]
                    st.write(anteprima + "... [Continua nel PDF]")
                    
                    st.divider()
                    
                    if ap.get('file_pdf_base64'):
                        import base64
                        st.download_button(
                            label="📩 Scarica File Originale (PDF)", 
                            data=base64.b64decode(ap['file_pdf_base64']), 
                            file_name=f"{ap['titolo'].replace(' ', '_')}_Originale.pdf", 
                            mime="application/pdf", 
                            key=f"dl_comm_{ap['id']}",
                            use_container_width=True
                        )
                    else:
                        pdf_bytes = genera_pdf_scaricabile(t_trasc, t_schem, t_riass)
                        st.download_button(
                            label="📩 Scarica Appunti Elaborati (PDF)", 
                            data=pdf_bytes, 
                            file_name=f"{ap['titolo'].replace(' ', '_')}.pdf", 
                            mime="application/pdf", 
                            key=f"dl_comm_{ap['id']}",
                            use_container_width=True
                        )
        else:
            st.info("Nessun risultato trovato. Sii il primo a pubblicare!")

# ==========================================
# FASE 7: ARCHIVIO PRIVATO
# ==========================================
with tab7:
    st.subheader("🗂️ Il tuo Archivio Privato")
    st.write("Qui trovi i tuoi ultimi 25 appunti privati. Caricando il 26°, il più vecchio verrà eliminato automaticamente.")
    
    miei_archiviati = db_get_miei_appunti(st.session_state.utente_loggato.id, solo_privati=True)
    
    if miei_archiviati.data:
        st.write(f"Hai **{len(miei_archiviati.data)}/25** appunti privati salvati.")
        
        for ap in miei_archiviati.data:
            data_formattata = ap['created_at'][:10]
            with st.expander(f"📄 {ap['titolo']} | 🧬 {ap['materia']} (Creato il: {data_formattata})"):
                
                testo_salvato = ap['testo_estratto']
                try:
                    t_trasc = testo_salvato.split("[TRASCRIZIONE]")[1].split("[/TRASCRIZIONE]")[0].strip()
                    t_schem = testo_salvato.split("[SCHEMA]")[1].split("[/SCHEMA]")[0].strip()
                    t_riass = testo_salvato.split("[RIASSUNTO]")[1].split("[/RIASSUNTO]")[0].strip()
                except:
                    t_trasc, t_schem, t_riass = "", "", testo_salvato
                    
                anteprima = t_riass[:500] if t_riass else t_trasc[:500]
                st.write(anteprima + "... [Continua nel PDF]")
                
                st.divider()
                
                if ap.get('file_pdf_base64'):
                    st.download_button(
                        label="📩 Scarica File Originale (PDF)", 
                        data=base64.b64decode(ap['file_pdf_base64']), 
                        file_name=f"{ap['titolo'].replace(' ', '_')}_Originale.pdf", 
                        mime="application/pdf", 
                        key=f"dl_privato_{ap['id']}"
                    )
                else:
                    pdf_bytes = genera_pdf_scaricabile(t_trasc, t_schem, t_riass)
                    st.download_button(
                        label="📩 Scarica Appunti Elaborati (PDF)", 
                        data=pdf_bytes, 
                        file_name=f"{ap['titolo'].replace(' ', '_')}.pdf", 
                        mime="application/pdf", 
                        key=f"dl_privato_{ap['id']}"
                    )
    else:
        st.info("Il tuo archivio privato è ancora vuoto. Elabora un PDF nella Fase 1 e salvalo come Privato!")
