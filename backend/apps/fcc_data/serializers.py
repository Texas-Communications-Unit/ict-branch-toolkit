from rest_framework import serializers

from .models import AntennaStructure, FccImportBatch, UlsLicense


class FccBatchSummarySerializer(serializers.ModelSerializer):
    dataset_label = serializers.CharField(source="get_dataset_display", read_only=True)

    class Meta:
        model = FccImportBatch
        fields = [
            "id", "dataset", "dataset_label", "archive_kind", "archive_name",
            "source_url", "content_sha256", "parser_version", "retrieved_at",
        ]


class AntennaStructureSerializer(serializers.ModelSerializer):
    batch = FccBatchSummarySerializer(read_only=True)

    class Meta:
        model = AntennaStructure
        fields = [
            "id", "registration_number", "status_code", "owner_name", "owner_frn",
            "structure_type", "latitude", "longitude", "structure_height_m",
            "ground_elevation_m", "overall_height_m", "overall_height_amsl_m",
            "faa_study_number", "painting_lighting", "construction_date",
            "dismantlement_date", "batch",
        ]


class UlsLicenseSerializer(serializers.ModelSerializer):
    batch = FccBatchSummarySerializer(read_only=True)
    frequencies_hz = serializers.SerializerMethodField()
    location_count = serializers.IntegerField(read_only=True)
    frequency_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = UlsLicense
        fields = [
            "id", "call_sign", "license_status", "radio_service_code",
            "applicant_type_code", "selection_rule", "licensee_name", "frn",
            "address", "city", "state", "postal_code", "grant_date",
            "expiration_date", "cancellation_date", "last_action_date",
            "location_count", "frequency_count", "frequencies_hz", "batch",
        ]

    def get_frequencies_hz(self, obj):
        return list(
            obj.frequencies.order_by("frequency_hz")
            .values_list("frequency_hz", flat=True)
            .distinct()[:10]
        )
