from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from auditlog.registry import auditlog


class UserManager(BaseUserManager):

    def create_user(self, phone, password=None, **extra):
        if not phone:
            raise ValueError("Le numéro de téléphone est obligatoire.")
        user = self.model(phone=phone, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password, **extra):
        extra.setdefault("is_staff",     True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role",         User.Role.ADMIN)
        extra.setdefault("status",       User.Status.ACTIVE)
        extra.setdefault("phone_verified", True)
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):

    class Role(models.TextChoices):
        STUDENT = "student", _("Élève")
        PARENT  = "parent",  _("Parent")
        TUTOR   = "tutor",   _("Répétiteur")
        VENDOR  = "vendor",  _("Vendeur")
        SCHOOL  = "school",  _("École")
        ADMIN   = "admin",   _("Administrateur")

    class Status(models.TextChoices):
        PENDING   = "pending",   _("En attente")
        ACTIVE    = "active",    _("Actif")
        SUSPENDED = "suspended", _("Suspendu")
        BANNED    = "banned",    _("Banni")

    phone    = PhoneNumberField(unique=True, db_index=True, verbose_name=_("Téléphone"))
    email    = models.EmailField(blank=True, null=True)

    first_name   = models.CharField(max_length=100, verbose_name=_("Prénom"))
    last_name    = models.CharField(max_length=100, verbose_name=_("Nom"))
    display_name = models.CharField(max_length=200, blank=True)
    avatar       = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio          = models.TextField(blank=True)

    role   = models.CharField(max_length=20, choices=Role.choices,   default=Role.STUDENT, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    suspension_reason = models.TextField(blank=True)

    points = models.PositiveIntegerField(default=0)
    city   = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)

    phone_verified = models.BooleanField(default=False)
    firebase_uid   = models.CharField(max_length=128, blank=True, db_index=True)

    is_staff  = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    date_joined = models.DateTimeField(default=timezone.now)
    last_login  = models.DateTimeField(null=True, blank=True)
    last_active = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD  = "phone"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        verbose_name        = _("Utilisateur")
        verbose_name_plural = _("Utilisateurs")
        ordering            = ["-date_joined"]
        indexes = [
            models.Index(fields=["role", "status"]),
            models.Index(fields=["last_active"]),
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.phone})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or str(self.phone)

    def get_short_name(self):
        return self.first_name

    @property
    def is_vendor(self):  return self.role == self.Role.VENDOR
    @property
    def is_tutor(self):   return self.role == self.Role.TUTOR
    @property
    def is_admin_role(self): return self.role == self.Role.ADMIN

    def credit_points(self, amount: int, reason: str = ""):
        User.objects.filter(pk=self.pk).update(points=models.F("points") + amount)
        self.refresh_from_db(fields=["points"])
        PointsHistory.objects.create(user=self, amount=amount, reason=reason)

    def suspend(self, reason: str):
        self.status = self.Status.SUSPENDED
        self.suspension_reason = reason
        self.save(update_fields=["status", "suspension_reason"])
        from kharandi.services.sms import send_sms, sms_account_suspended, normalize_phone
        send_sms(normalize_phone(str(self.phone)), sms_account_suspended(reason))


class TutorProfile(models.Model):
    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name="tutor_profile")
    subjects     = models.CharField(max_length=500, blank=True, verbose_name=_("Matières"))
    levels       = models.CharField(max_length=200, blank=True, verbose_name=_("Niveaux"))
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_kyc_verified = models.BooleanField(default=False)
    kyc_document  = models.FileField(upload_to="kyc/tutors/", blank=True, null=True)
    avg_rating    = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_students = models.PositiveIntegerField(default=0)
    description   = models.TextField(blank=True, verbose_name=_("Présentation"))

    class Meta:
        verbose_name        = _("Profil Répétiteur")
        verbose_name_plural = _("Profils Répétiteurs")

    def __str__(self): return f"Profil répétiteur — {self.user}"


class VendorProfile(models.Model):

    class KYCStatus(models.TextChoices):
        PENDING  = "pending",  _("En attente")
        APPROVED = "approved", _("Approuvé")
        REJECTED = "rejected", _("Rejeté")

    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name="vendor_profile")
    shop_name    = models.CharField(max_length=200, verbose_name=_("Boutique"))
    shop_logo    = models.ImageField(upload_to="shops/", blank=True, null=True)
    shop_address = models.TextField(blank=True)
    kyc_status   = models.CharField(max_length=20, choices=KYCStatus.choices, default=KYCStatus.PENDING)
    kyc_document = models.FileField(upload_to="kyc/vendors/", blank=True, null=True)
    total_sales  = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    avg_rating   = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    is_featured  = models.BooleanField(default=False)
    commission_override = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _("Profil Vendeur")
        verbose_name_plural = _("Profils Vendeurs")

    def __str__(self): return f"{self.shop_name} ({self.user.phone})"


class OTPCode(models.Model):
    phone      = models.CharField(max_length=20, db_index=True)
    code       = models.CharField(max_length=6)
    purpose    = models.CharField(max_length=30, default="verification")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used    = models.BooleanField(default=False)

    class Meta:
        verbose_name        = _("Code OTP")
        verbose_name_plural = _("Codes OTP")
        indexes = [models.Index(fields=["phone", "is_used"])]

    def __str__(self): return f"OTP {self.phone} ({self.purpose})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @classmethod
    def cleanup_expired(cls):
        deleted, _ = cls.objects.filter(expires_at__lt=timezone.now()).delete()
        return deleted


class PointsHistory(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="points_history")
    amount     = models.IntegerField()
    reason     = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name        = _("Historique Points")
        verbose_name_plural = _("Historique Points")


auditlog.register(User, exclude_fields=["password", "last_login"])
auditlog.register(VendorProfile)
auditlog.register(TutorProfile)
