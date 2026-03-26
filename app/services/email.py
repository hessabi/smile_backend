import html
import logging

import resend

from app.config import settings

logger = logging.getLogger(__name__)


def _init_resend() -> None:
    resend.api_key = settings.resend_api_key


def send_share_email(
    to_email: str,
    patient_name: str,
    clinic_name: str,
    provider_name: str,
    treatment_type: str,
    share_url: str,
    before_image_url: str | None = None,
    preview_image_url: str | None = None,
    pdf_bytes: bytes | None = None,
) -> bool:
    _init_resend()

    # H3: Escape all user-supplied values for HTML context
    patient_name = html.escape(patient_name)
    clinic_name = html.escape(clinic_name)
    provider_name = html.escape(provider_name)
    treatment_type = html.escape(treatment_type)

    images_html = ""
    if before_image_url and preview_image_url:
        images_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin: 24px 0;">
            <tr>
                <td width="48%" style="text-align: center;">
                    <p style="margin: 0 0 8px; font-size: 14px; color: #666;">Before</p>
                    <img src="{before_image_url}" alt="Before" style="max-width: 100%; border-radius: 8px;" />
                </td>
                <td width="4%"></td>
                <td width="48%" style="text-align: center;">
                    <p style="margin: 0 0 8px; font-size: 14px; color: #666;">Preview</p>
                    <img src="{preview_image_url}" alt="Preview" style="max-width: 100%; border-radius: 8px;" />
                </td>
            </tr>
        </table>
        """

    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px 24px;">
        <h2 style="color: #1a1a1a; margin-bottom: 8px;">{clinic_name}</h2>
        <p style="color: #666; margin-top: 0;">Your Smile Preview from {provider_name}</p>

        <p>Hi {patient_name},</p>

        <p>Here is your {treatment_type} smile preview. This AI-generated simulation shows what your new smile could look like.</p>

        {images_html}

        <div style="text-align: center; margin: 32px 0;">
            <a href="{share_url}" style="background-color: #2563eb; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">View Your Smile Preview</a>
        </div>

        <p style="font-size: 12px; color: #999; margin-top: 32px; border-top: 1px solid #eee; padding-top: 16px;">
            This is an AI-generated simulation for illustration purposes only. Actual results may vary.
            Consult your dental professional for personalized treatment plans.
        </p>

        <p style="font-size: 12px; color: #999;">
            This link will expire in {settings.share_token_expiry_days} days.
        </p>
    </div>
    """

    attachments = []
    if pdf_bytes:
        import base64
        attachments.append({
            "filename": "smile-preview.pdf",
            "content": list(pdf_bytes),
            "type": "application/pdf",
        })

    try:
        params = {
            "from": f"{clinic_name} <noreply@{settings.share_base_url.replace('https://', '').replace('http://', '').split('/')[0]}>",
            "to": [to_email],
            "subject": f"Your Smile Preview from {clinic_name}",
            "html": html_body,
        }
        if attachments:
            params["attachments"] = attachments

        resend.Emails.send(params)
        logger.info("Share email sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send share email to %s", to_email)
        return False
