"""
Commande Django pour envoyer des rappels aux utilisateurs inactifs.
Sur Render gratuit : appeler via un cron job externe (ex: cron-job.org gratuit).
Appeler l'endpoint GET /api/admin/cron/inactivity/ depuis un cron externe.
Usage : python manage.py send_inactivity_reminders
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = "Envoie des SMS de rappel aux utilisateurs inactifs depuis 7+ jours."

    def handle(self, *args, **kwargs):
        from django.contrib.auth import get_user_model
        from kharandi.services.sms import send_sms, normalize_phone, sms_inactivity

        User   = get_user_model()
        cutoff = timezone.now() - timedelta(days=7)

        inactive = User.objects.filter(
            last_active__lt=cutoff,
            status="active",
            phone_verified=True,
        ).exclude(role="admin")

        sent = 0
        for user in inactive:
            days = (timezone.now() - user.last_active).days
            ok   = send_sms(
                normalize_phone(str(user.phone)),
                sms_inactivity(user.first_name, days)
            )
            if ok:
                sent += 1

        self.stdout.write(self.style.SUCCESS(f"✅ {sent} rappels SMS envoyés sur {inactive.count()} inactifs."))
