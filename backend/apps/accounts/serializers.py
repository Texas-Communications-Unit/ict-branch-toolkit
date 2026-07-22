from rest_framework import serializers

from .policy import permissions_for_user, role_for_user


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
