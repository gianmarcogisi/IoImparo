import base64
import streamlit as st
import os
from google import genai
from PIL import Image
import PyPDF2
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
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
def genera_pdf_scaricabile(trascrizione, schema, riassunto):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    
    style_title = styles['Heading1']
    style_sub = styles['Heading2']
    style_normal = styles['Normal']
    
    story = []
    
    story.append(Paragraph("Appunti Completi - IoImparo 🎓", style_title))
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("📝 1. Trascrizione", style_sub))
    story.append(Paragraph(trascrizione.replace('\n', '<br/>'), style_normal))
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("🖼️ 2. Schema Concettuale", style_sub))
    # Invece del codice brutto, mettiamo un avviso elegante per il PDF
    story.append(Paragraph("<i>[Nota: Lo schema visivo e navigabile è consultabile interattivamente all'interno della Centrale Operativa Web]</i>", style_normal))
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("📖 3. Riassunto Completo", style_sub))
    testo_riassunto = riassunto.replace('**', '') 
    story.append(Paragraph(testo_riassunto.replace('\n', '<br/>'), style_normal))
    
    doc.build(story)
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
                    st.warning("⏱️ Sistema in raffreddamento. Attendi 30 secondi.")
                    st.stop()
                st.session_state.ultimo_utilizzo = time.time()

                # --- QUI INIZIA L'ELABORAZIONE (TUTTO RIENTRATO A DESTRA) ---
                with st.spinner("🧠 Il Prof. Gemini sta analizzando i tuoi appunti..."):
                    try:
                        # 1. LOGICA DI TRASCRIZIONE
                        if is_foto:
                            istruzioni_trascrizione = "Trascrivi fedelmente tutto il testo dell'immagine."
                        else:
                            istruzioni_trascrizione = "Scrivi SOLO '📄 Documento PDF in memoria'. NON trascrivere nulla."

                        # 2. IL TUO PROMPT COMPLETO
                        contenuti = [f"""Agisci come il miglior assistente universitario del mondo. 
Dividi la risposta ESATTAMENTE usando questi tag:

[TRASCRIZIONE]
{istruzioni_trascrizione}
[/TRASCRIZIONE]

[SCHEMA]
Genera ESCLUSIVAMENTE codice Mermaid.js valido (formato graph TD).
REGOLE TASSATIVE ANTI-CRASH (SE SBAGLI IL GRAFICO SARÀ BIANCO):
1. Sviluppa in VERTICALE. Max 2 frecce per nodo padre.
2. Usa questa sintassi esatta: A["Titolo: breve spiegazione"] --> B["Titolo: breve spiegazione"]
3. VIETATO ANDARE A CAPO all'interno delle parentesi quadre ["..."]. Il testo della descrizione deve stare tutto su una singola riga!
4. VIETATO usare altre virgolette doppie ("), apici (') o parentesi tonde dentro le descrizioni. Usa solo testo semplice.
5. Vai a capo SOLO dopo aver completato l'intero collegamento della freccia.
6. Impersoni un professore di Farmacia Severo ma simpatico.
[/SCHEMA]

[RIASSUNTO]
Scrivi un riassunto discorsivo, chiaro, con le parole chiave in grassetto.
[/RIASSUNTO]"""]
                        
                        if is_foto:
                            for foto in file_input: contenuti.append(Image.open(foto))
                        else:
                            reader = PyPDF2.PdfReader(file_input)
                            contenuti.append("".join([page.extract_text() for page in reader.pages]))

                        # CHIAMATA A GEMINI
                        response = client.models.generate_content(model='gemini-2.5-flash', contents=contenuti)
                        st.session_state.testo_pulito_studente = response.text
                        
                        # 3. GESTIONE OUTPUT
                        testo_gemini = response.text
                        try:
                            trascrizione = testo_gemini.split("[TRASCRIZIONE]")[1].split("[/TRASCRIZIONE]")[0].strip()
                            codice_mermaid = testo_gemini.split("[SCHEMA]")[1].split("[/SCHEMA]")[0].strip()
                            riassunto = testo_gemini.split("[RIASSUNTO]")[1].split("[/RIASSUNTO]")[0].strip()
                        except:
                            trascrizione, codice_mermaid, riassunto = "", "", testo_gemini 

                        # PULIZIA ACCENTI PER MERMAID
                        mappa_pulizia = str.maketrans("àèéìòùÀÈÉÌÒÙ", "aeeiouAEEIOU")
                        codice_mermaid = codice_mermaid.translate(mappa_pulizia).replace("```mermaid", "").replace("```", "").strip()

                        # GENERAZIONE PDF CON LE 3 PARTI
                        st.session_state.riassunto_pdf = genera_pdf_scaricabile(trascrizione, codice_mermaid, riassunto)

                        # --- MOSTRA RISULTATI ---
                        st.markdown("### 📝 Trascrizione")
                        st.write(trascrizione if trascrizione else "Documento elaborato.")

                        st.markdown("### 🖼️ Schema Concettuale Visivo")
                        if codice_mermaid and "graph" in codice_mermaid:
                            html_code = f"""
                            <div id="wrapper" style="width: 100%; background: white; border-radius: 10px; border: 1px solid #ccc; position: relative;">
                                <button onclick="downloadSVG()" style="position: absolute; top: 10px; left: 10px; z-index: 100; padding: 8px 12px; background: #4F46E5; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">
                                    💾 Scarica per Stampa (PNG)
                                </button>
                                <div id="graphDiv" style="width: 100%; height: 600px;">{codice_mermaid}</div>
                            </div>
                            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
                            <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
                            <script>
                                mermaid.initialize({{ startOnLoad: true, theme: 'base' }});
                                setTimeout(function() {{
                                    var svgElement = document.querySelector('#graphDiv svg');
                                    if(svgElement) {{
                                        svgElement.style.width = '100%'; svgElement.style.height = '100%'; svgElement.style.maxWidth = 'none';
                                        window.panZoom = svgPanZoom(svgElement, {{ zoomEnabled: true, controlIconsEnabled: true, fit: true, center: true }});
                                    }}
                                }}, 1500);
                                function downloadSVG() {{
                                    var svg = document.querySelector('#graphDiv svg');
                                    var canvas = document.createElement('canvas');
                                    var bbox = svg.getBBox();
                                    canvas.width = bbox.width * 2; canvas.height = bbox.height * 2;
                                    var context = canvas.getContext('2d');
                                    var img = new Image();
                                    var xml = new XMLSerializer().serializeToString(svg);
                                    var svgBlob = new Blob([xml], {{type: 'image/svg+xml;charset=utf-8'}});
                                    var url = URL.createObjectURL(svgBlob);
                                    img.onload = function() {{
                                        context.fillStyle = "white"; context.fillRect(0, 0, canvas.width, canvas.height);
                                        context.drawImage(img, 0, 0, canvas.width, canvas.height);
                                        var a = document.createElement("a");
                                        a.href = canvas.toDataURL("image/png"); a.download = "Schema_IoImparo.png"; a.click();
                                    }};
                                    img.src = url;
                                }}
                            </script>"""
                            st.components.v1.html(html_code, height=650)
                        
                        st.markdown("### 📖 Riassunto Completo")
                        st.markdown(riassunto)

                        # SALVATAGGIO NEL DATABASE
                        try:
                            supabase.table("appunti_salvati").insert({
                                "user_id": st.session_state.utente_loggato.id,
                                "testo_estratto": st.session_state.testo_pulito_studente,
                                "is_public": is_public, "titolo": titolo_appunto, "materia": materia_appunto
                            }).execute()
                            st.toast("✅ Appunti salvati!", icon="💾")
                        except: pass
                        
                        st.balloons()

                    except Exception as e:
                        if "503" in str(e): st.warning("⏳ Server Google intasati. Riprova tra poco!")
                        else: st.error(f"Errore Gemini: {e}")

        # --- TASTO DOWNLOAD (FUORI DALLE LOGICHE DI ERRORE) ---
        if st.session_state.riassunto_pdf:
            st.write("---")
            st.download_button(
                label="📩 Scarica PDF Completo", 
                data=st.session_state.riassunto_pdf, 
                file_name="riassunto_ioimparo.pdf", 
                mime="application/pdf",
                use_container_width=True
            )

with tab2:
    st.subheader("⚡ Flashcard Visive & Dinamiche")
    
    if "flashcards" not in st.session_state: st.session_state.flashcards = []
    if "indice_flashcard" not in st.session_state: st.session_state.indice_flashcard = 0
    
    opzioni_appunti = {}
    if st.session_state.testo_pulito_studente:
        opzioni_appunti["✨ Appunti Fase 1"] = st.session_state.testo_pulito_studente
    try:
        miei_appunti = supabase.table("appunti_salvati").select("id, titolo, materia, testo_estratto").eq("user_id", st.session_state.utente_loggato.id).order("created_at", desc=True).execute()
        for ap in miei_appunti.data:
            opzioni_appunti[f"📁 {ap['titolo']} | {ap['materia']}"] = ap['testo_estratto']
    except: pass
        
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
                    
                    prompt_flash = "Agisci come professore. Crea " + str(num_cards) + """ flashcard in formato JSON ESATTO. 
Nessun blocco markdown, nessuna chiacchiera, solo l'array puro.
Struttura: [{"domanda": "...", "tipo_visuale": "molecola", "query_visuale": "paracetamol", "risposta": "..."}]
Tipi visuali permessi: "molecola", "immagine", "nessuno".
Testo da usare: """ + testo_f2

                    try:
                        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_flash)
                        testo = res.text
                        
                        inizio = testo.find('[')
                        fine = testo.rfind(']') + 1
                        
                        if inizio == -1 or fine <= 0:
                            st.error("L'IA non ha generato un array JSON.")
                            st.code(testo) # Stampiamo la risposta grezza!
                        else:
                            st.session_state.flashcards = json.loads(testo[inizio:fine])
                            st.session_state.indice_flashcard = 0
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Errore tecnico IA: {str(e)}")
                        try:
                            st.warning("Risposta grezza ricevuta:")
                            st.write(res.text)
                        except:
                            st.warning("Nessun testo ricevuto (Probabile blocco dei filtri di sicurezza sui farmaci!).")

        if st.session_state.flashcards:
            idx = st.session_state.indice_flashcard
            carta = st.session_state.flashcards[idx]
            
            with st.container(border=True):
                st.write(f"### Carta {idx+1} di {len(st.session_state.flashcards)}")
                st.markdown(f"#### ❓ {carta.get('domanda')}")
                
                t_v = carta.get('tipo_visuale')
                q_v = str(carta.get('query_visuale', '')).replace(" ", "_")
                
                if t_v == 'molecola' and q_v:
                    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{q_v}/PNG"
                    st.image(url, width=300, caption="Struttura chimica (Riconoscila!)")
                elif t_v == 'immagine' and q_v:
                    # Query pulita per evitare il simbolo rotto (🖼️0)
                    url = f"https://image.pollinations.ai/prompt/{q_v}_scientific_illustration_clean_background?width=512&height=512&nologo=true"
                    st.image(url, width=400, caption="Rappresentazione concettuale")

                with st.expander("Gira la Carta 🔄"):
                    st.success(f"**Risposta:** {carta.get('risposta')}")

            c1, c2, c3 = st.columns(3)
            if c1.button("⬅️", disabled=idx==0): 
                st.session_state.indice_flashcard -= 1
                st.rerun()
            if c3.button("➡️", disabled=idx==len(st.session_state.flashcards)-1):
                st.session_state.indice_flashcard += 1
                st.rerun()

with tab3:
    st.subheader("🧑‍🏫 Simulazione Esame Orale")
    
    # --- VARIABILI PER LA CATTIVERIA DEL PROF ---
    if "errori_totali" not in st.session_state: st.session_state.errori_totali = 0
    if "esame_bocciato" not in st.session_state: st.session_state.esame_bocciato = False

    opzioni_esame = {}
    if st.session_state.testo_pulito_studente:
        opzioni_esame["✨ Appunti Fase 1"] = st.session_state.testo_pulito_studente
    try:
        miei_db = supabase.table("appunti_salvati").select("id, titolo, materia, testo_estratto").eq("user_id", st.session_state.utente_loggato.id).execute()
        for ap in miei_db.data: opzioni_esame[f"📁 {ap['titolo']}"] = ap['testo_estratto']
    except: pass

    if opzioni_esame:
        scelta_e = st.selectbox("Argomento esame:", list(opzioni_esame.keys()), key="sel_e")
        
        # RESET AZZERA ANCHE I CONTATORI DI BOCCIATURA
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

        # SE NON SEI ANCORA STATO CACCIATO DALL'AULA...
        if not st.session_state.esame_bocciato:
            if p_studente := st.chat_input("Rispondi... (Il libretto non dimentica)"):
                st.session_state.messaggi_chat.append({"ruolo": "user", "contenuto": p_studente})
                
                with st.chat_message("assistant"):
                    with st.spinner("Il Prof. annota le tue mancanze..."):
                        
                        # PROMPT SPIETATO E MEMORIA DI FERRO
                        sys_p = f"""Sei un Prof. di Farmacia universitario spietato (stile Dr. House). Testo: {opzioni_esame[scelta_e]}
                        
                        REGOLE TASSATIVE:
                        1. Se lo studente scrive solo "Iniziamo", ti saluta o fa convenevoli: NON DARE NESSUN VOTO. Fai direttamente la prima domanda per avviare l'esame.
                        2. Se invece lo studente sta rispondendo a una tua domanda: valuta la risposta. Se corretta, sii ironico. Se errata, sii cinico e cattivo.
                        3. SOLO quando valuti una risposta vera, scrivi su una riga nuova: "VOTO: X" (numero da 1 a 30).
                        4. Dopo il voto, fai una NUOVA domanda specifica, colpendolo sui dettagli.
                        5. NON SEMPLIFICARE MAI LE DOMANDE. Nessuna pietà."""
                        
                        r_prof = chat_professore_gemini(sys_p, st.session_state.messaggi_chat)    
                        
                        # LOGICA VOTI E BOCCIATURA AD ACCUMULO
                        voto = 0
                        try:
                            voto = int(''.join(filter(str.isdigit, r_prof.split("VOTO:")[1][:3])))
                        except: pass
                        
                        if voto > 0:
                            # SE SBAGLI, L'ERRORE SI ACCUMULA. SE INDOVINI, NON SI AZZERA!
                            if voto < 18:
                                st.session_state.errori_totali += 1
                            
                            # CONTROLLO BOCCIATURA (LIMITE: 4 ERRORI TOTALI)
                            if st.session_state.errori_totali >= 4:
                                st.session_state.esame_bocciato = True
                                msg_bocciato = f"🔴 VOTO: {voto}/30. Quarto errore totale. La sua preparazione fa acqua da tutte le parti. Prenda il suo libretto, è **BOCCIATO**. E chiuda la porta uscendo!"
                                st.error(msg_bocciato)
                                st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": msg_bocciato})
                                time.sleep(4)
                                st.rerun()
                            
                            else:
                                # CONTINUA L'ESAME NORMALE
                                commento = r_prof.split("VOTO:")[0]
                                nuova_d = r_prof.split(str(voto))[1] if str(voto) in r_prof else ""

                                st.markdown(commento)
                                if 1 <= voto <= 11: 
                                    st.error(f"🔴 VOTO: {voto}/30 - Disastroso. (Errori accumulati: {st.session_state.errori_totali}/4)")
                                elif 12 <= voto <= 17: 
                                    st.warning(f"🟡 VOTO: {voto}/30 - Mediocre. (Errori accumulati: {st.session_state.errori_totali}/4)")
                                elif voto >= 18: 
                                    # Ti fa i complimenti, ma ti ricorda che sei sul filo del rasoio se hai errori
                                    st.success(f"🟢 VOTO: {voto}/30 - Accettabile. Ma il libretto ricorda le sue lacune. (Errori accumulati: {st.session_state.errori_totali}/4)")
                                
                                st.markdown(f"**Prossima Domanda:** {nuova_d}")
                                st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": r_prof})
                                
                                # PAUSA TATTICA DI 5 SECONDI
                                st.info("⌛ Il Professore ti scruta in silenzio... (5s)")
                                time.sleep(5)
                                st.rerun()
                        else:
                            st.markdown(r_prof)
                            st.session_state.messaggi_chat.append({"ruolo": "assistant", "contenuto": r_prof})
                            st.rerun()
        else:
            # SCHERMATA DI BOCCIATURA
            st.error("❌ ESAME FALLITO. Il professore ti ha bocciato. Ripresentati al prossimo appello (Premi 'Reset Esame').")

# --- FASE 4 DEVE STARE TUTTO A SINISTRA (ZERO SPAZI) ---
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
REGOLE: Scrivi un commento sarcastico alla Dr. House. Ricorda di impersonare un professore di Farmacia Poi vai a capo e scrivi esattamente "VOTO: X" (dove X è un numero da 1 a 30)."""
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
                
                # 1. Spacchettiamo PRIMA di fare qualsiasi cosa
                testo_salvato = ap['testo_estratto']
                try:
                    t_trasc = testo_salvato.split("[TRASCRIZIONE]")[1].split("[/TRASCRIZIONE]")[0].strip()
                    t_schem = testo_salvato.split("[SCHEMA]")[1].split("[/SCHEMA]")[0].strip()
                    t_riass = testo_salvato.split("[RIASSUNTO]")[1].split("[/RIASSUNTO]")[0].strip()
                except:
                    t_trasc, t_schem, t_riass = "", "", testo_salvato
                    
                # 2. ORA mostriamo a schermo SOLO il riassunto (senza codici!)
                anteprima = t_riass[:500] if t_riass else t_trasc[:500]
                st.write(anteprima + "... [Continua nel PDF]")
                
                st.divider()
                
                # 3. Bottone per scaricare al volo il PDF
                pdf_bytes = genera_pdf_scaricabile(t_trasc, t_schem, t_riass)
                st.download_button(
                    label="📩 Scarica PDF Completo", 
                    data=pdf_bytes, 
                    file_name=f"{ap['titolo'].replace(' ', '_')}.pdf", 
                    mime="application/pdf", 
                    key=f"dl_privato_{ap['id']}"
                )
    else:
        st.info("Il tuo archivio privato è ancora vuoto. Elabora un PDF nella Fase 1 e salvalo come Privato!")
