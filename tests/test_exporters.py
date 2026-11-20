"""Tests for export formats."""

from primo_mcp_server.exporters import export_bibtex, export_csv, export_ris
from primo_mcp_server.models import PrimoRecord, SearchResponse


class TestBibTeX:
    def test_article_export(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_bibtex(response.records)
        assert "@article{" in output
        assert "author = {" in output
        assert "title = {" in output
        assert "doi = {" in output

    def test_unique_keys(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_bibtex(response.records)
        # Extract all citation keys
        import re
        keys = re.findall(r"@\w+\{(\w+),", output)
        assert len(keys) == len(set(keys)), "BibTeX keys should be unique"

    def test_chinese_record_uses_stable_ascii_key_and_preserves_text(self):
        title = "\u5b89\u6e90 : \u767c\u6398\u4e2d\u570b\u9769\u547d\u4e4b\u50b3\u7d71."
        author = "\u88f4, \u5b9c\u7406."
        record = PrimoRecord(
            record_id="alma99317560802601",
            title=title,
            resource_type="book",
            creators=[author],
            creation_date="2014",
        )

        output = export_bibtex([record])

        assert "@book{alma99317560802601," in output
        assert f"author = {{{author}}}" in output
        assert f"title = {{{title}}}" in output

    def test_escapes_special_characters_and_maps_plural_conference_type(self):
        record = PrimoRecord(
            title="A_B & 100% {Test}",
            resource_type="conference_proceedings",
            creators=["Smith, John"],
            creation_date="2024",
        )

        output = export_bibtex([record])

        assert "@inproceedings{" in output
        assert r"title = {A\_B \& 100\% \{Test\}}" in output


class TestRIS:
    def test_article_export(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_ris(response.records)
        assert "TY  - JOUR" in output
        assert "AU  - " in output
        assert "TI  - " in output
        assert "ER  - " in output

    def test_has_doi(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_ris(response.records[:1])
        if response.records[0].doi:
            assert "DO  - " in output

    def test_chinese_record_preserved(self):
        title = "\u5b89\u6e90"
        author = "\u88f4, \u5b9c\u7406."
        output = export_ris([
            PrimoRecord(title=title, resource_type="book", creators=[author])
        ])

        assert f"AU  - {author}" in output
        assert f"TI  - {title}" in output

    def test_plural_record_types_and_multiline_values_are_exported_safely(self):
        output = export_ris([
            PrimoRecord(
                title="Conference Paper",
                resource_type="conference_proceedings",
                description="line one\nline two",
            )
        ])

        assert "TY  - CONF" in output
        assert "AB  - line one line two" in output


class TestCSV:
    def test_csv_has_header(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_csv(response.records)
        assert "Record ID" in output
        assert "Title" in output
        assert "Authors" in output

    def test_csv_has_bom(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_csv(response.records)
        assert output.startswith("\ufeff")

    def test_csv_row_count(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_csv(response.records)
        lines = output.strip().split("\n")
        # Header + data rows
        assert len(lines) == 1 + len(response.records)

    def test_chinese_record_preserved_with_bom(self):
        title = "\u5b89\u6e90"
        author = "\u88f4, \u5b9c\u7406."
        output = export_csv([
            PrimoRecord(title=title, resource_type="book", creators=[author])
        ])

        assert output.startswith("\ufeff")
        assert title in output
        assert author in output


class TestPublisherAndAuthors:
    @staticmethod
    def _kim_karrila() -> PrimoRecord:
        return PrimoRecord(
            record_id="alma9964140532108249",
            title="Microhydrodynamics : principles and selected applications",
            resource_type="book",
            authors_structured=["Kim, Sangtae"],
            co_authors=["Karrila, Seppo J."],
            creation_date="1991",
            publisher="Stoneham, Massachusetts : Butterworth-Heinemarm",
            publisher_name="Butterworth-Heinemarm",
            publication_place="Stoneham, Massachusetts",
        )

    def test_bibtex_separates_publisher_and_address_and_keeps_co_author(self):
        output = export_bibtex([self._kim_karrila()])
        assert "author = {Kim, Sangtae and Karrila, Seppo J.}" in output
        assert "publisher = {Butterworth-Heinemarm}" in output
        assert "address = {Stoneham, Massachusetts}" in output

    def test_ris_separates_publisher_and_place_and_keeps_co_author(self):
        output = export_ris([self._kim_karrila()])
        assert "AU  - Kim, Sangtae\nAU  - Karrila, Seppo J." in output
        assert "PB  - Butterworth-Heinemarm" in output
        assert "CY  - Stoneham, Massachusetts" in output

    def test_csv_separates_publisher_and_place(self):
        import csv as csv_module
        import io

        output = export_csv([self._kim_karrila()])
        rows = list(csv_module.DictReader(io.StringIO(output.lstrip("\ufeff"))))
        assert rows[0]["Publisher"] == "Butterworth-Heinemarm"
        assert rows[0]["Place"] == "Stoneham, Massachusetts"


class TestArticleNumbers:
    """Journals that number articles (JFM: "A16") instead of paging them."""

    @staticmethod
    def _li_koch() -> PrimoRecord:
        return PrimoRecord(
            record_id="cdi_crossref_primary_10_1017_jfm_2022_891",
            title="Dynamics of a self-propelled compound droplet",
            resource_type="article",
            authors_structured=["Li, Gaojin", "Koch, Donald L."],
            creation_date="2022-12-10",
            journal_title="Journal of fluid mechanics",
            volume="952",
            article_number="A16",
            doi="10.1017/jfm.2022.891",
        )

    def test_bibtex_puts_the_article_number_in_pages(self):
        # Where reference managers look for it; publishers' own BibTeX for
        # article-numbered journals does the same.
        assert "pages = {A16}" in export_bibtex([self._li_koch()])

    def test_ris_puts_the_article_number_in_sp(self):
        assert "SP  - A16" in export_ris([self._li_koch()])

    def test_csv_puts_the_article_number_in_pages(self):
        import csv as csv_module
        import io

        output = export_csv([self._li_koch()])
        rows = list(csv_module.DictReader(io.StringIO(output.lstrip("\ufeff"))))
        assert rows[0]["Pages"] == "A16"

    def test_page_range_wins_over_an_article_number(self):
        record = self._li_koch().model_copy(update={"start_page": "1", "end_page": "20"})
        assert "pages = {1--20}" in export_bibtex([record])
        assert "SP  - 1" in export_ris([record])
        assert "A16" not in export_ris([record])
