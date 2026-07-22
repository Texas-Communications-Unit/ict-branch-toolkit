from rest_framework import serializers

from .models import Incident, OperationalPeriod


class OperationalPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationalPeriod
        fields = ["id", "incident", "name", "starts_at", "ends_at", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        if attrs["ends_at"] <= attrs["starts_at"]:
            raise serializers.ValidationError({"ends_at": "End must be after start."})
        return attrs


class IncidentSerializer(serializers.ModelSerializer):
    operational_periods = OperationalPeriodSerializer(many=True, read_only=True)

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
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
