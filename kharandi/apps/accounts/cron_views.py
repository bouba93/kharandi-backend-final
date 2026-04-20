"""
Vues appelées par des crons HTTP externes (ex: cron-job.org — gratuit).
Ces endpoints remplacent Celery Beat sur Render plan gratuit.
Sécurisés par un token secret dans le header ou query param.
"""
import os
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny


CRON_SECRET = os.environ.get("CRON_SECRET", "")


def _check_cron_auth(request) -> bool:
    """Vérifie que la requête provient d'un cron autorisé."""
    if not CRON_SECRET:
        return True  # En dev sans secret, laisser passer
    token = request.headers.get("X-Cron-Secret") or request.query_params.get("secret", "")
    return token == CRON_SECRET


class CronInactivityView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not _check_cron_auth(request):
            return Response({"error": "Non autorisé."}, status=403)

        from django.utils import timezone
        from datetime import timedelta
        from django.contrib.auth import get_user_model
        from kharandi.services.sms import send_sms, normalize_phone, sms_inactivity

        User   = get_user_model()
        cutoff = timezone.now() - timedelta(days=7)
        inactive = User.objects.filter(
            last_active__lt=cutoff, status="active", phone_verified=True
        ).exclude(role="admin")[:200]  # Limiter à 200/appel sur plan gratuit

        sent = 0
        for user in inactive:
            days = (timezone.now() - user.last_active).days
            ok   = send_sms(normalize_phone(str(user.phone)), sms_inactivity(user.first_name, days))
            if ok:
                sent += 1

        return Response({"success": True, "sent": sent, "total_inactive": inactive.count()})


class CronCleanupOTPView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not _check_cron_auth(request):
            return Response({"error": "Non autorisé."}, status=403)

        from kharandi.apps.accounts.models import OTPCode
        n = OTPCode.cleanup_expired()
        return Response({"success": True, "deleted": n})
