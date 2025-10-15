from reportlab.lib.pagesizes import landscape, legal
from reportlab.lib.units import inch


def get_pdf_layout():
    """Retorna parâmetros padrão para geração de PDFs."""
    return {
        "pagesize": landscape(legal),
        "leftMargin": 0.2 * inch,
        "rightMargin": 0.2 * inch,
        "topMargin": 0.3 * inch,
        "bottomMargin": 0.3 * inch,
    }
