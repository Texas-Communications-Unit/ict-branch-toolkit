from rest_framework import serializers

from .models import ConventionalChannel, ResourceRelease, ResourceSource, TrunkedTalkgroup


class ResourceSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceSource
        fields = ["id", "slug", "name", "source_type", "authoritative_url"]


class ResourceReleaseSerializer(serializers.ModelSerializer):
    source = ResourceSourceSerializer(read_only=True)

    class Meta:
        model = ResourceRelease
        fields = [
            "id",
            "source",
            "version",
            "released_on",
            "effective_status",
            "content_sha256",
            "document_title",
            "publisher",
            "retrieved_on",
            "permitted_use",
            "transformation_method",
            "imported_at",
        ]


class ConventionalChannelSerializer(serializers.ModelSerializer):
    release = ResourceReleaseSerializer(read_only=True)

    class Meta:
        model = ConventionalChannel
        fields = [
            "id",
            "release",
            "identifier",
            "name",
            "channel_use",
            "band",
            "jurisdiction",
            "rx_frequency_hz",
            "tx_frequency_hz",
            "bandwidth_hz",
            "mode",
            "rx_squelch",
            "tx_squelch",
            "emission_designator",
            "eligibility",
            "authorization",
            "source_section",
            "source_pages",
            "restrictions",
            "notes",
            "is_active",
        ]


class TrunkedTalkgroupSerializer(serializers.ModelSerializer):
    release = ResourceReleaseSerializer(read_only=True)

    class Meta:
        model = TrunkedTalkgroup
        fields = [
            "id",
            "release",
            "identifier",
            "name",
            "system_name",
            "talkgroup_id",
            "mode",
            "eligibility",
            "authorization",
            "source_section",
            "source_pages",
            "restrictions",
            "notes",
            "is_active",
        ]


class ImportSourceSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=80)
    name = serializers.CharField(max_length=200)
    source_type = serializers.ChoiceField(choices=ResourceSource.Type.choices)
    authoritative_url = serializers.URLField(max_length=500, required=False, allow_blank=True)


class ImportReleaseSerializer(serializers.Serializer):
    version = serializers.CharField(max_length=80)
    released_on = serializers.DateField(required=False, allow_null=True)
    effective_status = serializers.ChoiceField(choices=ResourceRelease.Status.choices)
    content_sha256 = serializers.RegexField(r"^[0-9a-f]{64}$")
    document_title = serializers.CharField(max_length=300, required=False, allow_blank=True)
    publisher = serializers.CharField(max_length=200, required=False, allow_blank=True)
    retrieved_on = serializers.DateField(required=False, allow_null=True)
    permitted_use = serializers.CharField(required=False, allow_blank=True)
    transformation_method = serializers.CharField(required=False, allow_blank=True)


class ImportConventionalChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConventionalChannel
        exclude = ["id", "release"]


class ImportTrunkedTalkgroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrunkedTalkgroup
        exclude = ["id", "release"]


class ChannelImportSerializer(serializers.Serializer):
    dry_run = serializers.BooleanField(default=True)
    source = ImportSourceSerializer()
    release = ImportReleaseSerializer()
    conventional_channels = ImportConventionalChannelSerializer(many=True, required=False)
    trunked_talkgroups = ImportTrunkedTalkgroupSerializer(many=True, required=False)

    def validate(self, attrs):
        conventional = attrs.get("conventional_channels", [])
        talkgroups = attrs.get("trunked_talkgroups", [])
        if not conventional and not talkgroups:
            raise serializers.ValidationError("At least one resource record is required.")
        for field, records in (
            ("conventional_channels", conventional),
            ("trunked_talkgroups", talkgroups),
        ):
            identifiers = [record["identifier"] for record in records]
            duplicates = sorted({value for value in identifiers if identifiers.count(value) > 1})
            if duplicates:
                raise serializers.ValidationError(
                    {field: f"Duplicate identifiers in payload: {', '.join(duplicates)}"}
                )
        return attrs


class StructuredImportErrorSerializer(serializers.Serializer):
    path = serializers.CharField()
    code = serializers.CharField()
    message = serializers.CharField()


class ChannelImportResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    dry_run = serializers.BooleanField()
    approval_required = serializers.BooleanField(required=False)
    would_create = serializers.DictField(child=serializers.IntegerField(), required=False)
    created = serializers.DictField(child=serializers.IntegerField(), required=False)
    import_id = serializers.UUIDField(required=False)
    release_id = serializers.UUIDField(required=False)
    errors = StructuredImportErrorSerializer(many=True)
