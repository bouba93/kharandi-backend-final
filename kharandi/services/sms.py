"""
╔══════════════════════════════════════════════════════════════════════════╗
║         KHARANDI — Service NimbaSMS (sans Celery)                       ║
║                                                                          ║
║  Tous les SMS sont envoyés de façon synchrone directement               ║
║  depuis les vues. Retry simple sur erreur réseau.                        ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import logging
import time

from django.conf import settings

logger = logging.getLogger("kharandi")

SMS_MAX  = 160
MAX_RETRY = 2
RETRY_DELAY = 2  # secondes


def _get_client():
    from nimbasms import Client
    return Client(settings.NIMBA_SID, settings.NIMBA_TOKEN)


def _truncate(msg: str) -> str:
    return msg[:SMS_MAX]


# ══════════════════════════════════════════════════════════════════════════
#  FONCTION D'ENVOI DE BASE
# ══════════════════════════════════════════════════════════════════════════

def send_sms(phone: str, message: str, retry: int = MAX_RETRY) -> bool:
    """
    Envoie un SMS via NimbaSMS avec retry simple.
    Retourne True si succès, False sinon.
    """
    if not settings.NIMBA_SID or not settings.NIMBA_TOKEN:
        logger.warning(f"NimbaSMS non configuré — SMS simulé → {phone}: {message[:50]}...")
        return True  # Ne pas bloquer en dev si Nimba non configuré

    message = _truncate(message)

    for attempt in range(retry + 1):
        try:
            nimba = _get_client()
            resp  = nimba.messages.create(
                to=[phone],
                sender_name=settings.NIMBA_SENDER_NAME,
                message=message,
            )
            if resp.ok:
                logger.info(f"📱 SMS → {phone} [OK]")
                return True
            logger.error(f"NimbaSMS erreur → {phone}: {resp.data}")
            if attempt < retry:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            logger.exception(f"NimbaSMS exception → {phone} (tentative {attempt+1}): {e}")
            if attempt < retry:
                time.sleep(RETRY_DELAY)

    logger.error(f"❌ SMS échoué après {retry+1} tentatives → {phone}")
    return False


# ══════════════════════════════════════════════════════════════════════════
#  HELPERS NORMALISATION
# ══════════════════════════════════════════════════════════════════════════

def normalize_phone(phone: str) -> str:
    """Normalise au format guinéen : 224XXXXXXXXX"""
    phone = str(phone).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if not phone.startswith("224") and len(phone) <= 9:
        phone = "224" + phone
    return phone


# ══════════════════════════════════════════════════════════════════════════
#  TEMPLATES SMS
# ══════════════════════════════════════════════════════════════════════════

def sms_otp(code: str) -> str:
    return f"[Kharandi] Code verification : {code}. Valable 5min. Ne le partagez pas."

def sms_otp_reset(code: str) -> str:
    return f"[Kharandi] Code reinitialisation : {code}. Valable 15min. Si pas vous, ignorez."

def sms_welcome(name: str) -> str:
    return f"Bienvenue sur Kharandi {name[:20]} ! Compte pret. kharandi.com"

def sms_order_confirmation(order_id: str, total: int) -> str:
    return _truncate(f"[Kharandi] Commande #{order_id} confirmee ! {total:,} GNF. kharandi.com/orders")

def sms_order_shipped(order_id: str) -> str:
    return f"[Kharandi] Commande #{order_id} expediee. Votre vendeur vous contactera."

def sms_order_delivered(order_id: str) -> str:
    return f"[Kharandi] Commande #{order_id} livree. Merci de votre confiance !"

def sms_payment_success(amount: int) -> str:
    return f"[Kharandi] Paiement {amount:,} GNF recu. Merci pour votre achat !"

def sms_payment_failed(amount: int) -> str:
    return f"[Kharandi] Paiement {amount:,} GNF echoue. Reessayez : kharandi.com"

def sms_points_credit(name: str, points: int, total: int) -> str:
    return _truncate(f"[Kharandi] {name[:15]}, +{points} pts credites ! Solde: {total} pts.")

def sms_new_message(sender: str) -> str:
    return f"[Kharandi] Nouveau message de {sender[:20]}. kharandi.com"

def sms_course_reminder(course: str) -> str:
    return _truncate(f"[Kharandi] Continuez '{course[:30]}'. kharandi.com/courses")

def sms_annonce_validated(product: str) -> str:
    return _truncate(f"[Kharandi] Annonce '{product[:35]}' validee et visible !")

def sms_annonce_rejected(product: str, reason: str) -> str:
    return _truncate(f"[Kharandi] Annonce '{product[:20]}' rejetee. Raison: {reason[:40]}")

def sms_account_suspended(reason: str) -> str:
    return f"[Kharandi] Compte suspendu. {reason[:60]}. Contact: support@kharandi.com"

def sms_new_student(student: str, course: str) -> str:
    return _truncate(f"[Kharandi] {student[:15]} inscrit a '{course[:30]}'. kharandi.com")

def sms_new_review(rating: int, product: str) -> str:
    return _truncate(f"[Kharandi] Nouvel avis {rating}★ sur '{product[:30]}'. kharandi.com")

def sms_ticket_reply(ticket_number: str) -> str:
    return f"[Kharandi] Reponse sur votre ticket #{ticket_number}. kharandi.com/support"

def sms_kyc_approved(role: str) -> str:
    role_label = "vendeur" if role == "vendor" else "repetiteur"
    return f"[Kharandi] Votre compte {role_label} est valide ! Vous pouvez publier. kharandi.com"

def sms_inactivity(name: str, days: int) -> str:
    return _truncate(f"[Kharandi] {name[:15]}, {days}j sans connexion. Nouveaux cours ! kharandi.com")

def sms_custom(message: str) -> str:
    return _truncate(message)


# ══════════════════════════════════════════════════════════════════════════
#  VÉRIFICATION SOLDE
# ══════════════════════════════════════════════════════════════════════════

def get_sms_balance() -> dict:
    """Retourne le solde NimbaSMS."""
    try:
        nimba = _get_client()
        resp  = nimba.accounts.get()
        if resp.ok:
            return {"success": True, "balance": resp.data.get("balance")}
        return {"success": False, "error": str(resp.data)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def sms_inactivity(name: str, days: int) -> str:
    return _truncate(f"[Kharandi] {name[:15]}, {days}j sans connexion. Nouveaux cours ! kharandi.com")
