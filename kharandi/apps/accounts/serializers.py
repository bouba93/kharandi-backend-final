from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import TutorProfile, VendorProfile

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ["phone", "first_name", "last_name", "role", "password", "password2"]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError({"password2": "Les mots de passe ne correspondent pas."})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ["id", "phone", "email", "first_name", "last_name", "full_name",
                  "display_name", "role", "status", "points", "city", "district",
                  "phone_verified", "date_joined", "last_active"]
        read_only_fields = ["id", "phone", "role", "status", "points",
                            "phone_verified", "date_joined"]

    def get_full_name(self, obj): return obj.get_full_name()


class TutorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TutorProfile
        fields = ["subjects", "levels", "price_per_hour", "is_kyc_verified",
                  "avg_rating", "total_students", "description"]
        read_only_fields = ["is_kyc_verified", "avg_rating", "total_students"]


class VendorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = VendorProfile
        fields = ["shop_name", "shop_logo", "shop_address", "kyc_status",
                  "total_sales", "avg_rating", "is_featured"]
        read_only_fields = ["kyc_status", "total_sales", "avg_rating", "is_featured"]


class OTPSendSerializer(serializers.Serializer):
    phone   = serializers.CharField(max_length=20)
    purpose = serializers.ChoiceField(choices=["verification", "password_reset"],
                                      default="verification")


class OTPVerifySerializer(serializers.Serializer):
    phone   = serializers.CharField(max_length=20)
    code    = serializers.CharField(max_length=6, min_length=6)
    purpose = serializers.ChoiceField(choices=["verification", "password_reset"],
                                      default="verification")
