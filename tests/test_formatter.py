"""Tests for result formatting."""

from urllib.parse import parse_qs, urlparse

import pytest

from primo_mcp_server.config import PrimoConfig
from primo_mcp_server.formatter import (
    _format_availability,
    build_record_url,
    build_search_url,
    format_record_detail,
    format_search_results,
    format_suggestions,
    record_link,
)
from primo_mcp_server.models import (
    AccessLink,
    Facet,
    FacetValue,
    InstitutionAvailability,
    PrimoRecord,
    SearchResponse,
)


def _smu_config(**overrides) -> PrimoConfig:
    # A complete SMU fixture: the package defaults are now Towson's, so the
    # tab and scope names are pinned here rather than inherited.
    values = {
        "base_url": "https://search.library.smu.edu.sg/primaws/rest/pub",
        "discovery_base_url": None,
        "vid": "65SMU_INST:SMU_NUI",
        "language": "en",
        "tab_everything": "Everything",
        "tab_catalogue": "Catalogue",
        "tab_books_videos": "booksandvideos",
        "scope_combined": "MyInst_and_CI",
        "scope_local": "MyInstitution",
        "scope_books_videos": "BooksVideos",
    }
    values.update(overrides)
    return PrimoConfig(**values)


class TestFormatSearchResults:
    def test_formats_results(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = format_search_results(response, "entrepreneurship innovation")
        assert "entrepreneurship innovation" in output
        assert "[1]" in output
        assert "[2]" in output
        assert "[3]" in output

    def test_empty_results_message(self, empty_results_data):
        response = SearchResponse.from_api_response(empty_results_data)
        output = format_search_results(response, "xyzzyplugh99999", config=_smu_config())
        assert "No results found" in output
        assert "Queries attempted:" in output
        assert "- No results: [any,contains,xyzzyplugh99999](" in output
        assert "Suggestions" in output
        assert "Iterative search guidance:" in output
        assert "Try up to five total attempts" in output
        assert "start retries with catalogue databases" in output
        assert 'resource_type="databases"' in output
        assert "direct searches for likely database names" in output
        assert "OR queries for close alternatives" in output
        assert "combine all relevant results found across attempts" in output
        assert output.index("Queries attempted:") < output.index("Suggestions")

    def test_queries_attempted_block_survives_a_missing_search_url(
        self, search_results_data
    ):
        """Without config there is no link, but the attempt still gets reported."""
        response = SearchResponse.from_api_response(search_results_data)
        output = format_search_results(response, "test")

        assert output.startswith("## Required search transparency")
        assert "Queries attempted:" in output
        assert "- Results found: any,contains,test --" in output
        assert "http" not in output.split("[1]")[0]

    def test_queries_attempted_reports_the_full_total_not_the_page_size(self):
        """The count is Primo's total, not the handful of records shown."""
        response = SearchResponse.model_validate(
            {
                "info": {"total": 1234},
                "records": [{"record_id": "alma1", "title": "Only shown record"}],
            }
        )
        output = format_search_results(response, "inflation", config=_smu_config())

        assert "- Results found: [any,contains,inflation](" in output
        assert "-- 1,234 results" in output

    def test_contains_record_ids(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = format_search_results(response, "test")
        assert "Record ID:" in output

    def test_contains_total_count(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = format_search_results(response, "test")
        assert "Found" in output
        assert "results" in output

    def test_formats_results_without_query_argument_still_links_search(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = format_search_results(response, config=_smu_config())
        assert "Found" in output
        assert "Queries attempted:" in output
        assert "- Results found: [any,contains,](" in output

    def test_keeps_plain_titles_without_config(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        record = response.records[0]
        output = format_search_results(response, "test")

        assert f"[1] {record.title}" in output
        assert f"[1] [{record.title}](" not in output

    def test_links_search_result_titles(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        record = response.records[0]
        output = format_search_results(response, "test", config=_smu_config())

        assert "Queries attempted:" in output
        assert "- Results found: [any,contains,test](" in output
        assert output.index("Queries attempted:") < output.index("[1]")
        assert f"[1] [{record.title}](" in output
        assert "Berger, Elisabeth S.C." in output
        assert "| 2021 | Article" in output
        assert "Availability:" in output
        assert f"Record ID: {record.record_id}" in output

    def test_query_link_uses_normalised_field_alias(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = format_search_results(
            response,
            "corporate governance",
            config=_smu_config(),
            field="subject",
        )

        assert "- Results found: [sub,contains,corporate governance](" in output

    def test_result_options_include_relevance_metadata(self):
        record = PrimoRecord(
            record_id="alma99908902601",
            title="Social Services Abstracts.",
            resource_type="database",
            subjects=["Social Sciences", "Sociology", "Volunteering", "Singapore"],
            keywords=["Nonprofit organisations", "Community service"],
            language="eng",
            source_label="Alma",
            delivery_category="Alma-E",
        )
        response = SearchResponse.model_validate(
            {"info": {"total": 1}, "records": [record]}
        )

        output = format_search_results(response, "volunteer", config=_smu_config())

        assert "Subjects: Social Sciences; Sociology; Volunteering; Singapore" in output
        assert "Keywords: Nonprofit organisations; Community service" in output
        assert "Language: eng | Source: Alma" in output
        assert "Availability: Electronic resource: check availability in OneSearch" in output
        assert "Record ID: alma99908902601" in output

    def test_article_number_shows_as_article_not_pages(self):
        # Computers & Fluids files the article number as artnum and spage.
        record = PrimoRecord(
            record_id="cdi_crossref_citationtrail_10_1016_j_compfluid_2020_104786",
            title="T",
            context="PC",
            journal_title="Computers & Fluids",
            volume="214",
            start_page="104786",
            article_number="104786",
        )
        response = SearchResponse.model_validate({"info": {"total": 1}, "records": [record]})

        output = format_search_results(response, "isogeometric", config=_smu_config())
        detail = format_record_detail(record, _smu_config())

        assert "Computers & Fluids, 214, article 104786" in output
        assert "Journal: Computers & Fluids, vol. 214, article 104786" in detail
        assert "pp. 104786" not in output + detail

    def test_quoted_query_is_not_quoted_twice(self):
        record = PrimoRecord(record_id="cdi_1", title="T", context="PC")
        found = SearchResponse.model_validate({"info": {"total": 4}, "records": [record]})
        none = SearchResponse.model_validate({"info": {"total": 0}, "records": []})

        hit = format_search_results(found, '"active compound particle"', config=_smu_config())
        miss = format_search_results(none, '"active compound particle"', config=_smu_config())

        assert 'Found 4 results for "active compound particle" (showing' in hit
        assert 'No results found for "active compound particle".' in miss
        assert '""' not in hit + miss

    def test_queries_attempted_link_carries_facet_filters(self):
        record = PrimoRecord(record_id="cdi_1", title="T", context="PC")
        response = SearchResponse.model_validate({"info": {"total": 1}, "records": [record]})

        output = format_search_results(
            response,
            "fluid dynamics",
            config=_smu_config(),
            facet_filters={"topic": "Physics"},
            facet_exclusions={"rtype": "reviews"},
        )

        assert "facet=topic%2Cinclude%2CPhysics" in output
        assert "facet=rtype%2Cexclude%2Creviews" in output

    def test_other_libraries_holding_the_item_are_listed(self):
        # USMAI network records Towson does not own say no_inventory at
        # Towson; almaInstitutionsList names the libraries that hold them.
        record = PrimoRecord(
            record_id="alma9910165228008236",
            title="Low Reynolds number hydrodynamics",
            context="L",
            availability=["no_inventory"],
            delivery_category="Alma-P",
            other_institutions=[
                InstitutionAvailability(
                    name="University of Maryland, College Park (UMCP)",
                    status="available_in_institution",
                ),
                InstitutionAvailability(
                    name="University of Maryland, Baltimore County (UMBC)",
                    status="unavailable_in_institution",
                ),
            ],
        )
        response = SearchResponse.model_validate({"info": {"total": 1}, "records": [record]})

        output = format_search_results(response, "hydrodynamics", config=_smu_config())

        assert "Availability: Not held here" in output
        assert "Alma-P" not in output
        assert (
            "Other libraries: University of Maryland, College Park (UMCP) (available); "
            "University of Maryland, Baltimore County (UMBC) (checked out)"
        ) in output


class TestArticleIndexIncompleteNote:
    """A slow article index must not read as "no articles exist"."""

    def test_note_when_article_index_did_not_answer(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        response.article_index_incomplete = True
        output = format_search_results(response, "climate change")
        assert "article index did not answer in time" in output
        assert "do not conclude that no articles exist" in output
        # It sits in the header, before the first record.
        assert output.index("article index did not answer") < output.index("[1]")

    def test_note_on_zero_results_too(self, empty_results_data):
        response = SearchResponse.from_api_response(empty_results_data)
        response.article_index_incomplete = True
        output = format_search_results(response, "compound particle")
        assert "No results found" in output
        assert "article index did not answer in time" in output

    def test_no_note_by_default(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = format_search_results(response, "climate change")
        assert "article index did not answer" not in output


class TestFormatRecordDetail:
    def test_formats_detail(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = format_record_detail(response.records[0])
        assert "Title:" in output
        assert "Author(s):" in output
        assert "Year:" in output
        assert "Type:" in output
        assert "Record ID:" in output

    def test_includes_doi(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        record = response.records[0]
        if record.doi:
            output = format_record_detail(record)
            assert "DOI:" in output

    def test_links_detail_title(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        record = response.records[0]
        output = format_record_detail(record, config=_smu_config())

        assert f"Title: [{record.title}](" in output
        assert "Author(s):" in output
        assert f"Record ID: {record.record_id}" in output

    def test_preserves_chinese_record_text(self):
        title = "\u5b89\u6e90 : \u767c\u6398\u4e2d\u570b\u9769\u547d\u4e4b\u50b3\u7d71."
        author = "\u88f4, \u5b9c\u7406."
        record = PrimoRecord(
            record_id="alma99317560802601",
            title=title,
            resource_type="book",
            creators=[author],
            creation_date="2014",
        )
        output = format_search_results(
            SearchResponse.model_validate(
                {"info": {"total": 1}, "records": [record]}
            ),
            "\u5b89\u6e90",
            config=_smu_config(),
        )

        assert f"[{title}](" in output
        assert title in output
        assert author in output


class TestBuildRecordUrl:
    def test_alma_record_uses_local_context(self):
        record = PrimoRecord(record_id="alma99862242402601")
        url = build_record_url(record, _smu_config())
        assert url is not None

        params = parse_qs(urlparse(url).query)
        assert params["docid"] == ["alma99862242402601"]
        assert params["context"] == ["L"]

    def test_cdi_record_uses_pc_context(self):
        record = PrimoRecord(record_id="cdi_gale_onefilemisc_PPGS_A666195044")
        url = build_record_url(record, _smu_config())
        assert url is not None

        params = parse_qs(urlparse(url).query)
        assert params["docid"] == ["cdi_gale_onefilemisc_PPGS_A666195044"]
        assert params["context"] == ["PC"]

    def test_derives_discovery_base_url_from_api_base_url(self):
        record = PrimoRecord(record_id="alma99862242402601")
        url = build_record_url(record, _smu_config())
        assert url is not None

        parsed = urlparse(url)
        assert (
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            == "https://search.library.smu.edu.sg/discovery/fulldisplay"
        )

    def test_explicit_discovery_base_url_override(self):
        record = PrimoRecord(record_id="alma99862242402601")
        config = _smu_config(
            base_url="https://api.example.edu/primaws/rest/pub",
            discovery_base_url="https://catalogue.example.edu/discovery",
        )
        url = build_record_url(record, config)
        assert url is not None

        parsed = urlparse(url)
        assert (
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            == "https://catalogue.example.edu/discovery/fulldisplay"
        )

    def test_escapes_record_id_and_vid_values(self):
        record = PrimoRecord(record_id="cdi/example id:10.123/a b")
        url = build_record_url(record, _smu_config())
        assert url is not None

        assert "docid=cdi%2Fexample+id%3A10.123%2Fa+b" in url
        assert "vid=65SMU_INST%3ASMU_NUI" in url

    def test_returns_none_without_record_id(self):
        record = PrimoRecord(title="Untitled")
        assert build_record_url(record, _smu_config()) is None

    def test_record_link_alias_matches_build_record_url(self):
        record = PrimoRecord(record_id="alma99862242402601")
        config = _smu_config()
        assert record_link(record, config) == build_record_url(record, config)


class TestBuildSearchUrl:
    def test_catalogue_search_url_uses_ui_scope_params(self):
        url = build_search_url(
            "anthropic principle",
            _smu_config(),
            field="title",
            scope="catalogue",
            offset=20,
            resource_type="books",
        )
        assert url is not None

        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert (
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            == "https://search.library.smu.edu.sg/discovery/search"
        )
        assert params["query"] == ["title,contains,anthropic principle"]
        assert params["tab"] == ["Catalogue"]
        assert params["search_scope"] == ["MyInstitution"]
        assert params["vid"] == ["65SMU_INST:SMU_NUI"]
        assert params["offset"] == ["20"]
        assert params["pcAvailability"] == ["false"]
        assert params["facet"] == ["rtype,include,books"]

    def test_search_url_can_include_unavailable_records(self):
        url = build_search_url(
            "audit fees",
            _smu_config(),
            include_unavailable=True,
        )
        assert url is not None

        params = parse_qs(urlparse(url).query)
        assert params["pcAvailability"] == ["true"]

    def test_everything_search_url_uses_combined_scope(self):
        url = build_search_url("open access", _smu_config(), scope="everything")
        assert url is not None

        params = parse_qs(urlparse(url).query)
        assert params["tab"] == ["Everything"]
        assert params["search_scope"] == ["MyInst_and_CI"]

    def test_books_videos_search_url_uses_books_videos_scope(self):
        url = build_search_url("cinema", _smu_config(), scope="books & videos")
        assert url is not None

        params = parse_qs(urlparse(url).query)
        assert params["tab"] == ["booksandvideos"]
        assert params["search_scope"] == ["BooksVideos"]

    def test_search_url_escapes_chinese_query_and_filters(self):
        url = build_search_url(
            "\u5b89\u6e90",
            _smu_config(),
            date_from="2014",
            peer_reviewed=True,
        )
        assert url is not None

        params = parse_qs(urlparse(url).query)
        assert params["query"] == ["any,contains,\u5b89\u6e90"]
        assert "searchcreationdate,include,[2014 TO 2014]" in params["facet"]
        assert "tlevel,include,peer_reviewed" in params["facet"]

    def test_search_url_uses_date_range_facet(self):
        url = build_search_url(
            "open access",
            _smu_config(),
            resource_type="articles",
            date_from="2020",
            date_to="2022",
            peer_reviewed=True,
        )
        assert url is not None

        params = parse_qs(urlparse(url).query)
        assert params["facet"] == [
            "rtype,include,articles",
            "searchcreationdate,include,[2020 TO 2022]",
            "tlevel,include,peer_reviewed",
        ]

    def test_search_url_normalises_aliases(self):
        url = build_search_url(
            "poverty",
            _smu_config(),
            field="subject",
            sort_by="newest",
            resource_type="book",
        )
        assert url is not None

        params = parse_qs(urlparse(url).query)
        assert params["query"] == ["sub,contains,poverty"]
        # OneSearch's web UI calls "newest first" date_d (date_a is oldest).
        assert params["sortby"] == ["date_d"]
        assert params["facet"] == ["rtype,include,books"]

    def test_search_url_carries_facet_filters_and_exclusions(self):
        # The printed link must re-run the search that actually ran: the web
        # UI reads each facet as name,include|exclude,value.
        url = build_search_url(
            "fluid dynamics",
            _smu_config(),
            peer_reviewed=True,
            facet_filters={"subject": "Physics"},
            facet_exclusions={"rtype": "review article"},
        )
        assert url is not None

        params = parse_qs(urlparse(url).query)
        assert params["facet"] == [
            "tlevel,include,peer_reviewed",
            "topic,include,Physics",
            "rtype,exclude,review_article",
        ]

    def test_search_url_is_none_for_an_invalid_facet_name(self):
        url = build_search_url(
            "fluid dynamics", _smu_config(), facet_filters={"bad name!": "x"}
        )
        assert url is None


class TestFormatSuggestions:
    def test_formats_suggestions(self):
        output = format_suggestions(["machine learning", "machine vision"], "machine")
        assert "machine learning" in output
        assert "machine vision" in output

    def test_empty_suggestions(self):
        output = format_suggestions([], "xyzzy")
        assert "No suggestions" in output


class TestAvailabilityLabel:
    """CDI records without full text must not get the vague fallback."""

    def test_pc_record_without_fulltext_says_no_access(self):
        record = PrimoRecord(
            record_id="cdi_test_1", title="T", context="PC",
            fulltext_available=False,
        )
        assert "No full text access" in _format_availability(record)

    def test_local_record_without_fulltext_keeps_onesearch_fallback(self):
        record = PrimoRecord(
            record_id="alma991234", title="T", context="L",
            fulltext_available=False,
        )
        assert _format_availability(record) == "Check availability in OneSearch"

    def test_fulltext_record_unchanged(self):
        record = PrimoRecord(
            record_id="cdi_test_2", title="T", context="PC",
            fulltext_available=True,
        )
        assert "Full text available" in _format_availability(record)

    @pytest.mark.parametrize(
        ("codes", "expected"),
        [
            # Towson's own OneSearch labels for these codes, in its label
            # table: "Available Online", "Check request options" (no
            # inventory), "Check holdings", "Not Available".
            (["not_restricted"], "Available online"),
            (["no_inventory"], 'Not held here: no copy or online access (OneSearch: "Check request options")'),
            (["available_in_maininstitution"], "Available in the library"),
            (["check_holdings"], "Check holdings (may be available)"),
            (["unavailable"], "Not available: checked out or otherwise unavailable"),
            # MD-SOAR open-access records (alma9964182978708249); Towson's
            # label table: "Available Online".
            (["ext_not_restricted"], "Available online"),
            (["ext_restrictedNoLink"], "Not available online"),
            (["fulltext_unknown"], "Full text may be available"),
            (["some_new_code"], "some new code"),
        ],
    )
    def test_status_codes_replace_the_delivery_category(self, codes, expected):
        # The category (Alma-P, Alma-E) says what kind of record it is, not
        # whether there is a copy: alma9911670507508236 showed "Alma-P" for a
        # record with no inventory at all.
        record = PrimoRecord(
            record_id="alma991", title="T", context="L",
            availability=codes, delivery_category="Alma-P",
        )
        assert _format_availability(record) == expected

    @pytest.mark.parametrize(
        ("category", "expected"),
        [
            ("Alma-P", "Physical item: check availability in OneSearch"),
            ("Alma-E", "Electronic resource: check availability in OneSearch"),
            ("Alma-D", "Digital resource: check availability in OneSearch"),
            ("Something-Else", "Check availability in OneSearch"),
        ],
    )
    def test_category_fallback_when_primo_sends_no_status(self, category, expected):
        record = PrimoRecord(
            record_id="alma992", title="T", context="L", delivery_category=category,
        )
        assert _format_availability(record) == expected

    def test_record_detail_lists_other_libraries(self):
        record = PrimoRecord(
            record_id="alma9964140532108249",
            title="Microhydrodynamics",
            context="L",
            availability=["not_restricted"],
            other_institutions=[
                InstitutionAvailability(
                    name="University of Maryland, Baltimore County (UMBC)",
                    status="available_in_institution",
                )
            ],
        )
        detail = format_record_detail(record, _smu_config())
        assert "Availability: Available online" in detail
        assert "Other libraries: University of Maryland, Baltimore County (UMBC) (available)" in detail


class TestRecordContextMatching:
    """Source matching must be exact, not substring (bug: 'Almanac')."""

    def test_cdi_record_with_almanac_source_is_pc(self):
        record = PrimoRecord(
            record_id="cdi_test_almanac", title="T",
            source_label="World Almanac Education",
        )
        url = build_record_url(record, _smu_config())
        assert "context=PC" in url

    def test_alma_source_values_are_local(self):
        for field in ("source_id", "source_system", "source_label"):
            record = PrimoRecord(
                record_id="990012345", title="T", **{field: "Alma"}
            )
            url = build_record_url(record, _smu_config())
            assert "context=L" in url, field

    def test_explicit_context_still_wins(self):
        record = PrimoRecord(
            record_id="990012345", title="T", context="L",
            source_label="World Almanac Education",
        )
        url = build_record_url(record, _smu_config())
        assert "context=L" in url


class TestResultLandscape:
    def test_landscape_summarises_curated_facets(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        response.facets = [
            Facet(
                name="rtype",
                values=[
                    FacetValue(value="newspaper_articles", count=7368),
                    FacetValue(value="articles", count=20530),
                ],
            ),
            Facet(name="topic", values=[FacetValue(value="Ecology", count=6515)]),
            Facet(
                name="newrecords",
                values=[FacetValue(value="30 days back", count=6)],
            ),
            Facet(
                name="creationdate",
                values=[
                    FacetValue(value="2024", count=9),
                    FacetValue(value="1998", count=1),
                    FacetValue(value="not-a-year", count=2),
                ],
            ),
        ]
        output = format_search_results(response, "test")
        assert "Result landscape (facets over all matching results):" in output
        # Sorted by count and prettified for coded facets.
        assert "- Resource types: articles (20,530), newspaper articles (7,368)" in output
        assert "- Top subjects: Ecology (6,515)" in output
        assert "- Publication years: 1998-2024" in output
        assert "- Refine with resource_type" in output
        # Uncurated facets stay hidden.
        assert "newrecords" not in output
        assert "30 days back" not in output

    def test_landscape_shows_top_five_values_and_more_marker(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        response.facets = [
            Facet(
                name="topic",
                values=[
                    FacetValue(value=f"subject {i}", count=100 - i) for i in range(8)
                ],
            )
        ]
        output = format_search_results(response, "test")
        line = next(
            l for l in output.splitlines() if l.startswith("- Top subjects:")
        )
        assert "subject 0 (100)" in line
        assert "subject 4 (96)" in line
        assert "subject 5" not in line
        assert "+3 more" in line

    def test_no_landscape_without_facets(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = format_search_results(response, "test")
        assert "Result landscape" not in output


class TestCompoundQueryLinks:
    def _clauses(self):
        return [
            {"field": "title", "value": "capital", "connector": "AND"},
            {"field": "creator", "value": "piketty"},
        ]

    def test_build_search_url_uses_advanced_mode_with_one_param_per_clause(self):
        url = build_search_url("summary", _smu_config(), clauses=self._clauses())
        assert url is not None
        params = parse_qs(urlparse(url).query)
        assert params["query"] == [
            "title,contains,capital,AND",
            "creator,contains,piketty",
        ]
        assert params["mode"] == ["advanced"]

    def test_build_search_url_returns_none_for_invalid_clauses(self):
        url = build_search_url(
            "summary",
            _smu_config(),
            clauses=[{"value": "x", "operator": "fuzzy"}],
        )
        assert url is None

    def test_search_results_label_shows_compiled_clauses(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = format_search_results(
            response,
            "piketty capital",
            config=_smu_config(),
            clauses=self._clauses(),
        )
        assert (
            "- Results found: [title,contains,capital,AND;creator,contains,piketty]("
            in output
        )
        assert "mode=advanced" in output


class TestHoldingsAndAccessDisplay:
    def _physical_record(self) -> PrimoRecord:
        return PrimoRecord(
            record_id="alma9922481002601",
            title="Capital in the twenty-first century",
            resource_type="book",
            creators=["Piketty, Thomas"],
            creation_date="2014",
            locations=[
                {
                    "library": "Li Ka Shing Library",
                    "location": "Books Level 3",
                    "call_number": "HB501 .P43613 2014",
                    "status": "available",
                },
                {
                    "library": "Law Library",
                    "location": "Reserves",
                    "call_number": "K1 .X 2020",
                    "status": "on_loan",
                },
            ],
        )

    def _online_record(self) -> PrimoRecord:
        return PrimoRecord(
            record_id="alma99307218302601",
            title="Capital in the Twenty-First Century",
            resource_type="book",
            fulltext_available=True,
            access_links=[
                {"label": "Full text", "url": "https://www.jstor.org/stable/1"}
            ],
        )

    def test_search_results_show_location_with_more_marker(self):
        response = SearchResponse.model_validate(
            {"info": {"total": 1}, "records": [self._physical_record()]}
        )
        output = format_search_results(response, "capital")
        assert (
            "    Location: Li Ka Shing Library, Books Level 3 -- "
            "HB501 .P43613 2014 (available) | +1 more location" in output
        )

    def test_search_results_show_access_link(self):
        response = SearchResponse.model_validate(
            {"info": {"total": 1}, "records": [self._online_record()]}
        )
        output = format_search_results(response, "capital")
        assert "    Access: [Full text](https://www.jstor.org/stable/1)" in output

    def test_search_results_fall_back_to_openurl(self):
        record = PrimoRecord(
            record_id="cdi_x",
            title="Some article",
            openurl="https://resolver/openurl?a=1",
        )
        response = SearchResponse.model_validate(
            {"info": {"total": 1}, "records": [record]}
        )
        output = format_search_results(response, "test")
        assert (
            "    Access: [Full text via library](https://resolver/openurl?a=1)"
            in output
        )

    def test_record_detail_lists_all_locations_and_links(self):
        record = self._physical_record().model_copy(
            update={
                "access_links": [
                    AccessLink(
                        label="Full text", url="https://www.jstor.org/stable/1"
                    ),
                    AccessLink(label="Ebook Central", url="https://ebook/x"),
                ]
            }
        )
        output = format_record_detail(record)
        assert (
            "Location: Li Ka Shing Library, Books Level 3 -- "
            "HB501 .P43613 2014 (available)" in output
        )
        assert "Location: Law Library, Reserves -- K1 .X 2020 (on loan)" in output
        assert "Access: [Full text](https://www.jstor.org/stable/1)" in output
        assert "Access: [Ebook Central](https://ebook/x)" in output
