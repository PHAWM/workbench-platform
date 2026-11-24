import resend

from typing import Optional
import logging

from src.core.config import settings

logger = logging.getLogger(__name__)


def send_email(
    email_to: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """
    Args:
        email_to: User's e-mail address
        subject: Subject of e-mail
        html_content: Content of e-mail in HTML
        text_content: Content of e-mail in text
    Returns:
        True if e-mail was sent
        False if e-mail was not sent
    """
    params: resend.Emails.SendParams = {
          "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
          "to": email_to,
		  "subject": subject,
		  "html": html_content,
          "text": text_content
		   }

    resend.api_key = f"{settings.RESEND_API_KEY}"
    try:
        email = resend.Emails.send(params)
        logger.info(f"Email sent successfully to {email_to}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {email_to}: {str(e)}")
        return False

def send_verification_email(email_to: str, token: str, tenant_id: Optional[str] = None) -> bool:
    """
    Send email verification link to user

    Args:
        email_to: User's email address
        token: Verification token
        tenant_id: Tenant schema name — appended as ?tenant_id= so the frontend
                   knows which X-Tenant-ID to send on subsequent requests

    Returns:
        True if email was sent successfully
    """
    tenant_prefix = f"/{tenant_id}" if tenant_id else ""
    verification_link = f"{settings.FRONTEND_URL}{tenant_prefix}/verify-email?token={token}"

    subject = f"{settings.PROJECT_NAME} - Verify your email"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #007bff;
                color: #ffffff !important;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                font-size: 12px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Verify Your Email Address</h2>
            <p>Thank you for registering with {settings.PROJECT_NAME}!</p>
            <p>Please click the button below to verify your email address:</p>
            <a href="{verification_link}" class="button">Verify Email</a>
            <p>Or copy and paste this link into your browser:</p>
            <p>{verification_link}</p>
            <p>This link will expire in 7 days.</p>
            <div class="footer">
                <p>If you didn't create an account, please ignore this email.</p>
                <p>&copy; {settings.PROJECT_NAME}</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    Verify Your Email Address

    Thank you for registering with {settings.PROJECT_NAME}!

    Please visit the following link to verify your email address:
    {verification_link}

    This link will expire in 7 days.

    If you didn't create an account, please ignore this email.
    """

    return send_email(email_to, subject, html_content, text_content)


def send_invitation_email(email_to: str, token: str, inviter_name: Optional[str] = None, tenant_id: Optional[str] = None) -> bool:
    """
    Send invitation email to user with password setup link

    Args:
        email_to: User's email address
        token: Invitation token
        inviter_name: Name of the person who sent the invitation (optional)
        tenant_id: Tenant schema name — appended as ?tenant_id= so the frontend
                   knows which X-Tenant-ID to send on login after password setup

    Returns:
        True if email was sent successfully
    """
    tenant_prefix = f"/{tenant_id}" if tenant_id else ""
    invitation_link = f"{settings.FRONTEND_URL}{tenant_prefix}/accept-invite?token={token}"

    subject = f"{settings.PROJECT_NAME} - You've been invited!"

    inviter_text = f" by {inviter_name}" if inviter_name else ""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #28a745;
                color: #ffffff !important;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                font-size: 12px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>You've Been Invited!</h2>
            <p>You have been invited{inviter_text} to join {settings.PROJECT_NAME}!</p>
            <p>Click the button below to set your password and activate your account:</p>
            <a href="{invitation_link}" class="button">Set Password & Activate Account</a>
            <p>Or copy and paste this link into your browser:</p>
            <p>{invitation_link}</p>
            <p>This invitation will expire in 7 days.</p>
            <div class="footer">
                <p>If you didn't expect this invitation, please ignore this email.</p>
                <p>&copy; {settings.PROJECT_NAME}</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    You've Been Invited!

    You have been invited{inviter_text} to join {settings.PROJECT_NAME}!

    Please visit the following link to set your password and activate your account:
    {invitation_link}

    This invitation will expire in 7 days.

    If you didn't expect this invitation, please ignore this email.
    """

    return send_email(email_to, subject, html_content, text_content)


def send_audit_notification_email(
    email_to: str,
    audit_name: str,
    inviter_name: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> bool:
    """
    Notify an already-registered user they have been added to an audit.
    No token needed — they log in directly.
    """
    inviter_text = f" by {inviter_name}" if inviter_name else ""
    tenant_prefix = f"/{tenant_id}" if tenant_id else ""
    login_link = f"{settings.FRONTEND_URL}{tenant_prefix}/login"
    subject = f"{settings.PROJECT_NAME} - You've been added to an audit"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{
                display: inline-block; padding: 12px 24px;
                background-color: #007bff; color: #ffffff !important;
                text-decoration: none; border-radius: 4px; margin: 20px 0;
            }}
            .footer {{
                margin-top: 30px; padding-top: 20px;
                border-top: 1px solid #ddd; font-size: 12px; color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>You've Been Added to an Audit</h2>
            <p>You have been invited{inviter_text} to participate in the audit
            <strong>{audit_name}</strong> on {settings.PROJECT_NAME}.</p>
            <p>Log in to your account to get started:</p>
            <a href="{login_link}" class="button">Go to {settings.PROJECT_NAME}</a>
            <p>Or copy this link: {login_link}</p>
            <div class="footer">
                <p>If you didn't expect this, please contact your audit instigator.</p>
                <p>&copy; {settings.PROJECT_NAME}</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    You've Been Added to an Audit

    You have been invited{inviter_text} to participate in the audit '{audit_name}' on {settings.PROJECT_NAME}.

    Log in at: {login_link}

    If you didn't expect this, please contact your audit instigator.
    """

    return send_email(email_to, subject, html_content, text_content)


def send_password_reset_email(email_to: str, token: str, tenant_id: Optional[str] = None) -> bool:
    """
    Send password reset link to user

    Args:
        email_to: User's email address
        token: Password reset token
        tenant_id: Tenant schema name — appended as ?tenant_id= so the frontend
                   knows which X-Tenant-ID to send on login after the reset

    Returns:
        True if email was sent successfully
    """
    tenant_prefix = f"/{tenant_id}" if tenant_id else ""
    reset_link = f"{settings.FRONTEND_URL}{tenant_prefix}/reset-password?token={token}"

    subject = f"{settings.PROJECT_NAME} - Reset your password"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #dc3545;
                color: #ffffff !important;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                font-size: 12px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Reset Your Password</h2>
            <p>We received a request to reset your password for {settings.PROJECT_NAME}.</p>
            <p>Click the button below to reset your password:</p>
            <a href="{reset_link}" class="button">Reset Password</a>
            <p>Or copy and paste this link into your browser:</p>
            <p>{reset_link}</p>
            <p>This link will expire in {settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS} hours.</p>
            <div class="footer">
                <p>If you didn't request a password reset, please ignore this email.</p>
                <p>&copy; {settings.PROJECT_NAME}</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    Reset Your Password

    We received a request to reset your password for {settings.PROJECT_NAME}.

    Please visit the following link to reset your password:
    {reset_link}

    This link will expire in {settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS} hours.

    If you didn't request a password reset, please ignore this email.
    """

    return send_email(email_to, subject, html_content, text_content)
