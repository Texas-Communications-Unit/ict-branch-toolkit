from rest_framework import serializers

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
