from urllib.parse import quote

from rest_framework import serializers

from .models import (
    AntennaStructure,
    FccImportBatch,
    UlsEmission,
    UlsFrequency,
    UlsLicense,
    UlsLocation,
)


class FccBatchSummarySerializer(serializers.ModelSerializer):
    dataset_label = serializers.CharField(source="get_dataset_display", read_only=True)

    class Meta:
        model = FccImportBatch
        fields = [
            "id",
            "dataset",
            "dataset_label",
            "archive_kind",
            "archive_name",
            "source_url",
            "content_sha256",
            "parser_version",
            "retrieved_at",
        ]


class AntennaStructureSerializer(serializers.ModelSerializer):
    batch = FccBatchSummarySerializer(read_only=True)
    fcc_record_url = serializers.SerializerMethodField()

    class Meta:
        model = AntennaStructure
        fields = [
            "id",
            "registration_number",
            "status_code",
            "owner_name",
            "owner_frn",
            "structure_type",
            "latitude",
            "longitude",
            "structure_height_m",
            "ground_elevation_m",
            "overall_height_m",
            "overall_height_amsl_m",
            "faa_study_number",
            "painting_lighting",
            "construction_date",
            "dismantlement_date",
            "fcc_record_url",
            "batch",
        ]

    def get_fcc_record_url(self, obj) -> str:
        if not obj.unique_system_identifier:
            return "https://wireless2.fcc.gov/UlsApp/AsrSearch/asrSearch.jsp"
        key = quote(obj.unique_system_identifier, safe="")
        return f"https://wireless2.fcc.gov/UlsApp/AsrSearch/asrRegistration.jsp?regKey={key}"


class FccMapFeatureSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["cluster", "tower"])
    key = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    count = serializers.IntegerField(min_value=1)
    tower = AntennaStructureSerializer(required=False, allow_null=True)


class FccMapFeatureCollectionSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    feature_count = serializers.IntegerField(min_value=0)
    truncated = serializers.BooleanField()
    results = FccMapFeatureSerializer(many=True)


class UlsLicenseSerializer(serializers.ModelSerializer):
    batch = FccBatchSummarySerializer(read_only=True)
    frequencies_hz = serializers.SerializerMethodField()
    location_count = serializers.IntegerField(read_only=True)
    frequency_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = UlsLicense
        fields = [
            "id",
            "call_sign",
            "license_status",
            "radio_service_code",
            "applicant_type_code",
            "selection_rule",
            "licensee_name",
            "frn",
            "address",
            "city",
            "state",
            "postal_code",
            "grant_date",
            "expiration_date",
            "cancellation_date",
            "last_action_date",
            "location_count",
            "frequency_count",
            "frequencies_hz",
            "batch",
        ]

    def get_frequencies_hz(self, obj) -> list[int]:
        return list(
            obj.frequencies.order_by("frequency_hz")
            .values_list("frequency_hz", flat=True)
            .distinct()[:10]
        )


class FccTowerFrequencySerializer(serializers.ModelSerializer):
    antenna_number = serializers.IntegerField(min_value=-2_147_483_648, max_value=2_147_483_647)
    number_of_units = serializers.IntegerField(
        min_value=-2_147_483_648,
        max_value=2_147_483_647,
        allow_null=True,
        required=False,
    )

    class Meta:
        model = UlsFrequency
        fields = [
            "antenna_number",
            "station_class_code",
            "frequency_hz",
            "output_power_w",
            "effective_radiated_power_w",
            "number_of_units",
        ]


class FccTowerEmissionSerializer(serializers.ModelSerializer):
    antenna_number = serializers.IntegerField(min_value=-2_147_483_648, max_value=2_147_483_647)

    class Meta:
        model = UlsEmission
        fields = ["antenna_number", "frequency_hz", "emission_designator"]


class FccTowerLocationSerializer(serializers.ModelSerializer):
    location_number = serializers.IntegerField(min_value=0, max_value=2_147_483_647)
    frequencies = FccTowerFrequencySerializer(many=True, read_only=True)
    emissions = FccTowerEmissionSerializer(many=True, read_only=True)

    class Meta:
        model = UlsLocation
        fields = [
            "location_number",
            "location_type_code",
            "location_class_code",
            "address",
            "city",
            "county",
            "state",
            "latitude",
            "longitude",
            "ground_elevation_m",
            "asr_registration_number",
            "structure_type",
            "frequencies",
            "emissions",
        ]


class FccTowerLicenseSerializer(serializers.ModelSerializer):
    batch = FccBatchSummarySerializer(read_only=True)
    tower_locations = FccTowerLocationSerializer(many=True, read_only=True)
    fcc_record_url = serializers.SerializerMethodField()

    class Meta:
        model = UlsLicense
        fields = [
            "id",
            "call_sign",
            "license_status",
            "radio_service_code",
            "licensee_name",
            "frn",
            "grant_date",
            "expiration_date",
            "tower_locations",
            "fcc_record_url",
            "batch",
        ]

    def get_fcc_record_url(self, obj) -> str:
        key = quote(obj.unique_system_identifier, safe="")
        return f"https://wireless2.fcc.gov/UlsApp/UlsSearch/license.jsp?licKey={key}"


class FccTowerDetailSerializer(serializers.Serializer):
    structure = AntennaStructureSerializer()
    licenses = FccTowerLicenseSerializer(many=True)
    license_count = serializers.IntegerField()
    truncated = serializers.BooleanField()
    disclaimer = serializers.CharField()
