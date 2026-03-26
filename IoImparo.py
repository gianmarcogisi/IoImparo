import base64
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
import random
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

supabase: Client = create_client(supabase_url, supabase_key)
client = genai.Client(api_key=api_key)

if "access_token" in st.session_state:
    try:
        supabase.auth.set_session(st.session_state.access_token, st.session_state.refresh_token)
    except Exception:
        pass 

# --- I NUOVI MOTORI INTELLIGENTI (100% GEMINI) ---
def genera_testo_gemini(prompt):
    max_tentativi = 3
    attesa = 2
    for tentativo in range(max_tentativi):
        try:
            time.sleep(1) # Piccolo respiro
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            return response.text
        except Exception as e:
            if tentativo < max_tentativi - 1 and ("429" in str(e) or "503" in str(e)):
                st.toast(f"Gemini sta pensando... riprovo in {attesa}s", icon="⏳")
                time.sleep(attesa)
                attesa *= 2
            else:
                raise e

def chat_professore_gemini(system_prompt, messaggi_chat):
    try:
        prompt_completo = system_prompt + "\n\n--- CRONOLOGIA CHAT ---\n"
        for msg in messaggi_chat:
            ruolo = "Professore" if msg["ruolo"] == "assistant" else "Studente"
            prompt_completo += f"{ruolo}: {msg['contenuto']}\n"
            
        prompt_completo += "Professore: "
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_completo)
        return response.text
    except Exception as e:
        raise e

def invia_email_appunti(destinatario, titolo, materia, contenuto):
    try:
        mittente = st.secrets.get("EMAIL_SENDER", "")
        password = st.secrets.get("EMAIL_PASSWORD", "")
        if not mittente or not password:
            raise Exception("Credenziali email non configurate")
            
        msg = MIMEMultipart()
        msg['From'] = mittente
        msg['To'] = destinatario
        msg['Subject'] = f"🎓 IoImparo - Appunti di {materia}: {titolo}"
        
        corpo_email = f"Ciao!\n\nEcco gli appunti di {materia} che hai richiesto dalla Community di IoImparo.\n\nTitolo: {titolo}\n\n---\n\n{contenuto}\n\n---\nBuono studio!"
        msg.attach(MIMEText(corpo_email, 'plain', 'utf-8'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(mittente, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Errore invio email: {e}")
        return False

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

# --- 5. INTERFACCIA PRINCIPALE & MENU A TENDINA ---
col_titolo, col_profilo = st.columns([4, 1])

with col_titolo:
    st.title(f"🎓 Centrale Operativa {NOME_APP}")

with col_profilo:
    st.write("") 
    with st.popover("👤 Area Riservata", use_container_width=True):
        st.image("https://img.icons8.com/fluent/100/000000/graduation-cap.png", width=50)
        st.write(f"Socio:\n`{st.session_state.utente_loggato.email}`")
        if st.button("Esci (Logout)", use_container_width=True):
            st.session_state.utente_loggato = None
            st.rerun()

st.divider()

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

# TABS COMPLETI CON NOMI PULITI
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🗺️ Fase 1: Elabora & PDF", 
    "⚡ Fase 2: Flashcard", 
    "🧑‍🏫 Fase 3: Esame",
    "🥊 Fase 4: Arena Farmacia",
    "🏆 Profilo Ranked",  
    "🌍 Community",       
    "🗂️ Archivio Privato" 
])

with tab1:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("📥 Carica Materiale")
        tipo_file = st.radio("Formato:", ["📄 PDF", "📸 Foto"], horizontal=True)
        
        is_foto = (tipo_file == "📸 Foto")
        file_input = st.file_uploader(
            "Scegli file (Max 150 foto)" if is_foto else "Scegli file (Max 1 PDF)", 
            type=['png', 'jpg', 'jpeg'] if is_foto else ['pdf'], 
            accept_multiple_files=is_foto, 
            key="file_up"
        )
        
        troppe_foto = False
        if is_foto and isinstance(file_input, list) and len(file_input) > 150:
            st.error(f"🚨 Hai inserito {len(file_input)} foto! Rimuovine {len(file_input) - 150} per continuare.")
            troppe_foto = True
            
        st.divider()
        st.subheader("💾 Opzioni di Salvataggio")
        visibilita = st.radio("Visibilità Appunti:", ["🔒 Privato (Solo per me)", "🌍 Pubblico (Condividi nella Community)"], horizontal=True)
        is_public = (visibilita == "🌍 Pubblico (Condividi nella Community)")
        
        # --- LA TUA LISTA DELLE MATERIE ---
        lista_materie = [
            "Chimica Generale ed Inorganica", "Biologia Animale", "Biologia Vegetale", "Fisica", 
            "Matematica ed Informatica", "Anatomia Umana", "Chimica Organica", "Microbiologia", 
            "Fisiologia Umana", "Analisi dei Medicinali I", "Biochimica", "Farmacologia e Farmacoterapia", 
            "Analisi dei Medicinali II", "Patologia Generale", "Chimica Farmaceutica e Tossicologica I",
            "Chimica Farmaceutica e Tossicologica II", "Tecnologia e Legislazione Farmaceutiche", 
            "Tossicologia", "Chimica degli Alimenti", "Farmacognosia", "Farmacia Clinica", 
            "Saggi e Dosaggi dei Farmaci", "Biochimica Applicata", "Fitoterapia", "Igiene"
        ]
        
        # I campi ora appaiono SEMPRE, sia per il Pubblico che per il Privato
        titolo_appunto = st.text_input("Dai un titolo chiaro (es. Enzimi):")
        materia_appunto = st.selectbox("Seleziona la Materia:", lista_materie)
        
        # Controllo che il titolo non sia vuoto per non avere un Archivio disordinato
        if not titolo_appunto:
            st.warning("⚠️ Inserisci un Titolo per poter salvare i tuoi appunti.")
            troppe_foto = True # Blocca il bottone finché non scrivi il titolo

        bottone_elabora = st.button("Spremi Appunti 🪄", type="primary", use_container_width=True, disabled=troppe_foto)

    with col2:
        st.subheader("📄 Risultato")
        
        file_valido = len(file_input) > 0 if is_foto and file_input is not None else file_input is not None
        
        if bottone_elabora:
            if not file_valido:
                st.error("⚠️ Devi prima caricare un file (PDF o Foto) nel riquadro a sinistra!")
            else:
                if is_foto:
                    dimensione_totale = sum([f.size for f in file_input])
                    if dimensione_totale > 150 * 1024 * 1024: 
                        st.error("🚨 Le foto pesano troppo in totale. Max 150 MB.")
                        st.stop()
                else:
                    if file_input.size > 15 * 1024 * 1024: 
                        st.error("🚨 PDF troppo grande. Max 15 MB.")
                        st.stop()

                if "ultimo_utilizzo" not in st.session_state: st.session_state.ultimo_utilizzo = 0
                if time.time() - st.session_state.ultimo_utilizzo < 30:
                    st.warning("⏱️ Sistema in raffreddamento. Attendi 30 secondi tra un caricamento e l'altro.")
                    st.stop()
                st.session_state.ultimo_utilizzo = time.time()

                with st.spinner("🧠 Il Prof. Gemini sta analizzando i tuoi appunti e disegnando la mappa..."):
                    try:
                        # 1. IL PROMPT CON IL LIMITE AI NODI
                        if is_foto:
                            istruzioni_trascrizione = "Trascrivi fedelmente tutto il testo dell'immagine."
                        else:
                            istruzioni_trascrizione = "Scrivi SOLO '📄 Documento PDF in memoria'. NON trascrivere nulla."

                        contenuti = [f"""Agisci come il miglior assistente universitario del mondo. 
Dividi la risposta ESATTAMENTE usando questi tag:

[TRASCRIZIONE]
{istruzioni_trascrizione}
[/TRASCRIZIONE]

[SCHEMA]
Genera ESCLUSIVAMENTE codice Mermaid.js valido (formato graph TD).
REGOLE TASSATIVE (Se sgarri il sistema va in crash):
1. LIMITA la mappa a MASSIMO 15-20 NODI in totale. Estrai solo i concetti chiave, non fare ragnatele infinite.
2. Usa SEMPRE la sintassi: A["Testo Breve"] --> B["Altro Testo Breve"]
3. Vai SEMPRE a capo dopo ogni freccia.
4. NESSUN carattere speciale, virgole, o virgolette interne ai testi dei nodi.
[/SCHEMA]

[RIASSUNTO]
Scrivi un riassunto discorsivo, chiaro, con le parole chiave in grassetto.
[/RIASSUNTO]"""]
                        
                        if is_foto:
                            for foto in file_input: contenuti.append(Image.open(foto))
                        else:
                            reader = PyPDF2.PdfReader(file_input)
                            contenuti.append("".join([page.extract_text() for page in reader.pages]))

                        response = client.models.generate_content(model='gemini-2.5-flash', contents=contenuti)
                        st.session_state.testo_pulito_studente = response.text
                        st.session_state.riassunto_pdf = genera_pdf_scaricabile(response.text)
                        
                        # --- 2. GESTIONE OUTPUT INTELLIGENTE ---
                        testo_gemini = response.text
                        
                        try:
                            trascrizione = testo_gemini.split("[TRASCRIZIONE]")[1].split("[/TRASCRIZIONE]")[0].strip()
                            codice_mermaid = testo_gemini.split("[SCHEMA]")[1].split("[/SCHEMA]")[0].strip()
                            riassunto = testo_gemini.split("[RIASSUNTO]")[1].split("[/RIASSUNTO]")[0].strip()
                        except:
                            trascrizione, codice_mermaid, riassunto = "", "", testo_gemini 

                        # Mostra Trascrizione
                        st.markdown("### 📝 Trascrizione")
                        st.write(trascrizione if trascrizione else "Documento elaborato.")

                        # --- Mostra Schema Grafico (CON MOTORE ZOOM 🚀) ---
                        st.markdown("### 🖼️ Schema Concettuale Visivo")
                        st.info("💡 **Usa la rotellina del mouse per zoomare** e trascina la mappa per navigare!")
                        
                        if codice_mermaid and "graph" in codice_mermaid:
                            codice_mermaid = codice_mermaid.replace("```mermaid", "").replace("```", "").strip()
                            
                            # NUOVO CODICE HTML CON LIBRERIA PAN-ZOOM
                            html_code = f"""
                            <div style="width: 100%; height: 600px; background: white; border-radius: 10px; border: 1px solid #ccc; position: relative;">
                                <div class="mermaid" id="graphDiv" style="width: 100%; height: 100%;">
                                {codice_mermaid}
                                </div>
                            </div>
                            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
                            <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
                            <script>
                                mermaid.initialize({{ startOnLoad: true, theme: 'base' }});
                                
                                // Aspettiamo che Mermaid disegni, poi accendiamo il motore di Zoom
                                setTimeout(function() {{
                                    var svgElement = document.querySelector('#graphDiv svg');
                                    if(svgElement) {{
                                        svgElement.style.width = '100%';
                                        svgElement.style.height = '100%';
                                        svgElement.style.maxWidth = 'none';
                                        svgPanZoom(svgElement, {{
                                            zoomEnabled: true,
                                            controlIconsEnabled: true, // Aggiunge i bottoni + e -
                                            fit: true,
                                            center: true,
                                            minZoom: 0.5,
                                            maxZoom: 10
                                        }});
                                    }}
                                }}, 1500);
                            </script>
                            """
                            st.components.v1.html(html_code, height=650) 
                        else:
                            st.warning("⚠️ L'IA non è riuscita a trovare uno schema per questo testo.")

                        # Mostra Riassunto
                        st.markdown("### 📖 Riassunto Completo")
                        st.markdown(riassunto)

                        # --- 3. IL SALVATAGGIO NEL DATABASE ---
                        try:
                            supabase.table("appunti_salvati").insert({
                                "user_id": st.session_state.utente_loggato.id,
                                "testo_estratto": st.session_state.testo_pulito_studente,
                                "is_public": is_public,
                                "titolo": titolo_appunto,
                                "materia": materia_appunto
                            }).execute()
                            
                            if is_public: st.toast("🌍 Salvato e condiviso con la Community!", icon="✅")
                            else: st.toast("🔒 Salvato nel tuo archivio privato!", icon="✅")
                            
                            MAX_APPUNTI_MEMORIA = 25 
                            res_storico = supabase.table("appunti_salvati").select("id").eq("user_id", st.session_state.utente_loggato.id).eq("is_public", False).order("created_at").execute()
                            
                            if len(res_storico.data) > MAX_APPUNTI_MEMORIA:
                                appunti_da_eliminare = len(res_storico.data) - MAX_APPUNTI_MEMORIA
                                ids_da_eliminare = [record['id'] for record in res_storico.data[:appunti_da_eliminare]]
                                for old_id in ids_da_eliminare:
                                    supabase.table("appunti_salvati").delete().eq("id", old_id).execute()
                                st.toast(f"🧹 Spazio ottimizzato!", icon="♻️")
                                    
                        except Exception as db_e: 
                            st.error(f"Errore DB: {db_e}")
                        
                        st.balloons()
                        
                    except Exception as e:
                        if "503" in str(e): st.warning("⏳ Server Google intasati. Riprova tra poco!")
                        else: st.error(f"Errore Gemini: {e}")
        
        if st.session_state.riassunto_pdf:
            st.download_button("📩 Scarica PDF", data=st.session_state.riassunto_pdf, file_name="riassunto.pdf", mime="application/pdf")
with tab2:
    if st.session_state.testo_pulito_studente:
        if st.button("Genera Flashcard 🚀"):
            with st.spinner("🧠 Sto frullando gli appunti per creare le tue Flashcard magiche... Scalda il cervello!"):
                try:
                    testo_flashcard = genera_testo_gemini(f"Crea 5 flashcard domanda/risposta da qui: {st.session_state.testo_pulito_studente}")
                    st.info(testo_flashcard)
                except Exception as e: st.error(f"Errore generazione: {e}")
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
            
            system_prompt = f"""Sei il Prof. Dr. House, docente universitario di Farmacia/Medicina. Sei geniale, cinico, incredibilmente sarcastico e non sopporti l'ignoranza. Sotto sotto vuoi che gli studenti imparino, ma li tratti con affettuoso disprezzo.
Devi interrogare lo studente basandoti ESCLUSIVAMENTE su questi appunti:
{st.session_state.testo_pulito_studente[:3000]}

REGOLE TASSATIVE (Se le violi, sei licenziato):
1. Fai UNA SOLA DOMANDA alla volta e aspetta la risposta.
2. Quando lo studente risponde:
   - Valuta la sua risposta sfoggiando tutto il tuo sarcasmo.
   - Dagli un voto in trentesimi (es. 28/30 se è bravo, 1/30 se dice fesserie).
   - Correggi i suoi errori usando SEMPRE la "Lavagna Visiva" (Usa il Markdown per disegnare una Tabella, uno schema ad albero o un elenco puntato).
3. Finita la correzione, fagli SUBITO una nuova domanda sul testo."""
            
            try:
                # --- LO SPINNER DEL PROFESSORE ---
                with st.spinner("🧑‍🏫 Il Prof sta affilando il sarcasmo... Trema!"):
                    # Chiamata a Gemini
                    risposta_prof = chat_professore_gemini(system_prompt, st.session_state.messaggi_chat)
                
                # 1. MOSTRA SUBITO LA RISPOSTA (così puoi leggerla durante la pausa)
                with st.chat_message("assistant"): 
                    st.markdown(risposta_prof)
                
                # 2. AGGIUNGIAMO LA RISPOSTA ALLO STORICO
                st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": risposta_prof})
                
                # --- 3. LA PAUSA TATTICA DI 5 SECONDI ---
                # Usiamo una caption per avvisarti
                st.caption("⏱️ *Il Prof ti concede 5 secondi per assaporare la sua saggezza (e il suo sarcasmo) prima della prossima domanda...*")
                time.sleep(5) # Aspetta 5 secondi reali
                # ----------------------------------------
                
                # 4. ORA RICARICHIAMO LA PAGINA
                st.rerun()
                
            except Exception as e: 
                st.error(f"Errore Chat: {e}")

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
                        
                        quiz_raw = genera_testo_gemini(prompt_quiz)
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
                colonna_punteggio = "punteggio_host" if is_host else "punteggio_guest"
                colonna_risposte = "risposte_host" if is_host else "risposte_guest"
                
                # --- SISTEMA AFK (VITTORIA A TAVOLINO) ---
                mio_ping_col = "last_ping_host" if is_host else "last_ping_guest"
                suo_ping_col = "last_ping_guest" if is_host else "last_ping_host"
                
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
                
                # Riconnessione - Conta quante risposte hai già dato
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
                                prompt_voto = f"""Valuta questa risposta: '{risposta}'. 
Domanda: '{d['domanda']}'. 
Appunti: {sfida['appunti_testo'][:2000]}.
REGOLE: Scrivi un commento sarcastico alla Dr. House. Poi vai a capo e scrivi esattamente "VOTO: X" (dove X è un numero da 1 a 30)."""
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

# --- FASE 6: COMMUNITY ---
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
                    st.write(ap['testo_estratto'][:300] + "... [Continua]")
                    
                    st.divider()
                    col_mail_1, col_mail_2 = st.columns([3, 1])
                    with col_mail_1:
                        email_destinatario = st.text_input("Ricevi il file completo:", placeholder="La tua email...", key=f"mail_input_{ap['id']}")
                    with col_mail_2:
                        st.write("") 
                        if st.button("Invia Email ✉️", key=f"btn_mail_{ap['id']}", use_container_width=True):
                            if email_destinatario:
                                with st.spinner("Invio in corso..."):
                                    esito = invia_email_appunti(email_destinatario, ap['titolo'], ap['materia'], ap['testo_estratto'])
                                    if esito:
                                        st.success("Inviato! Controlla la posta.")
                                    else:
                                        st.error("Errore nell'invio! Hai configurato i Secrets EMAIL_SENDER e EMAIL_PASSWORD?")
                            else:
                                st.warning("Inserisci l'email!")
        else:
            st.info("Nessun risultato trovato. Sii il primo a pubblicare!")
# --- FASE 7: ARCHIVIO PRIVATO ---
with tab7:
    st.subheader("🗂️ Il tuo Archivio Privato")
    st.write("Qui trovi i tuoi ultimi 25 appunti privati. Caricando il 26°, il più vecchio verrà eliminato automaticamente.")
    
    # Li peschiamo ordinandoli dal più NUOVO al più VECCHIO (desc=True)
    miei_archiviati = supabase.table("appunti_salvati").select("*").eq("user_id", st.session_state.utente_loggato.id).eq("is_public", False).order("created_at", desc=True).execute()
    
    if miei_archiviati.data:
        st.write(f"Hai **{len(miei_archiviati.data)}/25** appunti privati salvati.")
        
        for ap in miei_archiviati.data:
            data_formattata = ap['created_at'][:10] # Prende solo la data YYYY-MM-DD
            with st.expander(f"📄 {ap['titolo']} | 🧬 {ap['materia']} (Creato il: {data_formattata})"):
                st.write(ap['testo_estratto'][:500] + "... [Continua nel PDF]")
                
                st.divider()
                
                # Bottone per scaricare al volo il PDF
                pdf_bytes = genera_pdf_scaricabile(ap['testo_estratto'])
                st.download_button(
                    label="📩 Scarica PDF Completo", 
                    data=pdf_bytes, 
                    file_name=f"{ap['titolo'].replace(' ', '_')}.pdf", 
                    mime="application/pdf", 
                    key=f"dl_privato_{ap['id']}"
                )
    else:
        st.info("Il tuo archivio privato è ancora vuoto. Elabora un PDF nella Fase 1 e salvalo come Privato!")

