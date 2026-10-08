from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NGINX_CONFIG = ROOT / "deploy" / "nginx.conf.template"


def test_public_nginx_denies_internal_api_before_general_api_proxy() -> None:
    config = NGINX_CONFIG.read_text(encoding="utf-8")

    internal = "location ^~ /api/internal/"
    public_api = "location /api/"
    assert internal in config
    assert config.index(internal) < config.index(public_api)
    internal_block = config[config.index(internal) : config.index(public_api)]
    assert "return 404;" in internal_block


def _location_block(config: str, header: str) -> str:
    start = config.index(header)
    return config[start : config.index("}", start)]


def _widget_server(config: str) -> str:
    marker = "server_name __WIDGET_HOST__;"
    start = config.rindex("server {", 0, config.index(marker))
    nxt = config.find("\nserver {", config.index(marker))
    return config[start:] if nxt == -1 else config[start:nxt]


def test_websocket_locations_forward_the_public_host() -> None:
    config = NGINX_CONFIG.read_text(encoding="utf-8")

    for header in ("location = /ws/visitor {", "location = /ws/agent {"):
        block = _location_block(config, header)
        assert "proxy_set_header Upgrade $http_upgrade;" in block
        assert "proxy_set_header Host $host;" in block


def test_nginx_rate_limits_login_and_widget_bootstrap() -> None:
    config = NGINX_CONFIG.read_text(encoding="utf-8")
    assert "limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;" in config
    assert "limit_req_zone $binary_remote_addr zone=bootstrap:10m rate=60r/m;" in config
    auth_block = _location_block(config, "location ^~ /auth/ {")
    assert "limit_req zone=auth burst=5 nodelay;" in auth_block
    widget_start = config.rindex("location = /api/public/widget-bootstrap {")
    widget_bootstrap = config[widget_start : config.index("}", widget_start)]
    assert "limit_req zone=bootstrap burst=20 nodelay;" in widget_bootstrap
    assert "proxy_pass http://127.0.0.1:8000;" in widget_bootstrap


def test_widget_host_proxies_phosphor_icons_and_message_tone() -> None:
    widget = _widget_server(NGINX_CONFIG.read_text(encoding="utf-8"))
    icons = _location_block(widget, "location ^~ /icons/")
    sounds = _location_block(widget, "location ^~ /sounds/")
    catch_all = _location_block(widget, "location / {")
    assert "proxy_pass http://127.0.0.1:3000;" in icons
    assert "proxy_pass http://127.0.0.1:3000;" in sounds
    assert "return 404;" in catch_all
