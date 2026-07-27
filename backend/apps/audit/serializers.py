from rest_framework import serializers


class ExportDigestVerificationRequestSerializer(serializers.Serializer):
    content_sha256 = serializers.RegexField(
        r"\A[0-9a-fA-F]{64}\Z",
        required=False,
        allow_blank=False,
        error_messages={
            "invalid": "Use a 64-character SHA-256 hexadecimal digest.",
        },
    )
    file = serializers.FileField(required=False)
