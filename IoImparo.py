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
from groq import Groq
import random
import json

# --- 1. CONFIGURAZIONE PAGINA ---
NOME_APP = "IoImparo 🎓"
st.set_page_config(page_title=NOME_APP, page_icon="🎓", layout="wide")

# --- NASCONDIAMO IL BRAND STREAMLIT ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 2. SICUREZZA E CHIAVI ---
api_key = st.secrets["GEMINI_API_KEY"]
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]
groq_api_key = st.secrets["GROQ_API_KEY"]

supabase: Client = create_client(supabase_url, supabase_key)
client = genai.Client(api_key=api_key)
groq_client = Groq(api_key=groq_api_key)

if "access_token" in st.session_state:
    try:
        supabase.auth.set_session(st.session_state.access_token, st.session_state.refresh_token)
    except Exception:
        pass 

# --- IL CENTRALINO MULTI-MODELLO ---
def genera_testo_con_fallback(prompt):
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        if "503" in str(e) or "429" in str(e):
            st.toast("Google intasato. Attivo Llama 3... 🚀", icon="🦙")
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-8b-8192",
            )
            return chat_completion.choices[0].message.content
        else:
            raise e

# --- 3. GESTIONE SESSIONE UTENTE ---
if "utente_loggato" not in st.session_state: st.session_state.utente_loggato = None
if "testo_pulito_studente" not in st.session_state: st.session_state.testo_pulito_studente = ""
if "riassunto_pdf" not in st.session_state: st.session_state.riassunto_pdf = None
if "messaggi_chat" not in st.session_state: st.session_state.messaggi_chat = []

# --- 4. LOGIN ---
if st.session_state.utente_loggato is None:
    st.title(f"🎓 {NOME_APP}")
    st.warning("👋 Benvenuto! Accedi o registrati per iniziare.")
    
    tab_login, tab_registrati = st.tabs(["🔑 Accedi", "📝 Registrati"])
    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Entra 🔑", use_container_width=True):
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

# --- 5. SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/fluent/100/000000/graduation-cap.png", width=100)
    st.title("Area Riservata")
    st.write(f"Socio: **{st.session_state.utente_loggato.email}**")
    if st.button("Esci (Logout)"):
        st.session_state.utente_loggato = None
        st.rerun()

# --- 6. PDF ---
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

# NUOVO TABS CHE INCLUDE LA FASE 5
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗺️ Fase 1: Elabora & PDF", 
    "⚡ Fase 2: Flashcard", 
    "🧑‍🏫 Fase 3: Esame",
    "🥊 Fase 4: Arena Farmacia",
    "🏆 Fase 5: Profilo Ranked"
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
(Scrivi un riassunto discorsivo, chiaro e approfondito per studiare)."""]
                    
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
                testo_flashcard = genera_testo_con_fallback(f"Crea 5 flashcard domanda/risposta da qui: {st.session_state.testo_pulito_studente}")
                st.info(testo_flashcard)
            except Exception as e: st.error(f"Errore generazione: {e}")
    else: st.warning("Carica prima qualcosa in Fase 1!")

# --- FASE 3 AGGIORNATA (LAVAGNA VISIVA) ---
with tab3:
    if st.session_state.testo_pulito_studente:
        st.markdown("Scrivi **'Iniziamo'** per far partire l'interrogazione.")
        for m in st.session_state.messaggi_chat:
            with st.chat_message(m["ruolo"]): st.markdown(m["contenuto"])
        
        inp = st.chat_input("Rispondi al prof... (Max 500 caratteri)", max_chars=500)
        if inp:
            st.chat_message("user").markdown(inp)
            st.session_state.messaggi_chat.append({"ruolo": "user", "contenuto": inp})
            
            prompt_prof = f"""Sei un professore universitario di materie scientifiche (Farmacia/Medicina) rigoroso ma moderno. 
Devi interrogare lo studente basandoti ESCLUSIVAMENTE su questi appunti: 
{st.session_state.testo_pulito_studente[:3000]}

REGOLE TASSATIVE:
1. Fai UNA SOLA domanda alla volta. Sii estremamente sintetico.
2. Se lo studente dà una risposta sbagliata o incompleta, PRIMA valuta da 1 a 30, POI correggilo usando la "Lavagna Visiva".
3. LAVAGNA VISIVA: Quando correggi concetti complessi (es. molecole, vie anatomiche, tabelle di classificazione farmaci), USA OBBLIGATORIAMENTE il linguaggio Markdown per creare Tabelle riassuntive, oppure usa schemi visivi (ASCII art o elenchi puntati nidificati) per fargli stampare il concetto in testa visivamente.
4. Dopo la spiegazione visiva, fai subito la domanda successiva.

Storico Chat: {st.session_state.messaggi_chat}"""
            
            try:
                risposta_prof = genera_testo_con_fallback(prompt_prof)
                with st.chat_message("assistant"): st.markdown(risposta_prof)
                st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": risposta_prof})
            except Exception as e: st.error(f"Errore Chat: {e}")
    else: st.warning("Carica prima qualcosa in Fase 1!")

with tab4:
    st.subheader("🧪 Arena di Farmacia")

    if "id_sfida_attiva" not in st.session_state:
        scelta_arena = st.radio("Cosa vuoi fare?", ["Crea Sfida 🏗️", "Unisciti a Sfida ⚔️"], horizontal=True)

        if scelta_arena == "Crea Sfida 🏗️":
            materia = st.selectbox("Seleziona l'esame:", [
                "Chimica Generale ed Inorganica", "Biologia Animale", "Biologia Vegetale", "Fisica", 
                "Matematica ed Informatica", "Anatomia Umana", "Chimica Organica", "Microbiologia", 
                "Fisiologia Umana", "Analisi dei Medicinali I", "Biochimica", "Farmacologia e Farmacoterapia", 
                "Analisi dei Medicinali II", "Patologia Generale", "Chimica Farmaceutica e Tossicologica I",
                "Chimica Farmaceutica e Tossicologica II", "Tecnologia e Legislazione Farmaceutiche", 
                "Tossicologia", "Chimica degli Alimenti", "Farmacognosia", "Farmacia Clinica", 
                "Saggi e Dosaggi dei Farmaci", "Biochimica Applicata", "Fitoterapia", "Igiene"
            ])
            file_sfida = st.file_uploader("Carica materiale", type=['pdf', 'jpg', 'png'], key="file_arena")
            
            if st.button("Genera Arena 🏟️") and file_sfida:
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
Devono essere 10 elementi in totale (5 multipla, 5 aperta).
Testo: {str(testo_arena)[:3000]}"""
                        
                        quiz_raw = genera_testo_con_fallback(prompt_quiz)
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
                    except Exception as e: st.error(f"Errore creazione arena: {e}")

        else: # Unisciti a Sfida
            pin_inserito = st.text_input("Inserisci il PIN di 4 cifre:")
            if st.button("Entra nel Ring 🥊"):
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
        # LOGICA DI COMBATTIMENTO
        res_live = supabase.table("sfide_multiplayer").select("*").eq("id", st.session_state.id_sfida_attiva).execute()
        
        if res_live.data:
            sfida = res_live.data[0]
            
            if sfida['stato'] == 'waiting':
                st.warning(f"⏳ PIN: {sfida['pin']} | In attesa dello sfidante...")
                if st.button("Aggiorna Stato 🔄"): st.rerun()
                if st.button("Annulla Sfida"): 
                    del st.session_state.id_sfida_attiva
                    st.rerun()
            
            elif sfida['stato'] == 'playing':
                st.divider()
                
                is_host = (st.session_state.utente_loggato.id == sfida['host_id'])
                colonna_punteggio = "punteggio_host" if is_host else "punteggio_guest"
                
                col1, col2 = st.columns(2)
                col1.metric("🔴 Punteggio Host", f"{sfida['punteggio_host']} / 300")
                col2.metric("🔵 Punteggio Sfidante", f"{sfida['punteggio_guest']} / 300")
                
                st.info(f"🏟️ ARENA: {sfida['materia']} | PIN: {sfida['pin']}")
                
                domande = sfida['domande_json']
                if "indice_domanda" not in st.session_state: st.session_state.indice_domanda = 0
                indice = st.session_state.indice_domanda
                
                if indice < len(domande):
                    d = domande[indice]
                    st.subheader(f"Domanda {indice + 1} di 10")
                    st.markdown(f"### {d['domanda']}")
                    
                    # Domande Multiple
                    if d.get("tipo") == "multipla":
                        scelta = st.radio("Scegli la risposta corretta:", d.get('opzioni', []), key=f"radio_{indice}")
                        if st.button("Conferma Risposta ✅", key=f"btn_m_{indice}"):
                            punti_vinti = 30 if scelta == d.get('corretta') else 0
                            if punti_vinti == 30: st.success("🎯 Esatto! +30 punti")
                            else: st.error(f"❌ Sbagliato! La corretta era: {d.get('corretta')}")
                            
                            nuovo_totale = sfida[colonna_punteggio] + punti_vinti
                            supabase.table("sfide_multiplayer").update({colonna_punteggio: nuovo_totale}).eq("id", sfida['id']).execute()
                            time.sleep(2)
                            st.session_state.indice_domanda += 1
                            st.rerun()

                    # Domande Aperte
                    else:
                        risposta = st.text_area("Scrivi la tua risposta:", key=f"text_{indice}")
                        if st.button("Consegna al Prof 📝", key=f"btn_a_{indice}"):
                            with st.spinner("Il professore sta correggendo..."):
                                prompt_voto = f"""Valuta questa risposta dello studente: '{risposta}'.
Domanda: '{d['domanda']}'.
Basati su questo testo: {sfida['appunti_testo'][:2000]}.
Dai SOLO un voto da 1 a 30 (scrivi solo il numero, niente altro testo)."""
                                try:
                                    voto_str = genera_testo_con_fallback(prompt_voto).strip()
                                    voto = int(''.join(filter(str.isdigit, voto_str))) 
                                    if voto > 30: voto = 30
                                except: voto = 15
                                    
                                st.success(f"🎓 Voto del professore: {voto}/30!")
                                nuovo_totale = sfida[colonna_punteggio] + voto
                                supabase.table("sfide_multiplayer").update({colonna_punteggio: nuovo_totale}).eq("id", sfida['id']).execute()
                                time.sleep(2)
                                st.session_state.indice_domanda += 1
                                st.rerun()
                else:
                    st.balloons()
                    st.success("🏁 Sfida terminata! Controlla il punteggio in alto per vedere chi ha vinto!")
                    if st.button("Esci dall'Arena"):
                        del st.session_state.id_sfida_attiva
                        st.rerun()

# --- NUOVA FASE 5 (TRACKER RANKED) ---
with tab5:
    st.subheader("🏆 Il Tuo Profilo Ranked")
    st.write("Spremi appunti e vinci sfide nell'Arena per salire di livello!")
    
    with st.spinner("Calcolo delle statistiche in corso..."):
        try:
            res_appunti = supabase.table("appunti_salvati").select("*").eq("user_id", st.session_state.utente_loggato.id).execute()
            appunti_creati = len(res_appunti.data)
            
            res_host = supabase.table("sfide_multiplayer").select("punteggio_host").eq("host_id", st.session_state.utente_loggato.id).execute()
            res_guest = supabase.table("sfide_multiplayer").select("punteggio_guest").eq("guest_id", st.session_state.utente_loggato.id).execute()
            
            punti_da_host = sum([x.get('punteggio_host', 0) for x in res_host.data])
            punti_da_guest = sum([x.get('punteggio_guest', 0) for x in res_guest.data])
            sfide_giocate = len(res_host.data) + len(res_guest.data)
            
            punti_totali = punti_da_host + punti_da_guest
            
            if punti_totali < 100: rank, icona, prox = "Novizio Speziale", "🌱", 100
            elif punti_totali < 500: rank, icona, prox = "Apprendista Alchimista", "🧪", 500
            elif punti_totali < 1500: rank, icona, prox = "Dottore in Farmacia", "👨‍⚕️", 1500
            elif punti_totali < 3000: rank, icona, prox = "Ricercatore Senior", "🔬", 3000
            else: rank, icona, prox = "Scienziato Supremo", "🧬", punti_totali
            
            st.markdown(f"### Grado Attuale: {icona} **{rank}**")
            
            if rank != "Scienziato Supremo":
                progresso = punti_totali / prox
                st.progress(min(progresso, 1.0))
                st.caption(f"Ti mancano {prox - punti_totali} punti per il prossimo livello!")
            else:
                st.progress(1.0)
                st.caption("Hai raggiunto il livello massimo! Sei una leggenda.")
            
            st.divider()
            
            c1, c2, c3 = st.columns(3)
            c1.metric(label="Punti Arena Totali", value=punti_totali, delta="Competitivo")
            c2.metric(label="Riassunti Generati", value=appunti_creati, delta="Secchione")
            c3.metric(label="Sfide Giocate", value=sfide_giocate)

        except Exception as e:
            st.error(f"Errore nel caricamento del profilo: {e}")
