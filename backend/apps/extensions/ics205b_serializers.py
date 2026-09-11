from rest_framework import serializers

from .ics205b_models import ICS205BAssignment, ICS205BForm


class ICS205BAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ICS205BAssignment
        fields = [
            "id",
            "form",
            "position",
            "assignment",
            "it_resource_type",
            "resource_name",
            "usage_description",
            "platform",
            "developer",
            "login_install",
            "equipment_location",
            "poc_information",
            "remarks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ICS205BFormSerializer(serializers.ModelSerializer):
    assignments = ICS205BAssignmentSerializer(many=True, read_only=True)
    incident_name = serializers.CharField(source="incident.name", read_only=True)
    operational_period_name = serializers.CharField(
        source="operational_period.name", read_only=True
    )
    operational_period_starts_at = serializers.DateTimeField(
        source="operational_period.starts_at", read_only=True
    )
    operational_period_ends_at = serializers.DateTimeField(
        source="operational_period.ends_at", read_only=True
    )

    class Meta:
        model = ICS205BForm
        fields = [
            "id",
            "incident",
            "incident_name",
            "operational_period",
            "operational_period_name",
            "operational_period_starts_at",
            "operational_period_ends_at",
            "prepared_at",
            "prepared_by_name",
            "prepared_by_position",
            "prepared_by_phone",
            "prepared_by_signature",
            "incident_location",
            "state",
            "county",
            "city",
            "assignments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        incident = attrs.get("incident", getattr(self.instance, "incident", None))
        operational_period = attrs.get(
            "operational_period", getattr(self.instance, "operational_period", None)
        )
        if (
            incident is not None
            and operational_period is not None
            and operational_period.incident_id != incident.id
        ):
            raise serializers.ValidationError(
                {
                    "operational_period": (
                        "Operational period must belong to the selected incident."
                    )
                }
            )
        return attrs
