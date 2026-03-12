"""Email service for sending password reset emails via SMTP."""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _get_smtp_config_from_db():
    """Read SMTP settings from AppSettings table."""
    from models import AppSettings
    host = AppSettings.get('smtp_host', '')
    port = AppSettings.get('smtp_port', '587')
    user = AppSettings.get('smtp_user', '')
    password = AppSettings.get('smtp_password', '')
    reset_email = AppSettings.get('reset_email', '')
    return {
        'host': host,
        'port': int(port) if port else 587,
        'user': user,
        'password': password,
        'reset_email': reset_email,
    }


def is_smtp_configured():
    """Check if SMTP has been configured with at least host, user, password, and reset_email."""
    cfg = _get_smtp_config_from_db()
    return all([cfg['host'], cfg['user'], cfg['password'], cfg['reset_email']])


def _send_email(to_addr, subject, html_body):
    """Send an email using the stored SMTP config."""
    cfg = _get_smtp_config_from_db()
    if not all([cfg['host'], cfg['user'], cfg['password']]):
        raise ValueError('SMTP is not configured')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = cfg['user']
    msg['To'] = to_addr
    msg.attach(MIMEText(html_body, 'html'))

    context = ssl.create_default_context()
    port = cfg['port']

    if port == 465:
        with smtplib.SMTP_SSL(cfg['host'], port, context=context, timeout=15) as server:
            server.login(cfg['user'], cfg['password'])
            server.sendmail(cfg['user'], to_addr, msg.as_string())
    else:
        with smtplib.SMTP(cfg['host'], port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(cfg['user'], cfg['password'])
            server.sendmail(cfg['user'], to_addr, msg.as_string())


def send_reset_email(reset_url):
    """Send a password-reset email to the configured reset address."""
    cfg = _get_smtp_config_from_db()
    to_addr = cfg['reset_email']
    if not to_addr:
        raise ValueError('Reset email address is not configured')

    html = f"""\
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 480px; margin: 0 auto; padding: 2rem;">
        <h2 style="color: #58a6ff;">Prompt Copier — Credential Reset</h2>
        <p style="color: #c9d1d9;">
            A credential reset was requested. Click the button below to set a new username and password.
            This link expires in <strong>1 hour</strong>.
        </p>
        <a href="{reset_url}"
           style="display: inline-block; margin: 1.5rem 0; padding: 0.75rem 1.5rem;
                  background-color: #238636; color: #ffffff; text-decoration: none;
                  border-radius: 6px; font-weight: 500;">
            Reset Credentials
        </a>
        <p style="color: #8b949e; font-size: 0.85rem;">
            If you didn't request this, you can safely ignore this email.
        </p>
        <hr style="border: none; border-top: 1px solid #30363d; margin: 1.5rem 0;">
        <p style="color: #8b949e; font-size: 0.75rem;">
            Or copy this link: <a href="{reset_url}" style="color: #58a6ff;">{reset_url}</a>
        </p>
    </div>
    """

    _send_email(to_addr, 'Prompt Copier — Credential Reset', html)


def send_test_email():
    """Send a test email to the configured reset address to verify SMTP works."""
    cfg = _get_smtp_config_from_db()
    to_addr = cfg['reset_email']
    if not to_addr:
        raise ValueError('Reset email address is not configured')

    html = """\
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 480px; margin: 0 auto; padding: 2rem;">
        <h2 style="color: #58a6ff;">Prompt Copier — SMTP Test</h2>
        <p style="color: #3fb950; font-weight: 500;">✅ SMTP is working correctly!</p>
        <p style="color: #c9d1d9;">This is a test email from your Prompt Copier instance.</p>
    </div>
    """

    _send_email(to_addr, 'Prompt Copier — SMTP Test', html)
