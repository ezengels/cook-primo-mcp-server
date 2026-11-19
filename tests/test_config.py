"""Tests for Primo configuration defaults."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from primo_mcp_server.config import PrimoConfig
from primo_mcp_server.formatter import build_search_url

_TOWSON_LOCATION_KEYS = (
    "PRIMO_BASE_URL",
    "PRIMO_DISCOVERY_BASE_URL",
    "PRIMO_VID",
    "PRIMO_TAB_EVERYTHING",
    "PRIMO_TAB_CATALOGUE",
    "PRIMO_TAB_BOOKS_VIDEOS",
    "PRIMO_SCOPE_COMBINED",
    "PRIMO_SCOPE_LOCAL",
    "PRIMO_SCOPE_BOOKS_VIDEOS",
)


def test_default_config_builds_towson_onesearch_links(monkeypatch):
    for key in _TOWSON_LOCATION_KEYS:
        monkeypatch.delenv(key, raising=False)
    config = PrimoConfig(_env_file=None)

    expected = {
        "everything": ("Everything", "DN_and_CI"),
        "catalogue": ("TULibraryCatalog", "MyInstitution"),
        # Towson-only alias for the books_videos slot.
        "network": ("New_Network_Catalog", "New_Discovery_Network"),
    }
    for scope, (tab, search_scope) in expected.items():
        url = build_search_url("piezo1", config, scope=scope)
        assert url is not None
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert (
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            == "https://usmai-tu.primo.exlibrisgroup.com/discovery/search"
        )
        assert params["vid"] == ["01USMAI_TU:01USMAI_TU"]
        assert params["tab"] == [tab], scope
        assert params["search_scope"] == [search_scope], scope


def test_default_config_is_towson(monkeypatch):
    for key in (
        "PRIMO_BASE_URL",
        "PRIMO_DISCOVERY_BASE_URL",
        "PRIMO_VID",
        "PRIMO_INSTITUTION_NAME",
        "PRIMO_TAB_EVERYTHING",
        "PRIMO_TAB_CATALOGUE",
        "PRIMO_TAB_BOOKS_VIDEOS",
        "PRIMO_SCOPE_COMBINED",
        "PRIMO_SCOPE_LOCAL",
        "PRIMO_SCOPE_BOOKS_VIDEOS",
        "PRIMO_LIBRARIANS_FILE",
        "PRIMO_INLINE_LIBRARIAN_RECOMMENDATIONS",
        "PRIMO_LIBRARIAN_MIN_SCORE",
    ):
        monkeypatch.delenv(key, raising=False)

    config = PrimoConfig(_env_file=None)

    assert config.base_url == "https://usmai-tu.primo.exlibrisgroup.com/primaws/rest/pub"
    assert config.discovery_base_url is None
    assert config.vid == "01USMAI_TU:01USMAI_TU"
    assert config.institution_name == "Towson University"
    assert config.tab_catalogue == "TULibraryCatalog"
    assert config.tab_everything == "Everything"
    assert config.tab_books_videos == "New_Network_Catalog"
    assert config.scope_local == "MyInstitution"
    assert config.scope_combined == "DN_and_CI"
    assert config.scope_books_videos == "New_Discovery_Network"
    assert config.librarians_file is None
    # Every librarian recommendation switch ships off; an institution
    # opts in after configuring a directory.
    assert config.inline_librarian_recommendations is False
    assert config.librarian_semantic_fallback is False
    assert config.librarian_llm_fallback is False
    assert config.librarian_llm_inline is False
    assert config.librarians_file is None
    assert config.librarian_min_score == 5.0


def test_user_agent_tracks_package_version():
    from importlib.metadata import version

    config = PrimoConfig(_env_file=None)
    assert config.user_agent == f"primo-mcp-server/{version('primo-mcp-server')}"
