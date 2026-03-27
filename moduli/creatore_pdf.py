import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def genera_pdf_scaricabile(trascrizione, schema, riassunto):
    """
    Trasforma i testi elaborati in un file PDF formattato.
    Restituisce un buffer di byte pronto per il download di Streamlit.
    """
    buf = io.BytesIO()
    
    # Configurazione del documento (Margini e dimensione foglio)
    doc = SimpleDocTemplate(
        buf, 
        pagesize=letter, 
        rightMargin=50, leftMargin=50, 
        topMargin=50, bottomMargin=50
    )
    
    # Carichiamo gli stili predefiniti (Titoli, paragrafi, ecc.)
    styles = getSampleStyleSheet()
    style_title = styles['Heading1']
    style_sub = styles['Heading2']
    style_normal = styles['Normal']
    
    # La "storia" è la lista di elementi che verranno stampati nel PDF
    story = []
    
    # --- INTESTAZIONE ---
    story.append(Paragraph("Appunti Completi - IoImparo 🎓", style_title))
    story.append(Spacer(1, 20))
    
    # --- SEZIONE 1: TRASCRIZIONE ---
    story.append(Paragraph("📝 1. Trascrizione", style_sub))
    # Trasformiamo i \n in <br/> perché il PDF usa una sorta di HTML per i paragrafi
    testo_trasc = trascrizione.replace('\n', '<br/>')
    story.append(Paragraph(testo_trasc, style_normal))
    story.append(Spacer(1, 20))
    
    # --- SEZIONE 2: SCHEMA ---
    story.append(Paragraph("🖼️ 2. Schema Concettuale", style_sub))
    avviso_schema = "<i>[Nota: Lo schema visivo e navigabile è consultabile interattivamente all'interno della Centrale Operativa Web]</i>"
    story.append(Paragraph(avviso_schema, style_normal))
    story.append(Spacer(1, 20))
    
    # --- SEZIONE 3: RIASSUNTO ---
    story.append(Paragraph("📖 3. Riassunto Completo", style_sub))
    # Puliamo i simboli '**' del grassetto Markdown che nel PDF non funzionano
    testo_riass = riassunto.replace('**', '').replace('\n', '<br/>')
    story.append(Paragraph(testo_riass, style_normal))
    
    # Costruzione effettiva del file
    doc.build(story)
    buf.seek(0)
    
    return buf
