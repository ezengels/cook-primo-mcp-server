"""Tests for citation formatting."""

import pytest

from primo_mcp_server.citations import format_citation, invalid_style_message
from primo_mcp_server.models import PrimoRecord, SearchResponse


class TestCitations:
    def _make_article(self) -> PrimoRecord:
        return PrimoRecord(
            title="Digital Entrepreneurship in Practice",
            resource_type="article",
            creators=["Smith, John", "Jones, Mary"],
            authors_structured=["Smith, John", "Jones, Mary"],
            creation_date="2023-06-15",
            journal_title="Journal of Business Research",
            volume="150",
            issue="2",
            start_page="100",
            end_page="115",
            doi="10.1016/j.jbusres.2023.001",
            issn=["0148-2963"],
            peer_reviewed=True,
        )

    def _make_book(self) -> PrimoRecord:
        return PrimoRecord(
            title="Innovation Management",
            resource_type="book",
            creators=["Brown, Alice"],
            authors_structured=["Brown, Alice"],
            creation_date="2022",
            publisher="Oxford University Press",
            isbn=["9780198765432"],
        )

    def test_apa7_article(self):
        citation = format_citation(self._make_article(), "apa7")
        assert "Smith, J." in citation
        assert "Jones, M." in citation
        assert "(2023)" in citation
        assert "Digital Entrepreneurship" in citation
        assert "10.1016" in citation

    def test_apa7_book(self):
        citation = format_citation(self._make_book(), "apa7")
        assert "Brown, A." in citation
        assert "(2022)" in citation
        assert "Innovation Management" in citation
        assert "Oxford University Press" in citation

    def test_harvard_article(self):
        citation = format_citation(self._make_article(), "harvard")
        assert "(2023)" in citation
        assert "vol." in citation

    def test_chicago_article(self):
        citation = format_citation(self._make_article(), "chicago")
        assert "Smith" in citation
        assert "Jones" in citation

    def test_ieee_article(self):
        citation = format_citation(self._make_article(), "ieee")
        assert "J. Smith" in citation
        assert "doi:" in citation

    def test_two_authors_join_with_and_no_comma(self):
        chicago = format_citation(self._make_article(), "chicago")
        ieee = format_citation(self._make_article(), "ieee")
        assert chicago.startswith("Smith, J. and Jones, M.")
        assert ieee.startswith("J. Smith and M. Jones,")

    def test_three_authors_keep_serial_comma(self):
        record = self._make_article().model_copy(
            update={"authors_structured": ["Smith, John", "Jones, Mary", "Lee, Kim"]}
        )
        assert format_citation(record, "ieee").startswith(
            "J. Smith, M. Jones, and K. Lee,"
        )

    def test_invalid_style_message(self):
        assert invalid_style_message("APA7") is None
        assert "Invalid citation style" in invalid_style_message("mla")

    def test_vancouver_article(self):
        citation = format_citation(self._make_article(), "vancouver")
        assert "Smith J" in citation
        assert "Jones M" in citation

    def test_from_live_data(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        for style in ["apa7", "harvard", "chicago", "ieee", "vancouver"]:
            citation = format_citation(response.records[0], style)
            assert len(citation) > 20
            assert response.records[0].title[:20] in citation

    def test_style_and_plural_article_type_are_normalised(self):
        record = self._make_article()
        record.resource_type = "articles"

        citation = format_citation(record, "APA7")

        assert "Journal of Business Research" in citation
        assert "Oxford University Press" not in citation

    def test_chinese_author_names_are_preserved(self):
        author = "\u88f4, \u5b9c\u7406."
        record = PrimoRecord(
            title="\u5b89\u6e90 : \u767c\u6398\u4e2d\u570b\u9769\u547d\u4e4b\u50b3\u7d71.",
            resource_type="book",
            creators=[author],
            authors_structured=[author],
            creation_date="2014",
            publisher="Hong Kong University Press",
        )

        for style in ["apa7", "harvard", "chicago", "ieee", "vancouver"]:
            citation = format_citation(record, style)
            assert author in citation
            assert "\u88f4, \u5b9c." not in citation


class TestYearWithoutJournal:
    """Regression: IEEE and Chicago dropped the year when jtitle was empty."""

    @staticmethod
    def _article_no_journal():
        return PrimoRecord(
            record_id="cdi_x", title="A Paper", resource_type="article",
            creators=["Tan, Mei Ling"], creation_date="2021",
        )

    def test_ieee_article_without_journal_keeps_year(self):
        assert "2021" in format_citation(self._article_no_journal(), "ieee")

    def test_chicago_article_without_journal_keeps_year(self):
        assert "2021" in format_citation(self._article_no_journal(), "chicago")

    def test_apa_article_without_journal_keeps_year(self):
        assert "2021" in format_citation(self._article_no_journal(), "apa7")

    def test_vancouver_article_without_journal_keeps_year(self):
        # Vancouver also only emits the year inside the journal block.
        assert "2021" in format_citation(self._article_no_journal(), "vancouver")

    def test_ieee_with_journal_unchanged(self):
        r = self._article_no_journal()
        r.journal_title = "J. Test"
        cite = format_citation(r, "ieee")
        assert "2021" in cite and "J. Test" in cite


class TestCitationDetails:
    """Defects found by the 2026-11-19 plugin test against live Towson records."""

    @staticmethod
    def _li_koch() -> PrimoRecord:
        # cdi_crossref_primary_10_1017_jfm_2022_891
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
            publisher="Cambridge, UK: Cambridge University Press",
            publisher_name="Cambridge University Press",
            publication_place="Cambridge, UK",
        )

    @staticmethod
    def _kim_karrila() -> PrimoRecord:
        # alma9964140532108249 (the publisher's misspelling is the record's)
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

    def test_apa_puts_a_comma_before_the_ampersand_for_two_authors(self):
        assert format_citation(self._li_koch(), "apa7").startswith(
            "Li, G., & Koch, D. L. (2022)."
        )

    def test_apa_cites_the_article_number(self):
        assert "*Journal of fluid mechanics*, *952*, Article A16." in format_citation(
            self._li_koch(), "apa7"
        )

    def test_apa_book_names_both_authors_and_the_publisher_without_its_place(self):
        assert format_citation(self._kim_karrila(), "apa7") == (
            "Kim, S., & Karrila, S. J. (1991). "
            "*Microhydrodynamics : principles and selected applications*. "
            "Butterworth-Heinemarm."
        )

    def test_chicago_has_no_double_period_after_initials(self):
        citation = format_citation(self._li_koch(), "chicago")
        assert citation.startswith('Li, G. and Koch, D. L. "Dynamics')
        assert ".." not in citation

    def test_chicago_book_gives_place_and_publisher(self):
        assert format_citation(self._kim_karrila(), "chicago").endswith(
            "Stoneham, Massachusetts: Butterworth-Heinemarm, 1991."
        )

    def test_harvard_joins_two_authors_with_and(self):
        assert format_citation(self._li_koch(), "harvard").startswith(
            "Li, G. and Koch, D. L. (2022)"
        )

    def test_other_styles_cite_the_article_number(self):
        record = self._li_koch()
        assert "952 (2022): A16." in format_citation(record, "chicago")
        assert "vol. 952, article A16." in format_citation(record, "harvard")
        assert "vol. 952, Art. no. A16, 2022." in format_citation(record, "ieee")
        assert "2022;952:A16." in format_citation(record, "vancouver")

    def test_ieee_book_joins_two_authors_with_and(self):
        assert format_citation(self._kim_karrila(), "ieee").startswith(
            "S. Kim and S. J. Karrila, *Microhydrodynamics"
        )

    @pytest.mark.parametrize(
        "romanised",
        [
            # ALA-LC romanisation of Cyrillic "Yu": I + ligature halves + U
            # (alma9963964836008249 at Towson), or the double inverted breve.
            "I\ufe20U\ufe21",
            "I\u0361U",
        ],
    )
    def test_transliterated_initials_keep_their_ligature(self, romanised):
        record = PrimoRecord(
            title="Methods of measuring environmental parameters",
            resource_type="book",
            authors_structured=[f"Posudin, {romanised}. I."],
            creation_date="2014",
            publisher_name="Wiley",
        )
        assert format_citation(record, "apa7").startswith(f"Posudin, {romanised}. I. (2014).")
        assert format_citation(record, "ieee").startswith(f"{romanised}. I. Posudin,")
        assert format_citation(record, "vancouver").startswith(f"Posudin {romanised}I.")

    def test_full_romanised_first_name_gives_the_ligature_initial(self):
        record = PrimoRecord(
            title="T", resource_type="book",
            authors_structured=["Posudin, I\ufe20u\ufe21rii\u0306"], creation_date="2014",
        )
        assert format_citation(record, "apa7").startswith("Posudin, I\ufe20U\ufe21. (2014).")

    def test_publisher_without_structured_fields_drops_the_isbd_place(self):
        record = PrimoRecord(
            title="Fluid mechanics", resource_type="book",
            authors_structured=["Batchelor, G. K."], creation_date="2000",
            publisher="Cambridge : Cambridge University Press",
        )
        assert format_citation(record, "apa7").endswith("Cambridge University Press.")
        assert format_citation(record, "chicago").endswith(
            "Cambridge: Cambridge University Press, 2000."
        )
