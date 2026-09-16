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
