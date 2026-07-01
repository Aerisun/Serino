import httpx

PROXY_ENV_KEYS = (
    "ALL_PROXY",
    "all_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "NO_PROXY",
    "no_proxy",
)


def test_httpx_client_initializes_with_socks_proxy_environment(monkeypatch) -> None:
    for key in PROXY_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:7892")

    with httpx.Client() as client:
        assert isinstance(client, httpx.Client)
