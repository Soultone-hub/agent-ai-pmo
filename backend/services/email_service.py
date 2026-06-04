import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from backend.config import settings


def _send(msg: MIMEMultipart) -> None:
    """Shared SMTP send helper."""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"[WARNING] SMTP non configuré. Email '{msg['Subject']}' vers {msg['To']} non envoyé.")
        return
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
            print(f"[INFO] Email '{msg['Subject']}' envoyé à {msg['To']}")
    except Exception as e:
        print(f"[ERROR] Échec de l'envoi de l'email: {e}")


def _base_msg(to_email: str, subject: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    return msg


# ── Email de réinitialisation de mot de passe ──────────────────────────────────
def send_reset_password_email(to_email: str, token: str) -> None:
    """Envoie un email de réinitialisation de mot de passe."""
    reset_url = f"{settings.FRONTEND_URL}/login?token={token}"

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"[WARNING] SMTP non configuré. Lien de réinitialisation: {reset_url}")
        return

    text = f"""Bonjour,

Vous avez demandé la réinitialisation de votre mot de passe PilotIA.
Cliquez sur le lien ci-dessous pour définir un nouveau mot de passe :

{reset_url}

Ce lien est valable 1 heure.
Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.

L'équipe PilotIA"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f0f1a;font-family:'Inter',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f1a;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#1a1a2e;border-radius:16px;overflow:hidden;border:1px solid rgba(55,138,221,0.2);">
        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#1e3a5f,#0d1f3c);padding:32px 40px;text-align:center;">
          <div style="font-size:28px;font-weight:700;color:#378ADD;letter-spacing:-0.5px;">Pilot<span style="color:#ffffff;">IA</span></div>
          <div style="color:#94a3b8;font-size:13px;margin-top:4px;">Intelligence Artificielle pour le PMO</div>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:40px;">
          <h2 style="color:#ffffff;font-size:20px;margin:0 0 16px;">Réinitialisation du mot de passe</h2>
          <p style="color:#94a3b8;line-height:1.7;margin:0 0 24px;">
            Vous avez demandé la réinitialisation de votre mot de passe PilotIA.<br>
            Cliquez sur le bouton ci-dessous pour en définir un nouveau.
          </p>
          <div style="text-align:center;margin:32px 0;">
            <a href="{reset_url}" style="display:inline-block;background:#378ADD;color:#ffffff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:600;font-size:15px;">
              Réinitialiser mon mot de passe
            </a>
          </div>
          <p style="color:#64748b;font-size:13px;margin:24px 0 0;">
            Ce lien est valable <strong style="color:#94a3b8;">1 heure</strong>.<br>
            Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.
          </p>
        </td></tr>
        <!-- Footer -->
        <tr><td style="padding:24px 40px;border-top:1px solid rgba(55,138,221,0.1);text-align:center;">
          <p style="color:#475569;font-size:12px;margin:0;">© 2025 PilotIA · <a href="{settings.FRONTEND_URL}" style="color:#378ADD;text-decoration:none;">pilotia.app</a></p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    msg = _base_msg(to_email, "Réinitialisation de votre mot de passe PilotIA")
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    _send(msg)


# ── Email de bienvenue ─────────────────────────────────────────────────────────
def send_welcome_email(to_email: str, first_name: str) -> None:
    """Envoie un email de bienvenue après la création du compte."""
    login_url = f"{settings.FRONTEND_URL}/login"
    name = first_name or "cher utilisateur"

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"[WARNING] SMTP non configuré. Bienvenue à {to_email} ({first_name})")
        return

    text = f"""Bonjour {name},

Bienvenue sur PilotIA ! Votre compte a été créé avec succès.

PilotIA est votre assistant IA pour la gestion de projets PMO : analyse de documents,
suivi des risques, tableaux de bord COPIL, KPIs et bien plus.

Accédez à votre espace : {login_url}

Bonne gestion de projets !
L'équipe PilotIA"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f0f1a;font-family:'Inter',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f1a;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#1a1a2e;border-radius:16px;overflow:hidden;border:1px solid rgba(55,138,221,0.2);">
        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#1e3a5f,#0d1f3c);padding:32px 40px;text-align:center;">
          <div style="font-size:28px;font-weight:700;color:#378ADD;letter-spacing:-0.5px;">Pilot<span style="color:#ffffff;">IA</span></div>
          <div style="color:#94a3b8;font-size:13px;margin-top:4px;">Intelligence Artificielle pour le PMO</div>
        </td></tr>
        <!-- Hero -->
        <tr><td style="padding:40px 40px 0;">
          <h2 style="color:#ffffff;font-size:22px;margin:0 0 12px;">Bienvenue, {name} ! 🎉</h2>
          <p style="color:#94a3b8;line-height:1.7;margin:0 0 20px;">
            Votre compte PilotIA a été créé avec succès. Vous pouvez désormais accéder à
            l'ensemble de vos outils IA pour la gestion de projets.
          </p>
        </td></tr>
        <!-- Features -->
        <tr><td style="padding:24px 40px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td width="48%" style="background:rgba(55,138,221,0.08);border:1px solid rgba(55,138,221,0.15);border-radius:10px;padding:16px;vertical-align:top;">
                <div style="color:#378ADD;font-size:18px;margin-bottom:8px;">📄</div>
                <div style="color:#ffffff;font-weight:600;font-size:14px;margin-bottom:4px;">Analyse de documents</div>
                <div style="color:#64748b;font-size:12px;line-height:1.5;">Extrayez les informations clés de vos rapports de projet.</div>
              </td>
              <td width="4%"></td>
              <td width="48%" style="background:rgba(55,138,221,0.08);border:1px solid rgba(55,138,221,0.15);border-radius:10px;padding:16px;vertical-align:top;">
                <div style="color:#378ADD;font-size:18px;margin-bottom:8px;">⚠️</div>
                <div style="color:#ffffff;font-weight:600;font-size:14px;margin-bottom:4px;">Matrice des risques</div>
                <div style="color:#64748b;font-size:12px;line-height:1.5;">Identifiez et priorisez les risques de vos projets.</div>
              </td>
            </tr>
            <tr><td colspan="3" style="padding-top:12px;"></td></tr>
            <tr>
              <td width="48%" style="background:rgba(55,138,221,0.08);border:1px solid rgba(55,138,221,0.15);border-radius:10px;padding:16px;vertical-align:top;">
                <div style="color:#378ADD;font-size:18px;margin-bottom:8px;">📊</div>
                <div style="color:#ffffff;font-weight:600;font-size:14px;margin-bottom:4px;">KPIs & Tableaux COPIL</div>
                <div style="color:#64748b;font-size:12px;line-height:1.5;">Générez automatiquement vos indicateurs de performance.</div>
              </td>
              <td width="4%"></td>
              <td width="48%" style="background:rgba(55,138,221,0.08);border:1px solid rgba(55,138,221,0.15);border-radius:10px;padding:16px;vertical-align:top;">
                <div style="color:#378ADD;font-size:18px;margin-bottom:8px;">💬</div>
                <div style="color:#ffffff;font-weight:600;font-size:14px;margin-bottom:4px;">Assistant IA</div>
                <div style="color:#64748b;font-size:12px;line-height:1.5;">Posez vos questions directement à l'IA sur vos projets.</div>
              </td>
            </tr>
          </table>
        </td></tr>
        <!-- CTA -->
        <tr><td style="padding:8px 40px 40px;text-align:center;">
          <a href="{login_url}" style="display:inline-block;background:#378ADD;color:#ffffff;text-decoration:none;padding:14px 40px;border-radius:8px;font-weight:600;font-size:15px;">
            Accéder à PilotIA
          </a>
        </td></tr>
        <!-- Footer -->
        <tr><td style="padding:24px 40px;border-top:1px solid rgba(55,138,221,0.1);text-align:center;">
          <p style="color:#475569;font-size:12px;margin:0;">© 2025 PilotIA · <a href="{settings.FRONTEND_URL}" style="color:#378ADD;text-decoration:none;">pilotia.app</a></p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    msg = _base_msg(to_email, "Bienvenue sur PilotIA 🚀")
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    _send(msg)


# ── Email de vérification de l'adresse email ───────────────────────────────────
def send_verification_email(to_email: str, first_name: str, token: str) -> None:
    """Envoie un email de confirmation d'adresse email."""
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    name = first_name or "cher utilisateur"

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"[WARNING] SMTP non configuré. Lien de vérification: {verify_url}")
        return

    text = f"""Bonjour {name},

Merci de vous être inscrit sur PilotIA !
Veuillez confirmer votre adresse email en cliquant sur le lien ci-dessous :

{verify_url}

Ce lien est valable 48 heures.
Si vous n'avez pas créé de compte, ignorez cet email.

L'équipe PilotIA"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f0f1a;font-family:'Inter',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f1a;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#1a1a2e;border-radius:16px;overflow:hidden;border:1px solid rgba(55,138,221,0.2);">
        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#1e3a5f,#0d1f3c);padding:32px 40px;text-align:center;">
          <div style="font-size:28px;font-weight:700;color:#378ADD;letter-spacing:-0.5px;">Pilot<span style="color:#ffffff;">IA</span></div>
          <div style="color:#94a3b8;font-size:13px;margin-top:4px;">Intelligence Artificielle pour le PMO</div>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:40px;">
          <div style="text-align:center;margin-bottom:28px;">
            <div style="display:inline-block;background:rgba(55,138,221,0.12);border:1px solid rgba(55,138,221,0.3);border-radius:50%;width:64px;height:64px;line-height:64px;font-size:28px;">✉️</div>
          </div>
          <h2 style="color:#ffffff;font-size:20px;margin:0 0 12px;text-align:center;">Confirmez votre adresse email</h2>
          <p style="color:#94a3b8;line-height:1.7;margin:0 0 28px;text-align:center;">
            Bonjour <strong style="color:#ffffff;">{name}</strong>, cliquez sur le bouton ci-dessous
            pour confirmer votre adresse email et activer votre compte PilotIA.
          </p>
          <div style="text-align:center;margin:0 0 32px;">
            <a href="{verify_url}" style="display:inline-block;background:#378ADD;color:#ffffff;text-decoration:none;padding:14px 40px;border-radius:8px;font-weight:600;font-size:15px;">
              Confirmer mon email
            </a>
          </div>
          <div style="background:rgba(55,138,221,0.06);border:1px solid rgba(55,138,221,0.12);border-radius:8px;padding:16px;">
            <p style="color:#64748b;font-size:12px;margin:0;line-height:1.6;">
              🔒 Ce lien est valable <strong style="color:#94a3b8;">48 heures</strong>.<br>
              Si vous n'avez pas créé de compte sur PilotIA, ignorez cet email.
            </p>
          </div>
        </td></tr>
        <!-- Footer -->
        <tr><td style="padding:24px 40px;border-top:1px solid rgba(55,138,221,0.1);text-align:center;">
          <p style="color:#475569;font-size:12px;margin:0;">© 2025 PilotIA · <a href="{settings.FRONTEND_URL}" style="color:#378ADD;text-decoration:none;">pilotia.app</a></p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    msg = _base_msg(to_email, "Confirmez votre adresse email - PilotIA")
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    _send(msg)
