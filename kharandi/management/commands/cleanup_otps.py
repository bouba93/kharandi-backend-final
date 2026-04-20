"""
Commande Django pour nettoyer les OTP expirés.
Sur Render gratuit : lancer via un cron HTTP ou manuellement.
Usage : python manage.py cleanup_otps
"""
from django.core.management.base import BaseCommand
from kharandi.apps.accounts.models import OTPCode


class Command(BaseCommand):
    help = "Supprime les codes OTP expirés de la base de données."

    def handle(self, *args, **kwargs):
        n = OTPCode.cleanup_expired()
        self.stdout.write(self.style.SUCCESS(f"✅ {n} OTP expirés supprimés."))
