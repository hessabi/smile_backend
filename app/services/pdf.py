import io
import logging
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from app.services.storage import download_image

logger = logging.getLogger(__name__)


def _add_image_from_gcs(c: canvas.Canvas, image_key: str, x: float, y: float, width: float, height: float) -> bool:
    try:
        image_bytes = download_image(image_key)
        img_reader = io.BytesIO(image_bytes)
        from reportlab.lib.utils import ImageReader
        img = ImageReader(img_reader)
        c.drawImage(img, x, y, width=width, height=height, preserveAspectRatio=True, anchor="c")
        return True
    except Exception:
        logger.exception("Failed to load image: %s", image_key)
        c.setFont("Helvetica", 10)
        c.setFillColorRGB(0.6, 0.6, 0.6)
        c.drawCentredString(x + width / 2, y + height / 2, "Image unavailable")
        return False


def generate_simulation_pdf(
    clinic_name: str,
    provider_name: str,
    patient_name: str,
    treatment_type: str,
    shade: str,
    created_at: datetime,
    before_image_key: str,
    result_image_key: str | None,
    post_procedure_image_key: str | None = None,
) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    page_width, page_height = letter

    margin = 0.75 * inch
    content_width = page_width - 2 * margin

    y = page_height - margin

    c.setFont("Helvetica-Bold", 20)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawString(margin, y, clinic_name)
    y -= 24

    c.setFont("Helvetica", 12)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(margin, y, "Smile Preview Report")
    y -= 36

    c.setFont("Helvetica", 11)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    details = [
        f"Patient: {patient_name}",
        f"Provider: {provider_name}",
        f"Treatment: {treatment_type.replace('_', ' ').title()}",
        f"Shade: {shade.title()}",
        f"Date: {created_at.strftime('%B %d, %Y')}",
    ]
    for detail in details:
        c.drawString(margin, y, detail)
        y -= 18

    y -= 12

    has_post_op = post_procedure_image_key is not None
    num_images = 3 if has_post_op else 2

    if has_post_op:
        img_width = (content_width - 0.25 * inch * 2) / 3
    else:
        img_width = (content_width - 0.25 * inch) / 2

    img_height = img_width * 1.2

    if y - img_height - 30 < margin:
        img_height = y - margin - 30

    labels = ["Before"]
    keys = [before_image_key]
    if result_image_key:
        labels.append("AI Preview")
        keys.append(result_image_key)
    if has_post_op:
        labels.append("Post-Procedure")
        keys.append(post_procedure_image_key)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.3, 0.3, 0.3)

    for i, (label, key) in enumerate(zip(labels, keys)):
        x = margin + i * (img_width + 0.25 * inch)
        c.drawCentredString(x + img_width / 2, y, label)
        _add_image_from_gcs(c, key, x, y - img_height - 4, img_width, img_height)

    y = y - img_height - 36

    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    disclaimer = (
        "DISCLAIMER: This is an AI-generated simulation for illustration purposes only. "
        "Actual results may vary based on individual dental conditions, treatment approach, "
        "and other factors. This preview does not constitute a guarantee of outcomes. "
        "Please consult your dental professional for personalized treatment plans and expectations."
    )

    text_obj = c.beginText(margin, y)
    text_obj.setFont("Helvetica", 8)
    text_obj.setFillColorRGB(0.5, 0.5, 0.5)

    words = disclaimer.split()
    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        if c.stringWidth(test_line, "Helvetica", 8) > content_width:
            text_obj.textLine(line)
            line = word
        else:
            line = test_line
    if line:
        text_obj.textLine(line)

    c.drawText(text_obj)

    c.save()
    return buf.getvalue()
