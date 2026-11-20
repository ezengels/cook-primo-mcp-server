"""Tests for citation formatting."""

import pytest

from primo_mcp_server.citations import CITATION_STYLES, format_citation, invalid_style_message
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
        # The record's "Journal of fluid mechanics" is given in title case.
        assert "*Journal of Fluid Mechanics*, *952*, Article A16." in format_citation(
            self._li_koch(), "apa7"
        )

    def test_apa_book_names_both_authors_and_the_publisher_without_its_place(self):
        # The catalogue's "Title : subtitle" becomes "Title: Subtitle" (APA
        # capitalises the first word of a subtitle).
        assert format_citation(self._kim_karrila(), "apa7") == (
            "Kim, S., & Karrila, S. J. (1991). "
            "*Microhydrodynamics: Principles and selected applications*. "
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


class TestThirdRetestDetails:
    """APA details from the third plugin test (2026-11-19), on live Towson records."""

    @staticmethod
    def _elsevier() -> PrimoRecord:
        # cdi_crossref_citationtrail_10_1016_j_jmps_2021_104345: Primo files the
        # article number both as addata.artnum and as addata.spage.
        return PrimoRecord(
            title="Elongation deformation of a red blood cell under shear flow",
            resource_type="article",
            authors_structured=["Tsubota, Ken-ichi"],
            creation_date="2021-07",
            journal_title="Journal of the Mechanics and Physics of Solids",
            volume="152",
            start_page="104345",
            article_number="104345",
            doi="10.1016/j.jmps.2021.104345",
        )

    @staticmethod
    def _mdpi() -> PrimoRecord:
        # cdi_crossref_primary_10_3390_computation13020047: no artnum; MDPI
        # numbers every article and files the number as the start page.
        return PrimoRecord(
            title="Transport characteristics of small molecules near deforming blood cells",
            resource_type="article",
            authors_structured=["Nix, Stephanie"],
            creation_date="2025-02",
            journal_title="Computation",
            volume="13",
            issue="2",
            start_page="47",
            doi="10.3390/computation13020047",
        )

    def test_hyphenated_given_name_keeps_both_initials(self):
        record = self._elsevier()
        assert format_citation(record, "apa7").startswith("Tsubota, K.-i. (2021).")
        assert format_citation(record, "ieee").startswith("K.-i. Tsubota,")
        assert format_citation(record, "vancouver").startswith("Tsubota KI.")

    def test_initials_written_without_a_space_are_both_kept(self):
        # cdi_crossref_citationtrail_10_1016_j_compfluid_2020_104786: "Lyu, J.M."
        record = self._elsevier().model_copy(
            update={"authors_structured": ["Lyu, J.M.", "Chen, Paul G."]}
        )
        assert format_citation(record, "apa7").startswith("Lyu, J. M., & Chen, P. G. (2021).")
        assert format_citation(record, "vancouver").startswith("Lyu JM, Chen PG.")

    def test_article_number_filed_as_start_page_is_cited_as_article(self):
        record = self._elsevier()
        assert "*152*, Article 104345." in format_citation(record, "apa7")
        assert "vol. 152, Art. no. 104345, 2021." in format_citation(record, "ieee")

    def test_mdpi_start_page_is_cited_as_its_article_number(self):
        assert "*13*(2), Article 47." in format_citation(self._mdpi(), "apa7")

    def test_page_range_is_still_cited_as_pages(self):
        record = self._elsevier().model_copy(
            update={"start_page": "100", "end_page": "115", "article_number": "104345"}
        )
        assert "*152*, 100-115." in format_citation(record, "apa7")

    def test_journal_title_is_given_in_title_case(self):
        # CDI often stores journal titles in sentence case.
        record = self._elsevier().model_copy(
            update={"journal_title": "Journal of computational physics"}
        )
        for style in ("apa7", "chicago", "harvard", "ieee"):
            assert "*Journal of Computational Physics*" in format_citation(record, style), style
        # Vancouver keeps the record's form, as NLM title abbreviations do.
        assert "Journal of computational physics." in format_citation(record, "vancouver")

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Journal of computational physics", "Journal of Computational Physics"),
            ("Computers & fluids", "Computers & Fluids"),
            ("The journal of the acoustical society of america",
             "The Journal of the Acoustical Society of America"),
            ("Biochimica et biophysica acta: biomembranes",
             "Biochimica et Biophysica Acta: Biomembranes"),
            ("IEEE transactions on medical imaging", "IEEE Transactions on Medical Imaging"),
            # Words with capitals of their own are left as the record has them.
            ("PLoS ONE", "PLoS ONE"),
            ("eLife", "eLife"),
        ],
    )
    def test_title_case_rules(self, raw, expected):
        from primo_mcp_server.citations import _title_case

        assert _title_case(raw) == expected


class TestCataloguePunctuation:
    """Found by a sweep of 120 live Towson records in all five styles."""

    def test_catalogue_colon_spacing_is_fixed_in_titles_and_journal_names(self):
        article = PrimoRecord(
            title="Plant phylogenomics : where are we",
            resource_type="article",
            authors_structured=["Wen, Jun"],
            creation_date="2020",
            journal_title="Journal of systematics and evolution : JSE",
            volume="58",
            start_page="533",
            end_page="545",
        )
        apa = format_citation(article, "apa7")
        assert "Plant phylogenomics: Where are we." in apa
        assert "*Journal of Systematics and Evolution: JSE*" in apa
        for style in CITATION_STYLES:
            assert " : " not in format_citation(article, style), style

    def test_title_ending_in_a_question_mark_gets_no_extra_period(self):
        article = PrimoRecord(
            title="Plant phylogenomics: where are we?",
            resource_type="article",
            authors_structured=["Wen, Jun"],
            creation_date="2020",
            journal_title="Journal of systematics and evolution",
            volume="58",
        )
        assert "where are we? *Journal" in format_citation(article, "apa7").replace("Where", "where")
        assert '"Plant phylogenomics: where are we?"' in format_citation(article, "chicago")
        for style in CITATION_STYLES:
            assert "?." not in format_citation(article, style), style

    def test_publisher_ending_in_a_period_is_not_doubled(self):
        # alma990016674110108249: "Baltimore : Celebrate Maryland, Inc."
        book = PrimoRecord(
            title="Maryland", resource_type="book", authors_structured=["Doe, Jane"],
            creation_date="2005", publisher_name="Celebrate Maryland, Inc.",
            publication_place="Baltimore",
        )
        assert format_citation(book, "apa7").endswith("Celebrate Maryland, Inc.")
        for style in CITATION_STYLES:
            assert ".." not in format_citation(book, style), style

    def test_multi_place_imprint_has_no_stray_semicolon(self):
        # alma990015940980108249: addata.cop "Philadelphia ;".
        book = PrimoRecord(
            title="Frederick Douglass", resource_type="book",
            authors_structured=["Washington, Booker T."], creation_date="1907",
            publisher_name="G.W. Jacobs", publication_place="Philadelphia ;",
        )
        assert format_citation(book, "chicago").endswith("Philadelphia: G.W. Jacobs, 1907.")

    def test_meeting_qualifier_is_left_out_of_a_conference_author(self):
        # alma9964138891408249: the meeting heading's number and date
        # "(18th : 1986)" are catalogue metadata; a fuller-name
        # parenthetical without " : " is kept.
        book = PrimoRecord(
            title="Three-dimensional models of marine and estuarine dynamics",
            resource_type="book",
            creators=[
                "International Liege Colloquium on Ocean Hydrodynamics (18th : 1986)",
                "Nihoul, Jacques C. J.",
            ],
            creation_date="1987",
        )
        apa = format_citation(book, "apa7")
        assert apa.startswith(
            "International Liege Colloquium on Ocean Hydrodynamics, & Nihoul, J. C. J. (1987)."
        )
        for style in CITATION_STYLES:
            assert "(18th" not in format_citation(book, style), style

    def test_elocator_is_cited_as_article(self):
        # cdi_crossref_citationtrail_10_1111_jjns_12573 (Wiley).
        article = PrimoRecord(
            title="T", resource_type="article", authors_structured=["Doe, Jane"],
            creation_date="2024", journal_title="Japan journal of nursing science",
            volume="21", issue="2", start_page="e12573", doi="10.1111/jjns.12573",
        )
        assert "*21*(2), Article e12573." in format_citation(article, "apa7")
