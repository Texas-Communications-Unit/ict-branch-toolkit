from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NGINX_CONFIG = REPOSITORY_ROOT / "frontend" / "nginx.conf"


def test_third_party_notices_do_not_fall_through_to_spa() -> None:
    nginx_config = NGINX_CONFIG.read_text(encoding="utf-8")

    location_start = nginx_config.index("location ^~ /third-party/")
    location_end = nginx_config.index("}", location_start)
    third_party_location = nginx_config[location_start:location_end]

    assert "try_files $uri =404;" in third_party_location
    assert 'add_header X-Content-Type-Options "nosniff" always;' in third_party_location
    assert "index.html" not in third_party_location
