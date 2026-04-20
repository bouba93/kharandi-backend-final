"""
╔══════════════════════════════════════════════════════════════════════════╗
║           KHARANDI — Accounts Views                                     ║
║  OTP synchrone via NimbaSMS direct (sans Celery, sans Redis)            ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import random
import string
from datetime import timedelta

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPCode, TutorProfile, VendorProfile
from .serializers import (
    UserRegistrationSerializer, UserProfileSerializer,
    OTPSendSerializer, OTPVerifySerializer,
    TutorProfileSerializer, VendorProfileSerializer,
)
from kharandi.services.sms import (
    send_sms, normalize_phone,
    sms_otp, sms_otp_reset, sms_welcome,
)

User = get_user_model()


# ══════════════════════════════════════════════════════════════════════════
#  THROTTLES
# ══════════════════════════════════════════════════════════════════════════

class OTPThrottle(AnonRateThrottle):
    scope = "otp"


# ══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════

def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


# ══════════════════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════

class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from django.db import connection
        db_ok = True
        try:
            connection.ensure_connection()
        except Exception:
            db_ok = False

        return Response({
            "success": True,
            "message": "Kharandi Backend Django v1.0 🚀",
            "data": {
                "version":  "1.0.0",
                "database": "UP" if db_ok else "DOWN",
                "sms":      "NimbaSMS (direct)",
                "services": ["Auth JWT", "OTP NimbaSMS", "LengoPay",
                             "Marketplace", "Courses", "IA Karamö",
                             "Reports PDF/Excel", "Support Tickets"],
                "timestamp": timezone.now().isoformat(),
            }
        })


# ══════════════════════════════════════════════════════════════════════════
#  INSCRIPTION
# ══════════════════════════════════════════════════════════════════════════

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        # SMS synchrone bienvenue
        phone = normalize_phone(str(user.phone))
        send_sms(phone, sms_welcome(user.first_name))

        return Response({
            "success": True,
            "message": "Compte créé avec succès.",
            "data": {
                "user":          UserProfileSerializer(user).data,
                "access_token":  str(refresh.access_token),
                "refresh_token": str(refresh),
            }
        }, status=status.HTTP_201_CREATED)


# ══════════════════════════════════════════════════════════════════════════
#  CONNEXION
# ══════════════════════════════════════════════════════════════════════════

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        phone_raw = request.data.get("phone", "").strip()
        password  = request.data.get("password", "")

        if not phone_raw or not password:
            return Response(
                {"success": False, "message": "Téléphone et mot de passe requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        phone = normalize_phone(phone_raw)

        try:
            user = User.objects.get(phone__contains=phone[-9:])  # Tolérance format
        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "Identifiants incorrects."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except User.MultipleObjectsReturned:
            return Response(
                {"success": False, "message": "Erreur compte — contactez le support."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(password):
            return Response(
                {"success": False, "message": "Identifiants incorrects."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if user.status == User.Status.SUSPENDED:
            return Response(
                {"success": False, "message": f"Compte suspendu : {user.suspension_reason}"},
                status=status.HTTP_403_FORBIDDEN
            )
        if user.status == User.Status.BANNED:
            return Response(
                {"success": False, "message": "Compte banni définitivement."},
                status=status.HTTP_403_FORBIDDEN
            )

        User.objects.filter(pk=user.pk).update(
            last_login=timezone.now(),
            last_active=timezone.now()
        )

        refresh = RefreshToken.for_user(user)
        return Response({
            "success": True,
            "message": "Connexion réussie.",
            "data": {
                "user":          UserProfileSerializer(user).data,
                "access_token":  str(refresh.access_token),
                "refresh_token": str(refresh),
            }
        })


# ══════════════════════════════════════════════════════════════════════════
#  OTP — ENVOI
# ══════════════════════════════════════════════════════════════════════════

class OTPSendView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [OTPThrottle]

    def post(self, request):
        serializer = OTPSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone   = normalize_phone(serializer.validated_data["phone"])
        purpose = serializer.validated_data.get("purpose", "verification")

        # Anti-spam : 1 OTP / 60 secondes par numéro (cache DB)
        cooldown_key = f"otp_cd_{phone}"
        if cache.get(cooldown_key):
            return Response(
                {"success": False, "message": "Un OTP a déjà été envoyé. Attendez 1 minute."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Invalider les anciens OTP non utilisés
        OTPCode.objects.filter(phone=phone, purpose=purpose, is_used=False).update(is_used=True)

        # Créer le nouvel OTP
        code = generate_otp()
        OTPCode.objects.create(
            phone=phone,
            code=code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        # Cooldown 60 secondes
        cache.set(cooldown_key, True, timeout=60)

        # Envoi SMS direct NimbaSMS (synchrone)
        msg = sms_otp_reset(code) if purpose == "password_reset" else sms_otp(code)
        ok  = send_sms(phone, msg)

        if not ok:
            # Annuler le code si le SMS échoue
            OTPCode.objects.filter(phone=phone, code=code).update(is_used=True)
            cache.delete(cooldown_key)
            return Response(
                {"success": False, "message": "Échec d'envoi SMS. Réessayez dans quelques secondes."},
                status=status.HTTP_502_BAD_GATEWAY
            )

        return Response({
            "success": True,
            "message": "Code OTP envoyé par SMS.",
            "data": {"phone": phone}
        })


# ══════════════════════════════════════════════════════════════════════════
#  OTP — VÉRIFICATION
# ══════════════════════════════════════════════════════════════════════════

class OTPVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone   = normalize_phone(serializer.validated_data["phone"])
        code    = serializer.validated_data["code"]
        purpose = serializer.validated_data.get("purpose", "verification")

        otp = OTPCode.objects.filter(
            phone=phone, purpose=purpose, is_used=False
        ).order_by("-created_at").first()

        if not otp:
            return Response(
                {"success": False, "message": "Aucun OTP trouvé. Demandez-en un nouveau."},
                status=status.HTTP_404_NOT_FOUND
            )
        if otp.is_expired:
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            return Response(
                {"success": False, "message": "OTP expiré. Demandez-en un nouveau."},
                status=status.HTTP_410_GONE
            )
        if otp.code != code:
            return Response(
                {"success": False, "message": "Code incorrect."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Usage unique
        otp.is_used = True
        otp.save(update_fields=["is_used"])

        # Activer le compte si c'est une vérification
        if purpose == "verification":
            User.objects.filter(phone=phone).update(
                phone_verified=True,
                status=User.Status.ACTIVE,
            )

        return Response({
            "success": True,
            "message": "Code vérifié avec succès.",
            "data": {"phone": phone, "verified": True}
        })


# ══════════════════════════════════════════════════════════════════════════
#  OTP — RENVOI
# ══════════════════════════════════════════════════════════════════════════

class OTPResendView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [OTPThrottle]

    def post(self, request):
        phone   = normalize_phone(request.data.get("phone", ""))
        purpose = request.data.get("purpose", "verification")
        # Supprimer le cooldown pour autoriser le renvoi
        cache.delete(f"otp_cd_{phone}")
        # Déléguer à OTPSendView
        from rest_framework.request import Request as DRFRequest
        new_data = request.data.copy()
        new_data["purpose"] = purpose
        new_data["phone"]   = phone
        inner = OTPSendView()
        inner.request = request
        inner.format_kwarg = None
        return inner.post(request)


# ══════════════════════════════════════════════════════════════════════════
#  MOT DE PASSE — RESET
# ══════════════════════════════════════════════════════════════════════════

class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        phone = normalize_phone(request.data.get("phone", ""))
        # Réponse générique (ne pas révéler si le numéro existe)
        if User.objects.filter(phone__contains=phone[-9:]).exists():
            code = generate_otp()
            OTPCode.objects.filter(
                phone=phone, purpose="password_reset", is_used=False
            ).update(is_used=True)
            OTPCode.objects.create(
                phone=phone,
                code=code,
                purpose="password_reset",
                expires_at=timezone.now() + timedelta(minutes=15),
            )
            from kharandi.services.sms import sms_otp_reset
            send_sms(phone, sms_otp_reset(code))

        return Response({
            "success": True,
            "message": "Si ce numéro est enregistré, un SMS a été envoyé."
        })


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        phone        = normalize_phone(request.data.get("phone", ""))
        code         = request.data.get("code", "").strip()
        new_password = request.data.get("new_password", "")

        if len(new_password) < 8:
            return Response(
                {"success": False, "message": "Mot de passe minimum 8 caractères."},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp = OTPCode.objects.filter(
            phone=phone, purpose="password_reset", is_used=False
        ).order_by("-created_at").first()

        if not otp or otp.is_expired or otp.code != code:
            return Response(
                {"success": False, "message": "Code invalide ou expiré."},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        try:
            user = User.objects.get(phone__contains=phone[-9:])
            user.set_password(new_password)
            user.save(update_fields=["password"])
        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "Utilisateur introuvable."},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({"success": True, "message": "Mot de passe modifié avec succès."})


# ══════════════════════════════════════════════════════════════════════════
#  PROFIL
# ══════════════════════════════════════════════════════════════════════════

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        return Response({"success": True, "data": self.get_serializer(self.get_object()).data})

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        resp = super().update(request, *args, **kwargs)
        return Response({"success": True, "message": "Profil mis à jour.", "data": resp.data})


class TutorProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = TutorProfileSerializer

    def get_object(self):
        profile, _ = TutorProfile.objects.get_or_create(user=self.request.user)
        return profile

    def retrieve(self, request, *args, **kwargs):
        return Response({"success": True, "data": self.get_serializer(self.get_object()).data})

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        resp = super().update(request, *args, **kwargs)
        return Response({"success": True, "data": resp.data})


class VendorProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = VendorProfileSerializer

    def get_object(self):
        profile, _ = VendorProfile.objects.get_or_create(
            user=self.request.user,
            defaults={"shop_name": self.request.user.get_full_name()}
        )
        return profile

    def retrieve(self, request, *args, **kwargs):
        return Response({"success": True, "data": self.get_serializer(self.get_object()).data})

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        resp = super().update(request, *args, **kwargs)
        return Response({"success": True, "data": resp.data})


# ══════════════════════════════════════════════════════════════════════════
#  DÉCONNEXION
# ══════════════════════════════════════════════════════════════════════════

class LogoutView(APIView):

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh_token", ""))
            token.blacklist()
        except Exception:
            pass
        return Response({"success": True, "message": "Déconnecté avec succès."})


# ══════════════════════════════════════════════════════════════════════════
#  LISTE PUBLIQUE RÉPÉTITEURS
# ══════════════════════════════════════════════════════════════════════════

class TutorListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from django.db.models import Q
        qs = User.objects.filter(
            role=User.Role.TUTOR,
            status=User.Status.ACTIVE,
            tutor_profile__is_kyc_verified=True,
        ).select_related("tutor_profile")

        subject = request.query_params.get("subject", "")
        level   = request.query_params.get("level", "")
        city    = request.query_params.get("city", "")

        if subject:
            qs = qs.filter(tutor_profile__subjects__icontains=subject)
        if level:
            qs = qs.filter(tutor_profile__levels__icontains=level)
        if city:
            qs = qs.filter(city__icontains=city)

        data = []
        for u in qs[:50]:
            tp = u.tutor_profile
            data.append({
                "id":           u.id,
                "name":         u.get_full_name(),
                "city":         u.city,
                "subjects":     tp.subjects,
                "levels":       tp.levels,
                "price_per_hour": str(tp.price_per_hour or 0),
                "avg_rating":   str(tp.avg_rating),
                "total_students": tp.total_students,
                "description":  tp.description,
            })

        return Response({"success": True, "data": data})
