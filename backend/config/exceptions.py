import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("ict_toolkit.api")


def handle_exception(exc, context):
    """Wrap DRF's default exception handler to add safe logging and handling for unknown errors.

    DRF's default handler already returns a well-formed JSON response for APIException
    subclasses (validation errors, permission denials, throttling, etc.); that existing shape is
    left untouched here. Any other exception (a bug) would otherwise propagate to Django's
    generic 500 handler, which is fine in DEBUG but returns an HTML page in production. Here we
    log the full exception with its request context for operators, and return a generic JSON
    body that never leaks a stack trace or internal exception message to the client.
    """
    response = exception_handler(exc, context)
    if response is not None:
        return response

    request = context.get("request")
    logger.exception(
        "Unhandled exception in %s %s",
        getattr(request, "method", "?"),
        getattr(request, "path", "?"),
        exc_info=exc,
    )
    return Response({"detail": "An unexpected error occurred."}, status=500)
