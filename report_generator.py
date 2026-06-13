import json

from dataclasses import asdict
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def export_json(file_path, analysis_result):
    """Exports DfM analysis results to a JSON file, sanitizing non-serializable OCC objects."""
    data = asdict(analysis_result)
    
    # Clean up non-serializable OCC shapes/edges
    if "parting_line" in data:
        pl = data["parting_line"]
        if "loops" in pl:
            for loop in pl["loops"]:
                if "edges" in loop:
                    del loop["edges"]
        if "raw_edges" in pl:
            for re in pl["raw_edges"]:
                if "edge" in re:
                    del re["edge"]
                    
    def sanitize(obj):
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items() if not str(type(v)).startswith("<class 'OCC.")}
        elif isinstance(obj, list):
            return [sanitize(x) for x in obj if not str(type(x)).startswith("<class 'OCC.")]
        return obj
        
    sanitized_data = sanitize(data)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(sanitized_data, f, indent=4)

def export_pdf(file_path, analysis_result):
    """Generates a professional PDF DfM analysis report using ReportLab."""
    doc = SimpleDocTemplate(file_path, pagesize=letter,
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Custom styles matching brand theme
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#e20015'), # Primary red
        spaceAfter=15
    )
    
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=colors.HexColor('#181825'),
        spaceBefore=12,
        spaceAfter=6
    )
    
    body_style = styles['Normal']
    header_col_style = ParagraphStyle('HeaderCol', parent=body_style, textColor=colors.whitesmoke, fontName='Helvetica-Bold')
    
    story.append(Paragraph("DfM Analysis Report — DfM Advisor", title_style))
    story.append(Paragraph(f"<b>Model Filename:</b> {analysis_result.filename}", body_style))
    story.append(Paragraph(f"<b>Selected Material:</b> {analysis_result.material}", body_style))
    story.append(Spacer(1, 10))
    
    # Summary table
    opt_stats = analysis_result.optimal_stats
    classification = opt_stats.get("classification", "PARTIALLY MOLDABLE")
    
    data = [
        [Paragraph("Metric", header_col_style), Paragraph("Value", header_col_style)],
        [Paragraph("Total Face Count", body_style), Paragraph(str(analysis_result.face_count), body_style)],
        [Paragraph(f"Optimal {getattr(analysis_result, 'optimal_axis', 'Z')} Parting Position", body_style), Paragraph(f"{analysis_result.optimal_z:.2f} mm", body_style)],
        [Paragraph("Moldability Score", body_style), Paragraph(f"{analysis_result.moldability_score:.2f} / 100", body_style)],
        [Paragraph("Classification Status", body_style), Paragraph(classification, body_style)],
        [Paragraph("Undercuts Count", body_style), Paragraph(str(opt_stats.get('undercut_count', 0)), body_style)],
        [Paragraph("Undercuts Area", body_style), Paragraph(f"{opt_stats.get('undercut_area', 0.0):.2f} mm²", body_style)],
        [Paragraph("Faces requiring geometric splitting", body_style), Paragraph(str(opt_stats.get('crossing_faces', 0)), body_style)],
        [Paragraph("Parting Line Length", body_style), Paragraph(f"{analysis_result.parting_line.get('total_length_mm', 0.0):.2f} mm", body_style)],
        [Paragraph("Closed Parting Loop", body_style), Paragraph("Yes" if analysis_result.parting_line.get('is_closed_loop') else "No", body_style)],
    ]
    
    t = Table(data, colWidths=[220, 230])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.HexColor('#181825')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    
    story.append(t)
    story.append(Spacer(1, 15))
    
    # Justification section
    story.append(Paragraph("Engineering Recommendation", heading_style))
    axis_label = getattr(analysis_result, 'optimal_axis', 'Z')
    justification = (
        f"The {axis_label} = {analysis_result.optimal_z:.2f} mm split minimizes undercut area ({opt_stats.get('undercut_area', 0.0):.1f} mm²), "
        f"reduces faces requiring geometric splitting ({opt_stats.get('crossing_faces', 0)}), and produces a highly balanced core/cavity separation. "
        f"This parting plane yields the highest moldability score ({analysis_result.moldability_score:.1f}) among all scanned candidates. "
        f"The physical moldability status is classified as: '{classification}'."
    )
    story.append(Paragraph(justification, body_style))
    
    doc.build(story)
