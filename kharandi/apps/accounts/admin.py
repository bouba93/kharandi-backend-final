from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline
from .models import User, TutorProfile, VendorProfile, OTPCode, PointsHistory


class TutorProfileInline(TabularInline):
    model  = TutorProfile
    extra  = 0
    fields = ["subjects", "levels", "price_per_hour", "is_kyc_verified", "avg_rating"]
    readonly_fields = ["avg_rating", "total_students"]


class VendorProfileInline(TabularInline):
    model  = VendorProfile
    extra  = 0
    fields = ["shop_name", "kyc_status", "total_sales", "is_featured"]
    readonly_fields = ["total_sales", "avg_rating"]


@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display    = ["phone", "get_full_name", "role", "status", "points", "city", "date_joined"]
    list_filter     = ["role", "status", "phone_verified", "city"]
    search_fields   = ["phone", "first_name", "last_name", "email"]
    ordering        = ["-date_joined"]
    readonly_fields = ["date_joined", "last_login", "last_active"]
    inlines         = [TutorProfileInline, VendorProfileInline]
    fieldsets = (
        (_("Identification"), {"fields": ("phone", "email", "password")}),
        (_("Profil"), {"fields": ("first_name", "last_name", "display_name", "avatar", "bio", "city", "district")}),
        (_("Rôle & Statut"), {"fields": ("role", "status", "suspension_reason", "phone_verified")}),
        (_("Gamification"), {"fields": ("points",)}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser"), "classes": ("collapse",)}),
        (_("Dates"), {"fields": ("date_joined", "last_login", "last_active"), "classes": ("collapse",)}),
    )
    actions = ["activate_users", "suspend_users", "verify_phones", "approve_tutor_kyc", "approve_vendor_kyc"]

    @admin.action(description="✅ Activer les comptes")
    def activate_users(self, request, queryset):
        queryset.update(status=User.Status.ACTIVE)
        self.message_user(request, f"{queryset.count()} compte(s) activé(s).")

    @admin.action(description="🚫 Suspendre les comptes")
    def suspend_users(self, request, queryset):
        for u in queryset.exclude(role="admin"):
            u.suspend("Suspendu par un administrateur")
        self.message_user(request, f"{queryset.count()} compte(s) suspendu(s).")

    @admin.action(description="📱 Marquer téléphones vérifiés")
    def verify_phones(self, request, queryset):
        queryset.update(phone_verified=True)
        self.message_user(request, f"{queryset.count()} téléphone(s) vérifié(s).")

    @admin.action(description="🎓 Valider KYC répétiteurs")
    def approve_tutor_kyc(self, request, queryset):
        from kharandi.services.sms import send_sms, normalize_phone, sms_kyc_approved
        for u in queryset.filter(role="tutor"):
            TutorProfile.objects.filter(user=u).update(is_kyc_verified=True)
            u.status = User.Status.ACTIVE
            u.save(update_fields=["status"])
            send_sms(normalize_phone(str(u.phone)), sms_kyc_approved("tutor"))
        self.message_user(request, f"KYC répétiteurs approuvés.")

    @admin.action(description="🏪 Valider KYC vendeurs")
    def approve_vendor_kyc(self, request, queryset):
        from kharandi.services.sms import send_sms, normalize_phone, sms_kyc_approved
        from .models import VendorProfile
        for u in queryset.filter(role="vendor"):
            VendorProfile.objects.filter(user=u).update(kyc_status=VendorProfile.KYCStatus.APPROVED)
            u.status = User.Status.ACTIVE
            u.save(update_fields=["status"])
            send_sms(normalize_phone(str(u.phone)), sms_kyc_approved("vendor"))
        self.message_user(request, f"KYC vendeurs approuvés.")


@admin.register(VendorProfile)
class VendorProfileAdmin(ModelAdmin):
    list_display  = ["shop_name", "user", "kyc_status", "total_sales", "is_featured"]
    list_filter   = ["kyc_status", "is_featured"]
    search_fields = ["shop_name", "user__phone"]


@admin.register(TutorProfile)
class TutorProfileAdmin(ModelAdmin):
    list_display  = ["user", "subjects", "price_per_hour", "is_kyc_verified", "avg_rating"]
    list_filter   = ["is_kyc_verified"]
    search_fields = ["user__phone", "subjects"]


@admin.register(OTPCode)
class OTPCodeAdmin(ModelAdmin):
    list_display    = ["phone", "purpose", "is_used", "created_at", "expires_at"]
    list_filter     = ["purpose", "is_used"]
    search_fields   = ["phone"]
    readonly_fields = ["phone", "code", "purpose", "created_at", "expires_at"]
    actions         = ["cleanup_expired"]

    @admin.action(description="🧹 Supprimer les OTP expirés")
    def cleanup_expired(self, request, queryset):
        n = OTPCode.cleanup_expired()
        self.message_user(request, f"{n} OTP expirés supprimés.")


@admin.register(PointsHistory)
class PointsHistoryAdmin(ModelAdmin):
    list_display    = ["user", "amount", "reason", "created_at"]
    readonly_fields = ["user", "amount", "reason", "created_at"]
