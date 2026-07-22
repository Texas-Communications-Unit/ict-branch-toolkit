from rest_framework import serializers

from apps.accounts.policy import permissions_for_user

from .models import Incident, IncidentMembership, OperationalPeriod


class OperationalPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationalPeriod
        fields = [
            "id",
            "incident",
            "name",
            "starts_at",
            "ends_at",
            "created_at",
            "updated_at",
            "archived_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "archived_at"]

    def validate(self, attrs):
        if (
            self.instance
            and attrs.get("incident", self.instance.incident) != self.instance.incident
        ):
            raise serializers.ValidationError({"incident": "The incident cannot be changed."})
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "End must be after start."})
        return attrs


class IncidentSerializer(serializers.ModelSerializer):
    operational_periods = OperationalPeriodSerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = [
            "id",
            "name",
            "incident_number",
            "status",
            "operational_periods",
            "created_at",
            "updated_at",
            "archived_at",
            "permissions",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "archived_at", "permissions"]

    def get_permissions(self, incident) -> list[str]:
        request = self.context.get("request")
        if not request:
            return []
        return sorted(permissions_for_user(request.user, incident))


class IncidentMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = IncidentMembership
        fields = [
            "id",
            "incident",
            "user",
            "username",
            "role",
            "is_active",
            "assigned_at",
            "updated_at",
        ]
        read_only_fields = ["id", "username", "assigned_at", "updated_at"]

    def validate(self, attrs):
        incident = attrs.get("incident", getattr(self.instance, "incident", None))
        if self.instance:
            if incident != self.instance.incident:
                raise serializers.ValidationError({"incident": "The incident cannot be changed."})
            if attrs.get("user", self.instance.user) != self.instance.user:
                raise serializers.ValidationError({"user": "The user cannot be changed."})
        if incident and incident.archived_at:
            raise serializers.ValidationError(
                "Memberships cannot be changed on an archived incident."
            )
        return attrs
