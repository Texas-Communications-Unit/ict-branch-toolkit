import json
import os
from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class What3WordsResult:
    label: str
    latitude: float
    longitude: float
    provider: str


class What3WordsError(Exception):
    """Expected provider failure safe for an operator-facing response."""


class DisabledWhat3WordsProvider:
    name = "disabled"

    def search(self, words: str) -> list[What3WordsResult]:
        return []


class DeterministicTestWhat3WordsProvider:
    """Synthetic-only adapter for deterministic CI coverage."""

    name = "synthetic-what3words-provider"

    def search(self, words: str) -> list[What3WordsResult]:
        if words.lower() != "alpha.bravo.charlie":
            return []
        return [
            What3WordsResult(
                label="///alpha.bravo.charlie (synthetic fixture)",
                latitude=33.2145,
                longitude=-97.1331,
                provider=self.name,
            )
        ]


def _configured_path() -> str:
    return getattr(
        settings,
        "ICT_WHAT3WORDS_PROVIDER",
        os.getenv(
            "ICT_WHAT3WORDS_PROVIDER",
            "apps.sites.what3words.DisabledWhat3WordsProvider",
        ),
    )


def _approved_paths() -> list[str]:
    configured = getattr(settings, "ICT_APPROVED_WHAT3WORDS_PROVIDERS", None)
    if configured is not None:
        return configured if isinstance(configured, list) else []
    try:
        value = json.loads(os.getenv("ICT_APPROVED_WHAT3WORDS_PROVIDERS", "[]"))
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) and all(isinstance(item, str) for item in value) else []


def configured_what3words():
    path = _configured_path()
    disabled = "apps.sites.what3words.DisabledWhat3WordsProvider"
    if path == disabled:
        return DisabledWhat3WordsProvider()
    if path not in _approved_paths():
        return DisabledWhat3WordsProvider()
    provider_class = import_string(path)
    return provider_class()
