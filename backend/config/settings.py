from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
database_url = os.getenv("DATABASE_URL")
ENABLE_GIS = os.getenv("DJANGO_ENABLE_GIS", str(bool(database_url))).lower() == "true"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-test-only-key")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "corsheaders",
    "apps.accounts",
    "apps.audit",
    "apps.incidents",
    "apps.resources",
    "apps.plans",
    "apps.sites",
    "apps.rf_analysis",
    "apps.deconfliction",
    "apps.collaboration",
    "apps.extensions",
]
if ENABLE_GIS:
    INSTALLED_APPS.append("django.contrib.gis")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"

if database_url:
    DATABASES = {"default": dj_database_url.parse(database_url, conn_max_age=60)}
else:
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    }
DATABASES["default"]["ATOMIC_REQUESTS"] = True

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ICT_ROLE_POLICY_OVERRIDES = json.loads(os.getenv("ICT_ROLE_POLICY_OVERRIDES", "{}"))
ICT_IDENTITY_PROVIDER = os.getenv("ICT_IDENTITY_PROVIDER", "local")
ICT_EXTERNAL_SSO_ENABLED = os.getenv("ICT_EXTERNAL_SSO_ENABLED", "false").lower() == "true"
ICT_EXTERNAL_IDENTITY_PROVIDER = os.getenv(
    "ICT_EXTERNAL_IDENTITY_PROVIDER",
    "apps.accounts.external_identity.DisabledExternalIdentityProvider",
)
ICT_EXTERNAL_ROLE_MAPPINGS = json.loads(os.getenv("ICT_EXTERNAL_ROLE_MAPPINGS", "{}"))
if not isinstance(ICT_EXTERNAL_ROLE_MAPPINGS, dict):
    raise ValueError("ICT_EXTERNAL_ROLE_MAPPINGS must be a JSON object.")
ICT_TOKEN_TTL_SECONDS = int(os.getenv("ICT_TOKEN_TTL_SECONDS", "28800"))
if ICT_TOKEN_TTL_SECONDS <= 0:
    raise ValueError("ICT_TOKEN_TTL_SECONDS must be greater than zero.")
ICT_COLLABORATION_PRESENCE_TTL_SECONDS = int(
    os.getenv("ICT_COLLABORATION_PRESENCE_TTL_SECONDS", "75")
)
if not 30 <= ICT_COLLABORATION_PRESENCE_TTL_SECONDS <= 300:
    raise ValueError("ICT_COLLABORATION_PRESENCE_TTL_SECONDS must be between 30 and 300.")
ICT_COLLABORATION_HISTORY_LIMIT = int(os.getenv("ICT_COLLABORATION_HISTORY_LIMIT", "100"))
if not 10 <= ICT_COLLABORATION_HISTORY_LIMIT <= 500:
    raise ValueError("ICT_COLLABORATION_HISTORY_LIMIT must be between 10 and 500.")
ICT_RESTRICTED_FIELD_DEFAULT_VIEW_ROLES = json.loads(
    os.getenv(
        "ICT_RESTRICTED_FIELD_DEFAULT_VIEW_ROLES",
        '["administrator","coml","comc"]',
    )
)
ICT_RESTRICTED_FIELD_DEFAULT_EDIT_ROLES = json.loads(
    os.getenv(
        "ICT_RESTRICTED_FIELD_DEFAULT_EDIT_ROLES",
        '["administrator","coml","comc"]',
    )
)
for setting_name, configured_roles in (
    ("ICT_RESTRICTED_FIELD_DEFAULT_VIEW_ROLES", ICT_RESTRICTED_FIELD_DEFAULT_VIEW_ROLES),
    ("ICT_RESTRICTED_FIELD_DEFAULT_EDIT_ROLES", ICT_RESTRICTED_FIELD_DEFAULT_EDIT_ROLES),
):
    if not isinstance(configured_roles, list) or not all(
        isinstance(role, str) for role in configured_roles
    ):
        raise ValueError(f"{setting_name} must be a JSON array of role names.")
    allowed_roles = {"administrator", "coml", "comc", "comt", "contributor", "read_only"}
    if any(role not in allowed_roles for role in configured_roles):
        raise ValueError(f"{setting_name} contains an unrecognized role.")
if not set(ICT_RESTRICTED_FIELD_DEFAULT_EDIT_ROLES).issubset(
    set(ICT_RESTRICTED_FIELD_DEFAULT_VIEW_ROLES)
):
    raise ValueError("ICT_RESTRICTED_FIELD_DEFAULT_EDIT_ROLES must be a subset of view roles.")
ICT_APPROVED_REFERENCE_IMPORTS = json.loads(os.getenv("ICT_APPROVED_REFERENCE_IMPORTS", "[]"))
ICT_GEOCODER_PROVIDER = os.getenv("ICT_GEOCODER_PROVIDER", "apps.sites.geocoders.DisabledGeocoder")
ICT_ELEVATION_PROVIDER = os.getenv(
    "ICT_ELEVATION_PROVIDER",
    "apps.rf_analysis.elevation.DisabledElevationProvider",
)
ICT_APPROVED_ELEVATION_SOURCES = json.loads(os.getenv("ICT_APPROVED_ELEVATION_SOURCES", "[]"))
ICT_ELEVATION_CACHE_TTL_SECONDS = int(os.getenv("ICT_ELEVATION_CACHE_TTL_SECONDS", "604800"))
if ICT_ELEVATION_CACHE_TTL_SECONDS < 0:
    raise ValueError("ICT_ELEVATION_CACHE_TTL_SECONDS cannot be negative.")
ICT_SYNTHETIC_ELEVATION_MODE = os.getenv("ICT_SYNTHETIC_ELEVATION_MODE", "flat")
if ICT_SYNTHETIC_ELEVATION_MODE not in {
    "flat",
    "slope",
    "rugged",
    "missing",
    "boundary",
    "out_of_coverage",
    "datum",
    "failure",
}:
    raise ValueError("ICT_SYNTHETIC_ELEVATION_MODE is not supported.")
ICT_COVERAGE_ENGINE = os.getenv(
    "ICT_COVERAGE_ENGINE",
    "apps.rf_analysis.coverage.ProvisionalFsplHorizonEngine",
)
ICT_COVERAGE_PRESETS = json.loads(os.getenv("ICT_COVERAGE_PRESETS", "{}"))
if not isinstance(ICT_COVERAGE_PRESETS, dict):
    raise ValueError("ICT_COVERAGE_PRESETS must be a JSON object.")
ICT_APPROVED_COVERAGE_CONFIGURATIONS = json.loads(
    os.getenv("ICT_APPROVED_COVERAGE_CONFIGURATIONS", "[]")
)
if not isinstance(ICT_APPROVED_COVERAGE_CONFIGURATIONS, list):
    raise ValueError("ICT_APPROVED_COVERAGE_CONFIGURATIONS must be a JSON array.")
ICT_APPROVED_DIRECTIONAL_RULES = json.loads(os.getenv("ICT_APPROVED_DIRECTIONAL_RULES", "[]"))
if not isinstance(ICT_APPROVED_DIRECTIONAL_RULES, list) or not all(
    isinstance(rule, str) for rule in ICT_APPROVED_DIRECTIONAL_RULES
):
    raise ValueError("ICT_APPROVED_DIRECTIONAL_RULES must be a JSON array of strings.")
ICT_APPROVED_CALIBRATION_METHODS = json.loads(os.getenv("ICT_APPROVED_CALIBRATION_METHODS", "[]"))
if not isinstance(ICT_APPROVED_CALIBRATION_METHODS, list) or not all(
    isinstance(method, str) for method in ICT_APPROVED_CALIBRATION_METHODS
):
    raise ValueError("ICT_APPROVED_CALIBRATION_METHODS must be a JSON array of strings.")
ICT_APPROVED_PHASE2_VALIDATION_PROFILES = json.loads(
    os.getenv("ICT_APPROVED_PHASE2_VALIDATION_PROFILES", "[]")
)
if not isinstance(ICT_APPROVED_PHASE2_VALIDATION_PROFILES, list) or not all(
    isinstance(profile, str) for profile in ICT_APPROVED_PHASE2_VALIDATION_PROFILES
):
    raise ValueError("ICT_APPROVED_PHASE2_VALIDATION_PROFILES must be a JSON array of strings.")
ICT_APPROVED_DECONFLICTION_RULESETS = json.loads(
    os.getenv("ICT_APPROVED_DECONFLICTION_RULESETS", "[]")
)
if not isinstance(ICT_APPROVED_DECONFLICTION_RULESETS, list) or not all(
    isinstance(rule_set, str) for rule_set in ICT_APPROVED_DECONFLICTION_RULESETS
):
    raise ValueError("ICT_APPROVED_DECONFLICTION_RULESETS must be a JSON array of strings.")
ICT_TERRAIN_PROVIDER = os.getenv(
    "ICT_TERRAIN_PROVIDER",
    "apps.rf_analysis.terrain.DisabledTerrainProfileProvider",
)
ICT_TERRAIN_ENGINE = os.getenv(
    "ICT_TERRAIN_ENGINE",
    "apps.rf_analysis.terrain.ProvisionalSampledLineOfSightEngine",
)
ICT_APPROVED_TERRAIN_CONFIGURATIONS = json.loads(
    os.getenv("ICT_APPROVED_TERRAIN_CONFIGURATIONS", "[]")
)
if not isinstance(ICT_APPROVED_TERRAIN_CONFIGURATIONS, list) or not all(
    isinstance(configuration, dict) for configuration in ICT_APPROVED_TERRAIN_CONFIGURATIONS
):
    raise ValueError("ICT_APPROVED_TERRAIN_CONFIGURATIONS must be a JSON array of objects.")
ICT_SYNTHETIC_TERRAIN_MODE = os.getenv("ICT_SYNTHETIC_TERRAIN_MODE", "flat")
if ICT_SYNTHETIC_TERRAIN_MODE not in {
    "flat",
    "ridge",
    "valley",
    "missing",
    "boundary",
    "out_of_coverage",
    "datum",
    "failure",
}:
    raise ValueError("ICT_SYNTHETIC_TERRAIN_MODE is not supported.")
ICT_TERRAIN_MAX_DISTANCE_M = int(os.getenv("ICT_TERRAIN_MAX_DISTANCE_M", "200000"))
if not 1_000 <= ICT_TERRAIN_MAX_DISTANCE_M <= 500_000:
    raise ValueError("ICT_TERRAIN_MAX_DISTANCE_M must be between 1000 and 500000.")
ICT_TERRAIN_MAX_SAMPLES = int(os.getenv("ICT_TERRAIN_MAX_SAMPLES", "1001"))
if not 2 <= ICT_TERRAIN_MAX_SAMPLES <= 5001:
    raise ValueError("ICT_TERRAIN_MAX_SAMPLES must be between 2 and 5001.")
RADIOREFERENCE_ENABLED = os.getenv("RADIOREFERENCE_ENABLED", "false").lower() == "true"
RADIOREFERENCE_WSDL_URL = os.getenv(
    "RADIOREFERENCE_WSDL_URL",
    "https://api.radioreference.com/soap2/?wsdl&v=latest",
).strip()
_radioreference_wsdl = urlsplit(RADIOREFERENCE_WSDL_URL)
if (
    len(RADIOREFERENCE_WSDL_URL) > 500
    or _radioreference_wsdl.scheme != "https"
    or not _radioreference_wsdl.hostname
    or _radioreference_wsdl.username
    or _radioreference_wsdl.password
    or _radioreference_wsdl.fragment
):
    raise ValueError(
        "RADIOREFERENCE_WSDL_URL must be an HTTPS URL without embedded credentials or a fragment."
    )
RADIOREFERENCE_MAX_RESPONSE_BYTES = int(os.getenv("RADIOREFERENCE_MAX_RESPONSE_BYTES", "1048576"))
if not 1_024 <= RADIOREFERENCE_MAX_RESPONSE_BYTES <= 5_242_880:
    raise ValueError("RADIOREFERENCE_MAX_RESPONSE_BYTES must be between 1024 and 5242880 bytes.")

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.ExpiringTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("DJANGO_THROTTLE_ANON_RATE", "30/min"),
        "user": os.getenv("DJANGO_THROTTLE_USER_RATE", "300/min"),
        "auth": os.getenv("DJANGO_THROTTLE_AUTH_RATE", "10/min"),
    },
    "EXCEPTION_HANDLER": "config.exceptions.handle_exception",
}

# Secure headers (P1.6 hardening). These are safe in every environment, including local
# development and CI over plain HTTP.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# HSTS, SSL redirect, and secure cookies are opt-in: they assume the deployment terminates TLS
# in front of Django (directly or via a trusted reverse proxy honoring SECURE_PROXY_SSL_HEADER
# above) and would otherwise break local development and CI, which run over plain HTTP.
DJANGO_FORCE_HTTPS = os.getenv("DJANGO_FORCE_HTTPS", "false").lower() == "true"
if DJANGO_FORCE_HTTPS:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

APP_VERSION = "0.2.0-rc.1"

SPECTACULAR_SETTINGS = {
    "TITLE": "ICT Branch Toolkit API",
    "DESCRIPTION": "Incident communications planning prototype API.",
    "VERSION": APP_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "PlanRevisionStatusEnum": "apps.plans.models.PlanRevision.Status",
        "ResourceChannelModeEnum": "apps.resources.models.ConventionalChannel.Mode",
        "FieldObservationReviewDecisionEnum": (
            "apps.rf_analysis.models.FieldObservationReview.Decision"
        ),
        "CollaborationResolutionDecisionEnum": (
            "apps.collaboration.models.CollaborationResolution.Decision"
        ),
        "CollaborationPresenceModeEnum": "apps.collaboration.models.PresenceLease.Mode",
        "CollaborationChangeDispositionEnum": (
            "apps.collaboration.models.CollaborationChange.Disposition"
        ),
        "DeconflictionFindingDispositionEnum": (
            "apps.deconfliction.models.DeconflictionFindingDisposition.Disposition"
        ),
        "ExtensionCapabilityKindEnum": "apps.extensions.models.ExtensionExecution.CapabilityKind",
        "ExtensionExecutionStatusEnum": "apps.extensions.models.ExtensionExecution.Status",
        "ExtensionOutputClassificationEnum": (
            "apps.extensions.models.ExtensionExecution.OutputClassification"
        ),
    },
}
