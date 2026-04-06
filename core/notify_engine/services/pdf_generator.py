"""
notify_engine/pdf_generator.py

Generates PDF attachments for outgoing emails.

Strategy
--------
Each pdf_template_code maps to a renderer class registered in PDF_REGISTRY.
The engine calls `generate_pdf(template_code, context)` and gets back a
file path it can attach to the email.

Supported renderers (all using reportlab):
  - ReportLabRenderer   – programmatic layout (tables, headings, grids)
  - HTMLRenderer        – render an HTML string to PDF via xhtml2pdf (weasyprint
                          is also supported as a drop-in swap)

Quick usage from engine.py:
    from .pdf_generator import generate_pdf
    pdf_path = generate_pdf('enquiry_pdf', context={'enquiry_number': 'ENQ-1025', ...})

Requirements:
    pip install reportlab xhtml2pdf
"""

import os
import uuid
import logging
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
# Override via Django settings: NOTIFY_ENGINE_PDF_DIR = '/var/media/email_pdfs/'
try:
    from django.conf import settings
    PDF_OUTPUT_DIR = getattr(settings, 'NOTIFY_ENGINE_PDF_DIR',
                             os.path.join(tempfile.gettempdir(), 'notify_engine_pdfs'))
except Exception:
    PDF_OUTPUT_DIR = os.path.join(tempfile.gettempdir(), 'notify_engine_pdfs')

os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Base renderer
# ---------------------------------------------------------------------------

class BasePDFRenderer(ABC):
    """
    All PDF renderers must implement `render(context) -> str`
    and return the absolute path to the generated PDF file.
    """

    def _output_path(self, prefix: str = 'pdf') -> str:
        filename = f"{prefix}_{uuid.uuid4().hex[:10]}.pdf"
        return os.path.join(PDF_OUTPUT_DIR, filename)

    @abstractmethod
    def render(self, context: dict[str, Any]) -> str:
        """Generate PDF and return its absolute file path."""
        ...


# ---------------------------------------------------------------------------
# ReportLab renderer — programmatic layout
# ---------------------------------------------------------------------------

class ReportLabRenderer(BasePDFRenderer):
    """
    Subclass this to build custom PDF layouts with reportlab's Platypus API.

    Override `build_story(context, styles)` and return a list of Flowables.
    The base implementation produces a simple key-value summary sheet so it
    works out of the box for any context dict.
    """

    title: str = 'Document'
    filename_prefix: str = 'doc'

    def build_story(self, context: dict, styles) -> list:
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm

        story = []

        # Title
        story.append(Paragraph(self.title, styles['Title']))
        story.append(Spacer(1, 6 * mm))

        # Generated timestamp
        ts = datetime.now().strftime('%d %b %Y  %H:%M')
        story.append(Paragraph(f"Generated: {ts}", styles['Normal']))
        story.append(Spacer(1, 8 * mm))

        # Key-value table from context
        table_data = [['Field', 'Value']]
        for key, value in context.items():
            table_data.append([str(key).replace('_', ' ').title(), str(value)])

        col_widths = [70 * mm, 100 * mm]
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0),  colors.HexColor('#4A4E69')),
            ('TEXTCOLOR',    (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',     (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, 0),  10),
            ('BOTTOMPADDING',(0, 0), (-1, 0),  8),
            ('TOPPADDING',   (0, 0), (-1, 0),  8),
            ('ROWBACKGROUNDS',(0, 1),(-1, -1), [colors.HexColor('#F7F7F7'),
                                                colors.white]),
            ('FONTNAME',     (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',     (0, 1), (-1, -1), 9),
            ('TOPPADDING',   (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING',(0, 1), (-1, -1), 6),
            ('GRID',         (0, 0), (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
            ('LEFTPADDING',  (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(t)
        return story

    def render(self, context: dict) -> str:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm

        out_path = self._output_path(self.filename_prefix)
        doc = SimpleDocTemplate(
            out_path,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )
        styles = getSampleStyleSheet()
        story = self.build_story(context, styles)
        doc.build(story)
        logger.info("PDF generated: %s", out_path)
        return out_path


# ---------------------------------------------------------------------------
# HTML renderer — render an HTML template string to PDF
# ---------------------------------------------------------------------------

class HTMLRenderer(BasePDFRenderer):
    """
    Renders an HTML string (with context tags already resolved) to a PDF.

    Supports two backends:
      - 'xhtml2pdf'   (default, pure Python, easier to install)
      - 'weasyprint'  (better CSS support, requires system libs)

    Set backend = 'weasyprint' on your subclass if needed.

    Override `get_html(context)` to return your HTML string.
    The default implementation renders the Django template found at
    `template_name` using the context dict.
    """

    template_name: str = ''   # e.g. 'emails/enquiry_pdf.html'
    filename_prefix: str = 'html_pdf'
    backend: str = 'xhtml2pdf'

    def get_html(self, context: dict) -> str:
        """Return the HTML string to convert. Override for custom logic."""
        if not self.template_name:
            raise NotImplementedError(
                "Set template_name or override get_html() on your HTMLRenderer subclass."
            )
        from django.template.loader import render_to_string
        return render_to_string(self.template_name, context)

    def _render_xhtml2pdf(self, html: str, out_path: str) -> str:
        from xhtml2pdf import pisa
        with open(out_path, 'wb') as pdf_file:
            result = pisa.CreatePDF(html, dest=pdf_file)
        if result.err:
            raise RuntimeError(f"xhtml2pdf error: {result.err}")
        return out_path

    def _render_weasyprint(self, html: str, out_path: str) -> str:
        from weasyprint import HTML
        HTML(string=html).write_pdf(out_path)
        return out_path

    def render(self, context: dict) -> str:
        html = self.get_html(context)
        out_path = self._output_path(self.filename_prefix)

        if self.backend == 'weasyprint':
            path = self._render_weasyprint(html, out_path)
        else:
            path = self._render_xhtml2pdf(html, out_path)

        logger.info("PDF generated (HTML backend=%s): %s", self.backend, path)
        return path


# ---------------------------------------------------------------------------
# Built-in template renderers
# Each maps to a pdf_template_code in email_master.pdf_template_code
# ---------------------------------------------------------------------------

class EnquiryPDFRenderer(ReportLabRenderer):
    """Generates a formatted enquiry summary PDF."""
    title = 'Enquiry Summary'
    filename_prefix = 'enquiry'

    def build_story(self, context: dict, styles) -> list:
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib import colors
        from reportlab.lib.units import mm

        story = []

        # ---- Header block ----
        story.append(Paragraph(self.title, styles['Title']))
        story.append(Paragraph(
            f"Enquiry No: <b>{context.get('enquiry_number', '—')}</b>",
            styles['Heading2']
        ))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#CCCCCC')))
        story.append(Spacer(1, 5 * mm))

        # ---- Customer info ----
        story.append(Paragraph('Customer Details', styles['Heading3']))
        fields = [
            ('Customer Name', context.get('customer_name', '')),
            ('Email',         context.get('customer_email', '')),
            ('Phone',         context.get('customer_phone', '')),
            ('Company',       context.get('company_name', '')),
        ]
        for label, value in fields:
            story.append(Paragraph(f"<b>{label}:</b>  {value}", styles['Normal']))
            story.append(Spacer(1, 2 * mm))

        story.append(Spacer(1, 4 * mm))

        # ---- Enquiry info ----
        story.append(Paragraph('Enquiry Details', styles['Heading3']))
        detail_fields = [
            ('Created Date', context.get('created_date', '')),
            ('Status',       context.get('status', '')),
            ('Description',  context.get('description', '')),
        ]
        for label, value in detail_fields:
            story.append(Paragraph(f"<b>{label}:</b>  {value}", styles['Normal']))
            story.append(Spacer(1, 2 * mm))

        story.append(Spacer(1, 6 * mm))

        # ---- Footer ----
        ts = datetime.now().strftime('%d %b %Y  %H:%M')
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#CCCCCC')))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(f"<font size=8 color='grey'>Generated on {ts}</font>", styles['Normal']))

        return story


class QuotationPDFRenderer(ReportLabRenderer):
    """Generates a formatted quotation PDF with a line-item table."""
    title = 'Quotation'
    filename_prefix = 'quotation'

    def build_story(self, context: dict, styles) -> list:
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib import colors
        from reportlab.lib.units import mm

        story = []

        story.append(Paragraph(self.title, styles['Title']))
        story.append(Paragraph(
            f"Quotation No: <b>{context.get('quotation_number', '—')}</b>  |  "
            f"Date: {context.get('quotation_date', '')}",
            styles['Normal']
        ))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#CCCCCC')))
        story.append(Spacer(1, 5 * mm))

        # Customer
        story.append(Paragraph(f"To: <b>{context.get('customer_name', '')}</b>", styles['Normal']))
        story.append(Paragraph(context.get('customer_email', ''), styles['Normal']))
        story.append(Spacer(1, 6 * mm))

        # Line items — context['items'] should be list of dicts with
        # keys: description, qty, unit_price, total
        items = context.get('items', [])
        if items:
            table_data = [['Description', 'Qty', 'Unit Price', 'Total']]
            for item in items:
                table_data.append([
                    item.get('description', ''),
                    str(item.get('qty', '')),
                    str(item.get('unit_price', '')),
                    str(item.get('total', '')),
                ])
            table_data.append(['', '', 'Grand Total', str(context.get('grand_total', ''))])

            col_widths = [90 * mm, 20 * mm, 35 * mm, 35 * mm]
            t = Table(table_data, colWidths=col_widths)
            t.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0),  (-1, 0),  colors.HexColor('#4A4E69')),
                ('TEXTCOLOR',     (0, 0),  (-1, 0),  colors.white),
                ('FONTNAME',      (0, 0),  (-1, 0),  'Helvetica-Bold'),
                ('FONTSIZE',      (0, 0),  (-1, -1), 9),
                ('TOPPADDING',    (0, 0),  (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0),  (-1, -1), 6),
                ('ROWBACKGROUNDS',(0, 1),  (-1, -2), [colors.HexColor('#F7F7F7'), colors.white]),
                ('FONTNAME',      (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND',    (0, -1), (-1, -1), colors.HexColor('#E8E8F0')),
                ('GRID',          (0, 0),  (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
                ('LEFTPADDING',   (0, 0),  (-1, -1), 8),
                ('RIGHTPADDING',  (0, 0),  (-1, -1), 8),
            ]))
            story.append(t)

        story.append(Spacer(1, 6 * mm))
        ts = datetime.now().strftime('%d %b %Y  %H:%M')
        story.append(Paragraph(f"<font size=8 color='grey'>Generated on {ts}</font>", styles['Normal']))
        return story


class InvoicePDFRenderer(ReportLabRenderer):
    """Generates a professional invoice PDF."""
    title = 'Tax Invoice'
    filename_prefix = 'invoice'

    def build_story(self, context: dict, styles) -> list:
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib import colors
        from reportlab.lib.units import mm

        story = []
        story.append(Paragraph(self.title, styles['Title']))
        story.append(Paragraph(
            f"Invoice No: <b>{context.get('invoice_number', '—')}</b>  |  "
            f"Date: {context.get('invoice_date', '')}  |  "
            f"Due: {context.get('due_date', '')}",
            styles['Normal']
        ))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#CCCCCC')))
        story.append(Spacer(1, 5 * mm))

        # Bill-to block
        story.append(Paragraph("Bill To", styles['Heading3']))
        story.append(Paragraph(f"<b>{context.get('customer_name', '')}</b>", styles['Normal']))
        story.append(Paragraph(context.get('customer_address', ''), styles['Normal']))
        story.append(Paragraph(context.get('customer_email', ''), styles['Normal']))
        story.append(Spacer(1, 6 * mm))

        # Line items
        items = context.get('items', [])
        if items:
            table_data = [['Description', 'Qty', 'Rate', 'Tax %', 'Amount']]
            for item in items:
                table_data.append([
                    item.get('description', ''),
                    str(item.get('qty', '')),
                    str(item.get('rate', '')),
                    str(item.get('tax_pct', '')),
                    str(item.get('amount', '')),
                ])

            subtotal    = context.get('subtotal', '')
            tax_amount  = context.get('tax_amount', '')
            grand_total = context.get('grand_total', '')

            table_data += [
                ['', '', '', 'Subtotal',   str(subtotal)],
                ['', '', '', 'Tax',        str(tax_amount)],
                ['', '', '', 'Total Due',  str(grand_total)],
            ]

            col_widths = [80 * mm, 18 * mm, 25 * mm, 22 * mm, 30 * mm]
            t = Table(table_data, colWidths=col_widths)
            t.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0),  (-1, 0),  colors.HexColor('#22223B')),
                ('TEXTCOLOR',     (0, 0),  (-1, 0),  colors.white),
                ('FONTNAME',      (0, 0),  (-1, 0),  'Helvetica-Bold'),
                ('FONTSIZE',      (0, 0),  (-1, -1), 9),
                ('TOPPADDING',    (0, 0),  (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0),  (-1, -1), 6),
                ('ROWBACKGROUNDS',(0, 1),  (-1, -4), [colors.HexColor('#F7F7F7'), colors.white]),
                ('FONTNAME',      (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND',    (0, -1), (-1, -1), colors.HexColor('#DDE1FF')),
                ('GRID',          (0, 0),  (-1, -1), 0.4, colors.HexColor('#CCCCCC')),
                ('LEFTPADDING',   (0, 0),  (-1, -1), 8),
                ('RIGHTPADDING',  (0, 0),  (-1, -1), 8),
            ]))
            story.append(t)

        story.append(Spacer(1, 6 * mm))

        # Payment note
        if context.get('payment_terms'):
            story.append(Paragraph(f"<b>Payment Terms:</b> {context['payment_terms']}", styles['Normal']))
            story.append(Spacer(1, 2 * mm))
        if context.get('bank_details'):
            story.append(Paragraph(f"<b>Bank Details:</b> {context['bank_details']}", styles['Normal']))

        story.append(Spacer(1, 6 * mm))
        ts = datetime.now().strftime('%d %b %Y  %H:%M')
        story.append(Paragraph(f"<font size=8 color='grey'>Generated on {ts}</font>", styles['Normal']))
        return story


# ---------------------------------------------------------------------------
# Registry — maps pdf_template_code → renderer instance
# ---------------------------------------------------------------------------

PDF_REGISTRY: dict[str, BasePDFRenderer] = {
    'enquiry_pdf':    EnquiryPDFRenderer(),
    'quotation_pdf':  QuotationPDFRenderer(),
    'invoice_pdf':    InvoicePDFRenderer(),
}


def register_renderer(template_code: str, renderer: BasePDFRenderer) -> None:
    """
    Register a custom renderer at runtime or at app startup.

    Call this from your app's AppConfig.ready():
        from notify_engine.pdf_generator import register_renderer
        register_renderer('purchase_order_pdf', PurchaseOrderRenderer())
    """
    PDF_REGISTRY[template_code] = renderer
    logger.debug("PDF renderer registered: %s → %s", template_code, type(renderer).__name__)


# ---------------------------------------------------------------------------
# Public entry point (called from queue.py)
# ---------------------------------------------------------------------------

def generate_pdf(template_code: str, context: dict) -> str:
    """
    Generate a PDF for the given template_code and context dict.

    Returns the absolute file path of the generated PDF.
    Raises ValueError if no renderer is registered for the template_code.
    Raises RuntimeError if PDF generation fails.
    """
    renderer = PDF_REGISTRY.get(template_code)
    if renderer is None:
        raise ValueError(
            f"No PDF renderer registered for template_code='{template_code}'. "
            f"Available codes: {list(PDF_REGISTRY.keys())}"
        )

    try:
        path = renderer.render(context)
    except Exception as exc:
        logger.exception("PDF generation failed for template_code='%s'", template_code)
        raise RuntimeError(f"PDF generation failed: {exc}") from exc

    if not os.path.isfile(path):
        raise RuntimeError(f"Renderer returned a path that does not exist: {path}")

    return path