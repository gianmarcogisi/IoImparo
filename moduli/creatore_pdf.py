import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

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
    
    # Sezione Trascrizione
    story.append(Paragraph("📝 1. Trascrizione", style_sub))
    story.append(Paragraph(trascrizione.replace('\n', '<br/>'), style_normal))
    story.append(Spacer(1, 20))
    
    # Sezione Riassunto
    story.append(Paragraph("📖 2. Riassunto Completo", style_sub))
    testo_riassunto = riassunto.replace('**', '') 
    story.append(Paragraph(testo_riassunto.replace('\n', '<br/>'), style_normal))
    
    doc.build(story)
    buf.seek(0)
    return buf
