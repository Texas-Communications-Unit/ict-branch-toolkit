import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _isolate_throttle_cache():
    """Clear the process-wide cache before every test.

    DRF's rate throttles (added for P1.6 hardening) key their counters in Django's default
    cache, which pytest-django's per-test transaction rollback does not reset. Without this,
    request counts would accumulate across unrelated tests in the same run and could trip a
    throttle meant for a single test's own requests.
    """
    cache.clear()
    yield
    cache.clear()
