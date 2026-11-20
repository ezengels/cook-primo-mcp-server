"""Tests for Primo API client request construction."""

from __future__ import annotations

import httpx
import pytest

from primo_mcp_server.client import PrimoAPIError, PrimoClient, _normalise_scope
from primo_mcp_server.config import PrimoConfig


def _config() -> PrimoConfig:
    return PrimoConfig(
        base_url="https://example.test/primaws/rest/pub",
        vid="TEST:VID",
        tab_catalogue="Catalogue",
        tab_everything="Everything",
        tab_books_videos="booksandvideos",
        scope_local="MyInstitution",
        scope_combined="MyInst_and_CI",
        scope_books_videos="BooksVideos",
    )


def _empty_response() -> httpx.Response:
    return httpx.Response(200, json={"info": {"total": 0}, "docs": []})


class TestScopeResolution:
    def test_scope_aliases(self):
        assert _normalise_scope("catalog") == "catalogue"
        assert _normalise_scope("my_institution") == "catalogue"
        assert _normalise_scope("all") == "everything"
        assert _normalise_scope("myinst_and_ci") == "everything"
        assert _normalise_scope("books/videos") == "books_videos"
        assert _normalise_scope("books & videos") == "books_videos"
        assert _normalise_scope("booksandvideos") == "books_videos"

    def test_invalid_scope_raises_clear_error(self):
        with pytest.raises(PrimoAPIError, match='Invalid scope "catalogg"'):
            _normalise_scope("catalogg")


class TestSearchRequestScopes:
    @pytest.mark.parametrize(
        ("scope", "expected_tab", "expected_scope"),
        [
            ("catalogue", "Catalogue", "MyInstitution"),
            ("everything", "Everything", "MyInst_and_CI"),
            ("books_videos", "booksandvideos", "BooksVideos"),
            ("BooksVideos", "booksandvideos", "BooksVideos"),
        ],
    )
    async def test_search_maps_scope_to_primo_params(
        self,
        scope: str,
        expected_tab: str,
        expected_scope: str,
    ):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await client.search("Singapore", scope=scope)

        params = requests[0].url.params
        assert params["tab"] == expected_tab
        assert params["scope"] == expected_scope

    async def test_invalid_scope_does_not_make_request(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            with pytest.raises(PrimoAPIError):
                await client.search("Singapore", scope="catalogg")

        assert requests == []


class TestNonJsonResponses:
    _MAINTENANCE_HTML = (
        "<!DOCTYPE html>\n<html>\n"
        "   <!--Do not remove or edit this comment. EXL_green -->\n"
        '<body><div align="center" class="container">'
        '<img src="/maintenance.jpg"></div></body></html>'
    )

    async def _search_against(self, response: httpx.Response) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return response

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await client.search("covidence")

    async def test_maintenance_page_raises_clear_outage_error(self):
        response = httpx.Response(
            200,
            text=self._MAINTENANCE_HTML,
            headers={"content-type": "text/html; charset=UTF-8"},
        )
        with pytest.raises(PrimoAPIError, match="down for maintenance") as exc_info:
            await self._search_against(response)
        assert exc_info.value.status_code == 503

    async def test_other_non_json_body_raises_clear_error(self):
        response = httpx.Response(
            200,
            text="<html><body>Access denied</body></html>",
            headers={"content-type": "text/html; charset=UTF-8"},
        )
        with pytest.raises(PrimoAPIError, match="non-JSON response") as exc_info:
            await self._search_against(response)
        assert exc_info.value.status_code == 502


class TestSearchRequestFilters:
    async def test_search_normalises_field_sort_and_resource_type_aliases(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await client.search(
                "Singapore",
                field="subject",
                sort_by="newest",
                resource_type="book",
            )

        params = requests[0].url.params
        assert params["q"] == "sub,contains,Singapore"
        assert params["sort"] == "date_d"
        assert params["qInclude"] == "facet_rtype,exact,books"

    @pytest.mark.parametrize(
        ("sort_by", "expected"),
        [
            ("rank", "rank"),
            ("relevance", "rank"),
            ("date", "date_d"),
            ("oldest", "date_a"),
            ("title", "title"),
            ("author", "author"),
        ],
    )
    async def test_sort_is_sent_as_primo_sort_parameter(self, sort_by, expected):
        # /pnxs reads "sort" (rank, date_d, date_a, title, author) and
        # ignores "sortby": observed at Towson on 2026-11-19, sortby=date
        # and sortby=title both came back in relevance order.
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await client.search("hydrodynamics", scope="catalogue", sort_by=sort_by)

        params = requests[0].url.params
        assert params["sort"] == expected
        assert "sortby" not in params

    async def test_invalid_sort_lists_the_documented_names(self):
        # The error listed Primo's codes (date_a, date_d), not the names the
        # tool description gives callers.
        async with httpx.AsyncClient(base_url="https://example.test") as http_client:
            client = PrimoClient(http_client, _config())
            with pytest.raises(
                PrimoAPIError, match=r"Use one of: rank, date, oldest, title, author\."
            ):
                await client.search("hydrodynamics", sort_by="nonsense_sort")

    async def test_coded_facet_values_accept_the_landscape_labels(self):
        # The result landscape prints rtype "review_article" as "review
        # article" and tlevel "online_resources" as "online"; a value copied
        # from it must still filter instead of silently matching nothing.
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await client.search(
                "fluid dynamics",
                scope="catalogue",
                facet_filters={"topic": "Fluid Dynamics", "availability": "online"},
                facet_exclusions={"rtype": "review article"},
            )

        params = requests[0].url.params
        assert params["qInclude"] == (
            "facet_topic,exact,Fluid Dynamics|,|facet_tlevel,exact,online_resources"
        )
        assert params["qExclude"] == "facet_rtype,exact,review_article"

    async def test_plain_query_strips_clause_separators(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await client.search("inflation;  monetary, policy")

        assert requests[0].url.params["q"] == "any,contains,inflation monetary policy"

    async def test_search_uses_documented_date_range_facet(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await client.search("Singapore", date_from="2020", date_to="2022")

        params = requests[0].url.params
        assert (
            params["qInclude"]
            == "facet_searchcreationdate,exact,[2020 TO 2022]"
        )

    async def test_search_uses_exact_year_range_for_date_from_only(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await client.search("Singapore", date_from="2020")

        params = requests[0].url.params
        assert (
            params["qInclude"]
            == "facet_searchcreationdate,exact,[2020 TO 2020]"
        )

    async def test_search_combines_date_range_with_other_filters(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await client.search(
                "Singapore",
                resource_type="articles",
                date_from="2020",
                date_to="2022",
                peer_reviewed=True,
            )

        params = requests[0].url.params
        assert params["qInclude"] == (
            "facet_rtype,exact,articles|,|"
            "facet_searchcreationdate,exact,[2020 TO 2022]|,|"
            "facet_tlevel,exact,peer_reviewed"
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"field": "badfield"},
            {"sort_by": "recently"},
            {"resource_type": "podcast"},
            {"date_from": "20XX"},
            {"date_to": "2022"},
            {"date_from": "2024", "date_to": "2020"},
        ],
    )
    async def test_invalid_search_parameters_do_not_make_request(self, kwargs):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            with pytest.raises(PrimoAPIError):
                await client.search("Singapore", **kwargs)

        assert requests == []


class TestGetRecord:
    def _alma_doc(self) -> dict:
        return {
            "pnx": {
                "control": {"recordid": ["alma99317560802601"]},
                "display": {"title": ["Anyuan"], "type": ["book"]},
            }
        }

    async def test_get_record_resolves_prefixed_alma_id_with_numeric_lookup(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if "guestJwt" in request.url.path or "/pnxs/" in request.url.path:
                return httpx.Response(404)
            requests.append(request)
            q = request.url.params["q"]
            if q == "any,contains,99317560802601":
                return httpx.Response(
                    200,
                    json={"info": {"total": 1}, "docs": [self._alma_doc()]},
                )
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            record = await client.get_record("alma99317560802601")

        assert record is not None
        assert record.record_id == "alma99317560802601"
        assert requests[0].url.params["scope"] == "MyInstitution"
        assert requests[1].url.params["q"] == "any,contains,99317560802601"

    async def test_get_record_resolves_numeric_alma_id(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if "guestJwt" in request.url.path or "/pnxs/" in request.url.path:
                return httpx.Response(404)
            q = request.url.params["q"]
            if q == "any,contains,99317560802601":
                return httpx.Response(
                    200,
                    json={"info": {"total": 1}, "docs": [self._alma_doc()]},
                )
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            record = await client.get_record("99317560802601")

        assert record is not None
        assert record.record_id == "alma99317560802601"


def _fake_jwt(exp_offset: int = 3600) -> str:
    import base64 as _b64
    import json as _json
    import time as _time

    payload = _json.dumps({"exp": int(_time.time()) + exp_offset}).encode()
    seg = _b64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    return f"header.{seg}.sig"


class TestGetRecordDirect:
    def _direct_doc(self) -> dict:
        return {
            "context": "L",
            "pnx": {
                "control": {"recordid": ["alma99317560802601"]},
                "display": {"title": ["Anyuan"], "type": ["book"]},
            },
            "delivery": {
                "deliveryCategory": ["Alma-P"],
                "availability": ["available_in_library"],
            },
        }

    async def test_direct_lookup_uses_guest_jwt_and_skips_search(self):
        requests: list[httpx.Request] = []
        token = _fake_jwt()

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if "guestJwt" in request.url.path:
                return httpx.Response(200, json=token)
            if request.url.path.endswith("/pnxs/L/alma99317560802601"):
                assert request.headers["Authorization"] == f"Bearer {token}"
                return httpx.Response(200, json=self._direct_doc())
            raise AssertionError(f"unexpected request: {request.url}")

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            record = await client.get_record("alma99317560802601")

        assert record is not None
        assert record.record_id == "alma99317560802601"
        assert record.delivery_category == "Alma-P"
        assert len(requests) == 2

    async def test_direct_lookup_url_encodes_record_id_path_segment(self):
        token = _fake_jwt()
        record_id = "cdi/example id:10.123/a b"

        def handler(request: httpx.Request) -> httpx.Response:
            if "guestJwt" in request.url.path:
                return httpx.Response(200, json=token)
            if "/pnxs/" in request.url.path:
                assert (
                    b"/pnxs/PC/cdi%2Fexample%20id%3A10.123%2Fa%20b"
                    in request.url.raw_path
                )
                return httpx.Response(
                    200,
                    json={
                        "context": "PC",
                        "pnx": {
                            "control": {"recordid": [record_id]},
                            "display": {"title": ["Remote"], "type": ["article"]},
                        },
                    },
                )
            raise AssertionError(f"unexpected request: {request.url}")

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            record = await client.get_record(record_id)

        assert record is not None
        assert record.record_id == record_id

    async def test_direct_lookup_refreshes_jwt_on_403(self):
        stale, fresh = _fake_jwt(3600), _fake_jwt(7200)
        issued: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if "guestJwt" in request.url.path:
                token = stale if not issued else fresh
                issued.append(token)
                return httpx.Response(200, json=token)
            auth = request.headers.get("Authorization", "")
            if auth == f"Bearer {stale}":
                return httpx.Response(403)
            return httpx.Response(200, json=self._direct_doc())

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            record = await client.get_record("alma99317560802601")

        assert record is not None
        assert issued == [stale, fresh]

    async def test_falls_back_to_search_when_jwt_unavailable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if "guestJwt" in request.url.path:
                return httpx.Response(500)
            if request.url.path.endswith("/pnxs"):
                q = request.url.params["q"]
                if "99317560802601" in q:
                    return httpx.Response(
                        200,
                        json={
                            "info": {"total": 1},
                            "docs": [
                                {
                                    "pnx": {
                                        "control": {
                                            "recordid": ["alma99317560802601"]
                                        },
                                        "display": {
                                            "title": ["Anyuan"],
                                            "type": ["book"],
                                        },
                                    }
                                }
                            ],
                        },
                    )
                return _empty_response()
            raise AssertionError(f"unexpected request: {request.url}")

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            record = await client.get_record("alma99317560802601")

        assert record is not None
        assert record.record_id == "alma99317560802601"

    @pytest.mark.parametrize(
        "direct_response",
        [
            httpx.Response(200, text="not-json"),
            httpx.Response(200, json={"pnx": "malformed"}),
        ],
    )
    async def test_falls_back_to_search_when_direct_response_is_malformed(
        self, direct_response: httpx.Response
    ):
        token = _fake_jwt()

        def handler(request: httpx.Request) -> httpx.Response:
            if "guestJwt" in request.url.path:
                return httpx.Response(200, json=token)
            if "/pnxs/" in request.url.path:
                return direct_response
            if request.url.path.endswith("/pnxs"):
                q = request.url.params["q"]
                if "99317560802601" in q:
                    return httpx.Response(
                        200,
                        json={
                            "info": {"total": 1},
                            "docs": [self._direct_doc()],
                        },
                    )
                return _empty_response()
            raise AssertionError(f"unexpected request: {request.url}")

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            record = await client.get_record("alma99317560802601")

        assert record is not None
        assert record.record_id == "alma99317560802601"

    async def test_direct_mismatch_returns_none_not_wrong_record(self):
        token = _fake_jwt()

        def handler(request: httpx.Request) -> httpx.Response:
            if "guestJwt" in request.url.path:
                return httpx.Response(200, json=token)
            if "/pnxs/" in request.url.path:
                wrong = self._direct_doc()
                wrong["pnx"]["control"]["recordid"] = ["alma990000000000001"]
                return httpx.Response(200, json=wrong)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            record = await client.get_record("alma99317560802601")

        assert record is None


class TestPcAvailability:
    """pcAvailability must be controllable, not hardcoded to true."""

    @staticmethod
    async def _search_params(config: PrimoConfig, **kwargs) -> httpx.QueryParams:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, config)
            await client.search("Singapore", **kwargs)
        return requests[0].url.params

    async def test_default_excludes_unavailable(self):
        params = await self._search_params(_config())
        assert params["pcAvailability"] == "false"

    async def test_explicit_true_includes_unavailable(self):
        params = await self._search_params(_config(), include_unavailable=True)
        assert params["pcAvailability"] == "true"

    async def test_explicit_false_overrides_config_default(self):
        config = _config()
        config.include_unavailable = True
        params = await self._search_params(config, include_unavailable=False)
        assert params["pcAvailability"] == "false"

    async def test_none_falls_back_to_config_default(self):
        config = _config()
        config.include_unavailable = True
        params = await self._search_params(config, include_unavailable=None)
        assert params["pcAvailability"] == "true"


def _search_payload() -> dict:
    return {
        "info": {"total": 1},
        "docs": [
            {
                "pnx": {
                    "control": {"recordid": ["alma1"]},
                    "display": {"title": ["A title"]},
                }
            }
        ],
    }


_FACETS_PAYLOAD = {
    "facets": [
        {"name": "rtype", "values": [{"value": "articles", "count": "42"}]}
    ]
}


class TestSearchFacets:
    async def _run_search(self, handler, **kwargs):
        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            return await client.search("Singapore", **kwargs)

    async def test_search_fetches_facets_with_same_query(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            return httpx.Response(200, json=_search_payload())

        response = await self._run_search(handler)

        assert [r.url.path for r in requests] == [
            "/primaws/rest/pub/pnxs",
            "/primaws/rest/pub/facets",
        ]
        # The /facets endpoint returns facets for the query the session just
        # ran, so the parameters must match the /pnxs request.
        assert requests[1].url.params["q"] == requests[0].url.params["q"]
        assert requests[1].url.params["tab"] == requests[0].url.params["tab"]
        assert [(f.name, f.values[0].count) for f in response.facets] == [
            ("rtype", 42)
        ]

    async def test_concurrent_searches_do_not_interleave_with_facets(self):
        """/facets reads the session's last search, so pairs must not mix."""
        import asyncio

        order: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            order.append(f"{request.url.path.rsplit('/', 1)[-1]}:{request.url.params['q']}")
            await asyncio.sleep(0)
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            return httpx.Response(200, json=_search_payload())

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await asyncio.gather(client.search("alpha"), client.search("beta"))

        assert order in (
            ["pnxs:any,contains,alpha", "facets:any,contains,alpha",
             "pnxs:any,contains,beta", "facets:any,contains,beta"],
            ["pnxs:any,contains,beta", "facets:any,contains,beta",
             "pnxs:any,contains,alpha", "facets:any,contains,alpha"],
        )

    async def test_empty_facets_for_large_search_are_retried_once(self, monkeypatch):
        # Primo can answer /facets with an empty list while it is still
        # computing facets for a large result set.
        monkeypatch.setattr(PrimoClient, "_FACETS_RETRY_DELAY_SECONDS", 0.0)
        facet_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal facet_calls
            if request.url.path.endswith("/facets"):
                facet_calls += 1
                payload = {"facets": []} if facet_calls == 1 else _FACETS_PAYLOAD
                return httpx.Response(200, json=payload)
            payload = _search_payload()
            payload["info"]["total"] = 5_000_000
            return httpx.Response(200, json=payload)

        response = await self._run_search(handler)

        assert facet_calls == 2
        assert [f.name for f in response.facets] == ["rtype"]

    async def test_empty_facets_for_small_search_are_not_retried(self, monkeypatch):
        # Scopes that serve no facets at all must not pay the retry delay.
        monkeypatch.setattr(PrimoClient, "_FACETS_RETRY_DELAY_SECONDS", 0.0)
        facet_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal facet_calls
            if request.url.path.endswith("/facets"):
                facet_calls += 1
                return httpx.Response(200, json={"facets": []})
            return httpx.Response(200, json=_search_payload())  # total 1

        response = await self._run_search(handler)

        assert facet_calls == 1
        assert response.facets == []

    async def test_facets_failure_degrades_to_no_facets(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/facets"):
                return httpx.Response(500)
            return httpx.Response(200, json=_search_payload())

        response = await self._run_search(handler)
        assert response.records
        assert response.facets == []

    async def test_no_facets_request_for_empty_results(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        response = await self._run_search(handler)
        assert [r.url.path for r in requests] == ["/primaws/rest/pub/pnxs"]
        assert response.facets == []

    async def test_include_facets_false_skips_facets_request(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=_search_payload())

        response = await self._run_search(handler, include_facets=False)
        assert [r.url.path for r in requests] == ["/primaws/rest/pub/pnxs"]
        assert response.facets == []

    async def test_config_default_can_disable_facets(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=_search_payload())

        config = _config()
        config.search_facets = False
        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, config)
            response = await client.search("Singapore")

        assert [r.url.path for r in requests] == ["/primaws/rest/pub/pnxs"]
        assert response.facets == []


def _search_doc(record_id: str) -> dict:
    return {
        "pnx": {
            "control": {"recordid": [record_id]},
            "display": {"title": [f"Title {record_id}"]},
        }
    }


def _pc_payload(total_pc: int, record_id: str) -> dict:
    """A one-record search payload with Primo's article-index (PC) count."""
    payload = _search_payload()
    payload["info"].update({"totalResultsLocal": 1, "totalResultsPC": total_pc})
    payload["docs"][0]["pnx"]["control"]["recordid"] = [record_id]
    return payload


class TestArticleIndexRetry:
    """Primo answers before CDI has finished when CDI is slow (PC == -1)."""

    async def _run(self, handler, monkeypatch, **kwargs):
        monkeypatch.setattr(PrimoClient, "_ARTICLE_INDEX_RETRY_DELAY_SECONDS", 0.0)
        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            return await client.search("climate change", **kwargs)

    async def test_combined_scope_repeats_until_article_index_answers(self, monkeypatch):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            pnxs_calls = sum(r.url.path.endswith("/pnxs") for r in requests)
            if pnxs_calls == 1:
                return httpx.Response(200, json=_pc_payload(-1, "alma1"))
            return httpx.Response(200, json=_pc_payload(42, "cdi_1"))

        response = await self._run(handler, monkeypatch)

        # The repeat is the identical search, and facets follow the final one.
        assert [r.url.path.rsplit("/", 1)[-1] for r in requests] == ["pnxs", "pnxs", "facets"]
        assert requests[1].url.params == requests[0].url.params
        assert response.info.total_pc == 42
        assert [r.record_id for r in response.records] == ["cdi_1"]
        assert response.article_index_incomplete is False

    async def test_flags_incomplete_when_article_index_never_answers(self, monkeypatch):
        pnxs_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal pnxs_calls
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            pnxs_calls += 1
            return httpx.Response(200, json=_pc_payload(-1, "alma1"))

        response = await self._run(handler, monkeypatch)

        assert pnxs_calls == 1 + PrimoClient._ARTICLE_INDEX_RETRIES
        assert response.article_index_incomplete is True
        assert [r.record_id for r in response.records] == ["alma1"]

    @pytest.mark.parametrize("sequence", [[-1, 0, 0], [-1, -1, 0, 0]])
    async def test_zero_after_a_timeout_is_not_trusted(self, monkeypatch, sequence):
        # When CDI fails outright Primo caches the failed part as 0; seen
        # live as -1, -1, 0 for topics with thousands of articles. The zero
        # is re-checked without the cache (last reply), and a zero that
        # still follows a timeout is not taken as "no articles".
        replies = iter(sequence)
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            return httpx.Response(200, json=_pc_payload(next(replies), "alma1"))

        response = await self._run(handler, monkeypatch)

        pnxs = [r for r in requests if r.url.path.endswith("/pnxs")]
        assert len(pnxs) == len(sequence)
        assert pnxs[-1].url.params["disableCache"] == "true"
        assert response.article_index_incomplete is True

    async def test_zero_after_a_timeout_recovers_when_uncached_search_finds_articles(
        self, monkeypatch
    ):
        replies = iter([-1, 0, 7])

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            pc = next(replies)
            return httpx.Response(200, json=_pc_payload(pc, "cdi_1" if pc > 0 else "alma1"))

        response = await self._run(handler, monkeypatch)

        assert response.info.total_pc == 7
        assert [r.record_id for r in response.records] == ["cdi_1"]
        assert response.article_index_incomplete is False

    async def test_zero_is_rechecked_with_an_uncached_search(self, monkeypatch):
        # A repeat of a search whose article index failed earlier is answered
        # straight from Primo's cache with the failure stored as 0, with no -1
        # in the same call. Only an uncached search can tell that apart from
        # a real zero (in the first test report, disableCache=true found 87
        # articles where the cached request had returned none).
        replies = iter([0, 42])
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            pc = next(replies)
            return httpx.Response(200, json=_pc_payload(pc, "cdi_1" if pc > 0 else "alma1"))

        response = await self._run(handler, monkeypatch)

        first, check, facets = requests
        assert "disableCache" not in first.url.params
        assert check.url.params["disableCache"] == "true"
        assert {k: v for k, v in check.url.params.items() if k != "disableCache"} == dict(
            first.url.params
        )
        # Facets describe the search that produced the final records.
        assert facets.url.path.endswith("/facets")
        assert facets.url.params == check.url.params
        assert response.info.total_pc == 42
        assert [r.record_id for r in response.records] == ["cdi_1"]
        assert response.article_index_incomplete is False

    async def test_zero_confirmed_by_an_uncached_search_is_trusted(self, monkeypatch):
        replies = iter([0, 0])
        pnxs_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal pnxs_calls
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            pnxs_calls += 1
            return httpx.Response(200, json=_pc_payload(next(replies), "alma1"))

        response = await self._run(handler, monkeypatch)

        assert pnxs_calls == 2
        assert response.article_index_incomplete is False

    async def test_unreported_article_index_count_is_not_rechecked(self, monkeypatch):
        # Primo reports totalResultsPC on every combined-scope search; a reply
        # without it says nothing about the article index, so it is neither
        # "no articles" nor worth an uncached repeat.
        pnxs_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal pnxs_calls
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            pnxs_calls += 1
            return httpx.Response(200, json=_search_payload())

        response = await self._run(handler, monkeypatch)

        assert pnxs_calls == 1
        assert response.article_index_incomplete is False

    async def test_slow_article_index_is_logged_with_primo_search_times(
        self, monkeypatch, caplog
    ):
        # No failed reply has been captured yet; Primo's own timelog says how
        # long the article-index part took, so log it to settle, next time
        # the index fails, how a cached failure looks.
        replies = iter([(-1, "5012"), (42, "210")])

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            pc, ms = next(replies)
            payload = _pc_payload(pc, "cdi_1")
            payload["timelog"] = {"PC_SEARCH_TIME_TOTAL": ms}
            return httpx.Response(200, json=payload)

        with caplog.at_level("INFO", logger="primo_mcp_server.client"):
            await self._run(handler, monkeypatch)

        message = next(r.getMessage() for r in caplog.records if "article index" in r.getMessage())
        assert "totalResultsPC [-1, 42]" in message
        assert "[5012, 210]" in message

    async def test_cached_zero_with_a_failing_article_index_is_flagged(self, monkeypatch):
        replies = iter([0, -1])

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            return httpx.Response(200, json=_pc_payload(next(replies), "alma1"))

        response = await self._run(handler, monkeypatch)

        assert response.article_index_incomplete is True

    @pytest.mark.parametrize("scope", ["catalogue", "books_videos"])
    async def test_local_only_scopes_never_retry(self, monkeypatch, scope):
        # Scopes without the article index always report totalResultsPC -1.
        pnxs_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal pnxs_calls
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            pnxs_calls += 1
            return httpx.Response(200, json=_pc_payload(-1, "alma1"))

        response = await self._run(handler, monkeypatch, scope=scope)

        assert pnxs_calls == 1
        assert response.article_index_incomplete is False

    async def test_answered_article_index_is_not_retried(self, monkeypatch):
        pnxs_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal pnxs_calls
            if request.url.path.endswith("/facets"):
                return httpx.Response(200, json=_FACETS_PAYLOAD)
            pnxs_calls += 1
            return httpx.Response(200, json=_pc_payload(5, "cdi_1"))

        response = await self._run(handler, monkeypatch)

        assert pnxs_calls == 1
        assert response.article_index_incomplete is False


class TestGetRecords:
    def _http_client(self, handler) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        )

    async def test_preserves_input_order_and_drops_missing_ids(self):
        import asyncio

        async def handler(request: httpx.Request) -> httpx.Response:
            if "guestJwt" in request.url.path or "/pnxs/" in request.url.path:
                return httpx.Response(404)
            rid = request.url.params["q"].rsplit(",", 1)[-1]
            if rid == "cdi_slow":
                # The slowest lookup is the FIRST id; order must still hold.
                await asyncio.sleep(0.05)
                return httpx.Response(
                    200, json={"info": {"total": 1}, "docs": [_search_doc(rid)]}
                )
            if rid == "cdi_fast":
                return httpx.Response(
                    200, json={"info": {"total": 1}, "docs": [_search_doc(rid)]}
                )
            return _empty_response()

        async with self._http_client(handler) as http_client:
            client = PrimoClient(http_client, _config())
            records = await client.get_records(
                ["cdi_slow", "cdi_missing", "cdi_fast"]
            )

        assert [r.record_id for r in records] == ["cdi_slow", "cdi_fast"]

    async def test_lookup_records_keeps_a_slot_for_each_missing_id(self):
        # Callers need to know WHICH ids failed, so primo_cite and
        # primo_export can say so instead of silently omitting them.
        async def handler(request: httpx.Request) -> httpx.Response:
            if "guestJwt" in request.url.path or "/pnxs/" in request.url.path:
                return httpx.Response(404)
            rid = request.url.params["q"].rsplit(",", 1)[-1]
            if rid == "cdi_missing":
                return _empty_response()
            return httpx.Response(
                200, json={"info": {"total": 1}, "docs": [_search_doc(rid)]}
            )

        async with self._http_client(handler) as http_client:
            client = PrimoClient(http_client, _config())
            records = await client.lookup_records(["cdi_a", "cdi_missing", "cdi_b"])

        assert [r.record_id if r else None for r in records] == ["cdi_a", None, "cdi_b"]

    async def test_lookups_overlap_instead_of_running_sequentially(self):
        import asyncio

        inflight = 0
        max_inflight = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal inflight, max_inflight
            if "guestJwt" in request.url.path or "/pnxs/" in request.url.path:
                return httpx.Response(404)
            inflight += 1
            max_inflight = max(max_inflight, inflight)
            await asyncio.sleep(0.02)
            inflight -= 1
            rid = request.url.params["q"].rsplit(",", 1)[-1]
            return httpx.Response(
                200, json={"info": {"total": 1}, "docs": [_search_doc(rid)]}
            )

        async with self._http_client(handler) as http_client:
            client = PrimoClient(http_client, _config())
            records = await client.get_records(["cdi_a", "cdi_b", "cdi_c"])

        assert len(records) == 3
        assert max_inflight > 1

    async def test_propagates_lookup_errors_after_all_settle(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            if "guestJwt" in request.url.path or "/pnxs/" in request.url.path:
                return httpx.Response(404)
            rid = request.url.params["q"].rsplit(",", 1)[-1]
            if rid == "cdi_bad":
                return httpx.Response(500)
            return httpx.Response(
                200, json={"info": {"total": 1}, "docs": [_search_doc(rid)]}
            )

        async with self._http_client(handler) as http_client:
            client = PrimoClient(http_client, _config())
            with pytest.raises(PrimoAPIError):
                await client.get_records(["cdi_good", "cdi_bad"])

    async def test_concurrent_lookups_share_one_guest_jwt_fetch(self):
        token = _fake_jwt()
        jwt_calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal jwt_calls
            if "guestJwt" in request.url.path:
                jwt_calls += 1
                return httpx.Response(200, json=token)
            if "/pnxs/" in request.url.path:
                rid = request.url.path.rsplit("/", 1)[-1]
                return httpx.Response(
                    200,
                    json={
                        "context": "PC",
                        "pnx": {
                            "control": {"recordid": [rid]},
                            "display": {"title": [f"Title {rid}"]},
                        },
                    },
                )
            raise AssertionError(f"unexpected request: {request.url}")

        async with self._http_client(handler) as http_client:
            client = PrimoClient(http_client, _config())
            records = await client.get_records(["cdi_a", "cdi_b", "cdi_c"])

        assert [r.record_id for r in records] == ["cdi_a", "cdi_b", "cdi_c"]
        assert jwt_calls == 1


class TestSearchClauses:
    async def _search(self, handler, **kwargs):
        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            return await client.search("summary text", **kwargs)

    async def test_clauses_compile_to_multi_clause_q(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        await self._search(
            handler,
            clauses=[
                {"field": "title", "value": "capital", "connector": "AND"},
                {"field": "creator", "value": "piketty"},
            ],
        )

        assert requests[0].url.params["q"] == (
            "title,contains,capital,AND;creator,contains,piketty"
        )

    async def test_clause_aliases_and_value_sanitisation(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        await self._search(
            handler,
            clauses=[
                {
                    "field": "author",
                    "operator": "equals",
                    "value": "Piketty, Thomas; economist",
                    "connector": "or",
                },
                # Trailing connector on the last clause is ignored.
                {"value": "wealth", "connector": "NOT"},
            ],
        )

        assert requests[0].url.params["q"] == (
            "creator,exact,Piketty Thomas economist,OR;any,contains,wealth"
        )

    async def test_invalid_clause_operator_makes_no_request(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        with pytest.raises(PrimoAPIError, match="Invalid operator"):
            await self._search(
                handler,
                clauses=[{"value": "capital", "operator": "fuzzy"}],
            )
        assert requests == []

    async def test_empty_clause_value_makes_no_request(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        with pytest.raises(PrimoAPIError, match="empty value"):
            await self._search(handler, clauses=[{"value": " ,; "}])
        assert requests == []


class TestFacetFilters:
    async def _search_params(self, **kwargs) -> httpx.QueryParams:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await client.search("Singapore", **kwargs)

        return requests[0].url.params

    async def test_facet_filters_compile_into_qinclude(self):
        params = await self._search_params(
            facet_filters={"topic": "Economics", "language": "eng"}
        )
        assert params["qInclude"] == (
            "facet_topic,exact,Economics|,|facet_lang,exact,eng"
        )

    async def test_facet_name_aliases_and_prefix_are_normalised(self):
        params = await self._search_params(
            facet_filters={"subject": "Economics", "facet_jtitle": "Nature"}
        )
        assert params["qInclude"] == (
            "facet_topic,exact,Economics|,|facet_jtitle,exact,Nature"
        )

    async def test_facet_filters_append_after_dedicated_filters(self):
        params = await self._search_params(
            resource_type="articles",
            peer_reviewed=True,
            facet_filters={"topic": "Corporate governance"},
        )
        assert params["qInclude"] == (
            "facet_rtype,exact,articles|,|"
            "facet_tlevel,exact,peer_reviewed|,|"
            "facet_topic,exact,Corporate governance"
        )

    async def test_facet_exclusions_compile_into_qexclude(self):
        params = await self._search_params(
            facet_exclusions={"rtype": "reviews"}
        )
        assert params["qExclude"] == "facet_rtype,exact,reviews"
        assert "qInclude" not in params

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"facet_filters": {"bad name!": "x"}},
            {"facet_filters": {"topic": "   "}},
            {"facet_exclusions": {"": "x"}},
        ],
    )
    async def test_invalid_facet_filters_do_not_make_request(self, kwargs):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            with pytest.raises(PrimoAPIError):
                await client.search("Singapore", **kwargs)

        assert requests == []


class TestTransientRetries:
    """Timeouts, connection failures, and HTTP 429/5xx retry once by default."""

    def _sleep_recorder(self, monkeypatch) -> list[float]:
        import asyncio as _asyncio

        delays: list[float] = []

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        monkeypatch.setattr(_asyncio, "sleep", fake_sleep)
        return delays

    async def _run_search(self, handler, config: PrimoConfig | None = None):
        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, config or _config())
            return await client.search("Singapore")

    async def test_429_is_retried_honouring_retry_after(self, monkeypatch):
        delays = self._sleep_recorder(monkeypatch)
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) == 1:
                return httpx.Response(429, headers={"Retry-After": "2"})
            return _empty_response()

        response = await self._run_search(handler)

        assert len(calls) == 2
        assert delays == [2.0]
        assert response.total_results == 0

    async def test_retry_after_is_capped_at_configured_max(self, monkeypatch):
        delays = self._sleep_recorder(monkeypatch)
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) == 1:
                return httpx.Response(503, headers={"Retry-After": "300"})
            return _empty_response()

        await self._run_search(handler)

        assert delays == [_config().request_retry_max_delay]

    async def test_timeout_is_retried(self, monkeypatch):
        delays = self._sleep_recorder(monkeypatch)
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) == 1:
                raise httpx.ReadTimeout("slow", request=request)
            return _empty_response()

        response = await self._run_search(handler)

        assert len(calls) == 2
        assert delays == [0.5]
        assert response.total_results == 0

    async def test_mid_request_connection_reset_is_retried(self, monkeypatch):
        delays = self._sleep_recorder(monkeypatch)
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) == 1:
                raise httpx.ReadError("reset", request=request)
            return _empty_response()

        response = await self._run_search(handler)

        assert len(calls) == 2
        assert delays == [0.5]
        assert response.total_results == 0

    async def test_400_is_not_retried(self, monkeypatch):
        delays = self._sleep_recorder(monkeypatch)
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(400)

        with pytest.raises(PrimoAPIError) as exc_info:
            await self._run_search(handler)

        assert exc_info.value.status_code == 400
        assert len(calls) == 1
        assert delays == []

    async def test_exhausted_retries_raise_the_transient_error(self, monkeypatch):
        self._sleep_recorder(monkeypatch)
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(503)

        with pytest.raises(PrimoAPIError) as exc_info:
            await self._run_search(handler)

        assert exc_info.value.status_code == 503
        assert len(calls) == 2  # initial attempt + default single retry

    async def test_zero_attempts_disables_retries(self, monkeypatch):
        delays = self._sleep_recorder(monkeypatch)
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(503)

        config = _config().model_copy(update={"request_retry_attempts": 0})
        with pytest.raises(PrimoAPIError):
            await self._run_search(handler, config=config)

        assert len(calls) == 1
        assert delays == []
