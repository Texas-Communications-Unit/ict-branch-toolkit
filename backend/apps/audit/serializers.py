from rest_framework import serializers


class ExportDigestVerificationRequestSerializer(serializers.Serializer):
    content_sha256 = serializers.CharField(required=False, allow_blank=False)
    file = serializers.FileField(required=False)
