"""
╔══════════════════════════════════════════════════════════════════════════╗
║           KHARANDI — Notifications : Endpoints SMS                      ║
║  Appels NimbaSMS directs et synchrones (sans Celery)                    ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from kharandi.services.sms import (
    send_sms, normalize_phone, get_sms_balance,
    sms_welcome, sms_order_confirmation, sms_order_shipped,
    sms_order_delivered, sms_points_credit, sms_new_message,
    sms_course_reminder, sms_annonce_validated, sms_account_suspended,
    sms_otp_reset, sms_new_student, sms_custom,
)
from kharandi.apps.accounts.views import generate_otp


def _ok(msg="SMS envoyé."):
    return Response({"success": True, "message": msg})

def _err(msg, code=400):
    return Response({"success": False, "message": msg}, status=code)

def _require_admin(request):
    return request.user.is_staff or request.user.role == "admin"


class WelcomeSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        phone = normalize_phone(request.data.get("phone", ""))
        name  = request.data.get("name", "Utilisateur")
        if not phone: return _err("Champ 'phone' requis.")
        ok = send_sms(phone, sms_welcome(name))
        return _ok() if ok else _err("Échec d'envoi SMS.", 502)


class OrderConfirmationSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        phone    = normalize_phone(request.data.get("phone", ""))
        order_id = request.data.get("order_id", "")
        total    = request.data.get("total", 0)
        if not phone or not order_id: return _err("Champs 'phone' et 'order_id' requis.")
        ok = send_sms(phone, sms_order_confirmation(str(order_id), int(total)))
        return _ok() if ok else _err("Échec.", 502)


class OrderShippedSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        phone    = normalize_phone(request.data.get("phone", ""))
        order_id = request.data.get("order_id", "")
        if not phone or not order_id: return _err("Champs requis.")
        ok = send_sms(phone, sms_order_shipped(str(order_id)))
        return _ok() if ok else _err("Échec.", 502)


class OrderDeliveredSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        phone    = normalize_phone(request.data.get("phone", ""))
        order_id = request.data.get("order_id", "")
        if not phone or not order_id: return _err("Champs requis.")
        ok = send_sms(phone, sms_order_delivered(str(order_id)))
        return _ok() if ok else _err("Échec.", 502)


class PointsSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        phone  = normalize_phone(request.data.get("phone", ""))
        name   = request.data.get("name", "")
        added  = request.data.get("points_added", 0)
        total  = request.data.get("total_points", 0)
        if not phone: return _err("Champ 'phone' requis.")
        ok = send_sms(phone, sms_points_credit(name, int(added), int(total)))
        return _ok() if ok else _err("Échec.", 502)


class NewMessageSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        phone  = normalize_phone(request.data.get("phone", ""))
        sender = request.data.get("sender_name", "un utilisateur")
        if not phone: return _err("Champ 'phone' requis.")
        ok = send_sms(phone, sms_new_message(sender))
        return _ok() if ok else _err("Échec.", 502)


class CourseReminderSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        phone  = normalize_phone(request.data.get("phone", ""))
        course = request.data.get("course_title", "votre cours")
        if not phone: return _err("Champ 'phone' requis.")
        ok = send_sms(phone, sms_course_reminder(course))
        return _ok() if ok else _err("Échec.", 502)


class AnnonceValidatedSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        phone   = normalize_phone(request.data.get("phone", ""))
        product = request.data.get("product_name", "votre produit")
        if not phone: return _err("Champ 'phone' requis.")
        ok = send_sms(phone, sms_annonce_validated(product))
        return _ok() if ok else _err("Échec.", 502)


class AccountSuspendedSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        if not _require_admin(request): return _err("Accès réservé aux admins.", 403)
        phone  = normalize_phone(request.data.get("phone", ""))
        reason = request.data.get("reason", "violation des conditions")
        if not phone: return _err("Champ 'phone' requis.")
        ok = send_sms(phone, sms_account_suspended(reason))
        return _ok() if ok else _err("Échec.", 502)


class PasswordResetSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        phone = normalize_phone(request.data.get("phone", ""))
        if not phone: return _err("Champ 'phone' requis.")
        code = generate_otp(6)
        ok   = send_sms(phone, sms_otp_reset(code))
        if ok:
            return Response({"success": True, "message": "SMS envoyé.", "data": {"reset_code": code}})
        return _err("Échec.", 502)


class NewStudentSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        phone   = normalize_phone(request.data.get("phone", ""))
        student = request.data.get("student_name", "Un élève")
        course  = request.data.get("course_title", "votre cours")
        if not phone: return _err("Champ 'phone' requis.")
        ok = send_sms(phone, sms_new_student(student, course))
        return _ok() if ok else _err("Échec.", 502)


class BulkSMSView(APIView):
    """Broadcast admin — max 500 numéros."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _require_admin(request): return _err("Accès réservé aux admins.", 403)
        phones  = request.data.get("phones", [])
        message = request.data.get("message", "").strip()
        if not phones or not message: return _err("Champs 'phones' et 'message' requis.")
        if len(phones) > 500: return _err("Maximum 500 numéros par envoi.")

        sent   = 0
        failed = 0
        failed_numbers = []

        for raw in phones:
            phone = normalize_phone(str(raw))
            ok    = send_sms(phone, sms_custom(message))
            if ok: sent += 1
            else:
                failed += 1
                failed_numbers.append(phone)

        return Response({
            "success": True,
            "message": f"{sent} SMS envoyés, {failed} échecs.",
            "data":    {"sent": sent, "failed": failed, "failed_numbers": failed_numbers},
        })


class CustomSMSView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        if not _require_admin(request): return _err("Accès réservé aux admins.", 403)
        phone   = normalize_phone(request.data.get("phone", ""))
        message = request.data.get("message", "").strip()
        if not phone or not message: return _err("Champs 'phone' et 'message' requis.")
        ok = send_sms(phone, sms_custom(message))
        return _ok() if ok else _err("Échec.", 502)


class SMSBalanceView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if not _require_admin(request): return _err("Accès réservé aux admins.", 403)
        result = get_sms_balance()
        return Response({"success": result["success"], "data": result})
