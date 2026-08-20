from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from apps.incidents.models import Incident, IncidentMembership

from .models import LocalContingencyAccount, Role, UserRoleAssignment
from .policy import permissions_for_user, role_for_user


class TokenSessionSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)


class ExternalIdentityStatusSerializer(serializers.Serializer):
    provider = serializers.CharField(read_only=True)
    enabled = serializers.BooleanField(read_only=True)
    protocol = serializers.CharField(read_only=True)
    authorization_code_flow = serializers.BooleanField(read_only=True)
    password_passthrough = serializers.BooleanField(read_only=True)
    live_connection = serializers.BooleanField(read_only=True)
    warning = serializers.CharField(read_only=True)
    break_glass_local_login_available = serializers.BooleanField(read_only=True)
    eligibility_group = serializers.CharField(read_only=True)
    role_field = serializers.CharField(read_only=True)
    identity_refresh_seconds = serializers.IntegerField(read_only=True)
    outage_grace_seconds = serializers.IntegerField(read_only=True)
    allowed_roles = serializers.ListField(child=serializers.CharField(), read_only=True)


class CurrentUserSerializer(serializers.Serializer):
    username = serializers.CharField(read_only=True)
    display_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    def get_display_name(self, user) -> str:
        return user.get_full_name() or user.get_username()

    def get_role(self, user) -> str:
        return role_for_user(user)

    def get_permissions(self, user) -> list[str]:
        return sorted(permissions_for_user(user))


class LocalContingencyAccountSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    display_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    linked_to_external_identity = serializers.SerializerMethodField()

    class Meta:
        model = LocalContingencyAccount
        fields = [
            "username",
            "display_name",
            "email",
            "role",
            "is_active",
            "linked_to_external_identity",
            "reason",
            "must_change_password",
            "disabled_at",
            "disabled_reason",
            "created_at",
            "updated_at",
        ]

    def get_display_name(self, account) -> str:
        return account.user.get_full_name() or account.user.get_username()

    def get_role(self, account) -> str:
        return role_for_user(account.user)

    def get_linked_to_external_identity(self, account) -> bool:
        return hasattr(account.user, "external_identity")


class LocalContingencyAccountCreateSerializer(serializers.Serializer):
    username = serializers.RegexField(r"^[A-Za-z0-9.@_+-]{3,150}$")
    display_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=Role.choices)
    reason = serializers.CharField(max_length=500)
    incidents = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Incident.objects.filter(archived_at__isnull=True),
        required=False,
    )

    def validate_username(self, value):
        if get_user_model().objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is already in use.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if get_user_model().objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("That email address is already in use.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        incidents = validated_data.pop("incidents", [])
        actor = self.context["request"].user
        temporary_password = self.context["temporary_password"]
        user = get_user_model().objects.create(
            username=validated_data["username"],
            first_name=validated_data["display_name"],
            email=validated_data["email"],
            is_active=True,
        )
        user.set_password(temporary_password)
        user.save(update_fields=["password"])
        UserRoleAssignment.objects.create(
            user=user,
            role=validated_data["role"],
            assigned_by=actor,
        )
        account = LocalContingencyAccount.objects.create(
            user=user,
            reason=validated_data["reason"],
            created_by=actor,
        )
        IncidentMembership.objects.bulk_create(
            [
                IncidentMembership(
                    incident=incident,
                    user=user,
                    role=validated_data["role"],
                    assigned_by=actor,
                )
                for incident in incidents
            ]
        )
        return account


class LocalContingencyActivationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    temporary_password = serializers.CharField(
        max_length=256,
        trim_whitespace=False,
        write_only=True,
    )
    new_password = serializers.CharField(
        max_length=256,
        trim_whitespace=False,
        write_only=True,
    )

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["username"],
            password=attrs["temporary_password"],
        )
        if not user:
            raise serializers.ValidationError("The temporary credentials are not valid.")
        try:
            account = user.local_contingency_account
        except LocalContingencyAccount.DoesNotExist as exc:
            raise serializers.ValidationError(
                "This account does not use local contingency activation."
            ) from exc
        if not account.must_change_password:
            raise serializers.ValidationError("This temporary credential was already used.")
        password_validation.validate_password(attrs["new_password"], user)
        attrs["user"] = user
        attrs["account"] = account
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class LocalContingencyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        value = value.strip().lower()
        account = self.context["account"]
        if (
            get_user_model()
            .objects.filter(email__iexact=value)
            .exclude(pk=account.user_id)
            .exists()
        ):
            raise serializers.ValidationError("That email address is already in use.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=128, write_only=True)
    token = serializers.CharField(max_length=256, write_only=True)
    new_password = serializers.CharField(
        max_length=256,
        trim_whitespace=False,
        write_only=True,
    )

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = get_user_model().objects.get(pk=user_id, is_active=True)
            account = user.local_contingency_account
        except (ValueError, TypeError, OverflowError, get_user_model().DoesNotExist):
            raise serializers.ValidationError("This password-reset link is not valid.") from None
        except LocalContingencyAccount.DoesNotExist:
            raise serializers.ValidationError("This password-reset link is not valid.") from None
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError("This password-reset link is invalid or expired.")
        password_validation.validate_password(attrs["new_password"], user)
        attrs["user"] = user
        attrs["account"] = account
        return attrs
