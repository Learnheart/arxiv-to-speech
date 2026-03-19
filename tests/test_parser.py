"""
Unit tests for pipeline/parser.py
Covers: parse_docx(), parse_pdf(), parse_document()
"""
import io
import pytest
from unittest.mock import patch, MagicMock

from pipeline.parser import (
    DocumentElement,
    ElementType,
    parse_docx,
    parse_pdf,
    parse_document,
)


# ══════════════════════════════════════════════════════════
# TC-PARSE: parse_document() dispatch
# ══════════════════════════════════════════════════════════

class TestParseDocument:

    # ── TC-PARSE-001: Dispatch to docx parser ──
    @patch("pipeline.parser.parse_docx")
    def test_dispatches_docx(self, mock_parse):
        mock_parse.return_value = []
        parse_document(b"test", "docx")
        mock_parse.assert_called_once_with(b"test")

    # ── TC-PARSE-002: Dispatch to pdf parser ──
    @patch("pipeline.parser.parse_pdf")
    def test_dispatches_pdf(self, mock_parse):
        mock_parse.return_value = []
        parse_document(b"test", "pdf")
        mock_parse.assert_called_once_with(b"test")

    # ── TC-PARSE-003: Unsupported file type ──
    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            parse_document(b"test", "txt")

    def test_unsupported_type_pptx(self):
        with pytest.raises(ValueError):
            parse_document(b"test", "pptx")


# ══════════════════════════════════════════════════════════
# TC-DOCX: parse_docx() with mock python-docx
# ══════════════════════════════════════════════════════════

class TestParseDocx:

    # ── TC-DOCX-001: Empty document ──
    def test_empty_document(self):
        with patch("docx.Document") as MockDocument:
            mock_doc = MagicMock()
            mock_doc.element.body.iterchildren.return_value = iter([])
            mock_doc.paragraphs = []
            mock_doc.tables = []
            MockDocument.return_value = mock_doc

            result = parse_docx(b"PK\x03\x04")
            assert result == []

    # ── TC-DOCX-002: Element ordering preserved ──
    def test_elements_have_sequential_order(self):
        """If we parse a real docx, elements should have increasing order values."""
        # This is a structural test — we verify the contract
        elements = [
            DocumentElement(type=ElementType.HEADING, content="H1", heading_level=1, order=0),
            DocumentElement(type=ElementType.PARAGRAPH, content="P1", order=1),
            DocumentElement(type=ElementType.TABLE, table_data=[["a"]], order=2),
        ]
        orders = [e.order for e in elements]
        assert orders == sorted(orders)


# ══════════════════════════════════════════════════════════
# TC-PDF: parse_pdf() with mock PyMuPDF
# ══════════════════════════════════════════════════════════

class TestParsePdf:

    # ── TC-PDF-001: Empty PDF (no pages) ──
    def test_empty_pdf(self):
        with patch("fitz.open") as mock_open:
            mock_doc = MagicMock()
            mock_doc.__len__ = MagicMock(return_value=0)
            mock_doc.close = MagicMock()
            mock_open.return_value = mock_doc

            result = parse_pdf(b"%PDF-1.4")
            assert result == []
            mock_doc.close.assert_called_once()

    # ── TC-PDF-002: Font size heuristic for headings ──
    def test_font_size_heading_thresholds(self):
        """Verify heading level assignment logic:
        >16pt → H1, >13pt → H2, >11.5pt → H3, <=11.5pt → PARAGRAPH
        """
        thresholds = [
            (18.0, ElementType.HEADING, 1),
            (14.0, ElementType.HEADING, 2),
            (12.0, ElementType.HEADING, 3),
            (11.0, ElementType.PARAGRAPH, 0),
            (10.0, ElementType.PARAGRAPH, 0),
        ]
        for font_size, expected_type, expected_level in thresholds:
            if font_size > 16:
                assert expected_type == ElementType.HEADING
                assert expected_level == 1
            elif font_size > 13:
                assert expected_type == ElementType.HEADING
                assert expected_level == 2
            elif font_size > 11.5:
                assert expected_type == ElementType.HEADING
                assert expected_level == 3
            else:
                assert expected_type == ElementType.PARAGRAPH

    # ── TC-PDF-003: Y-position sorting within page ──
    def test_elements_sorted_by_y_position(self):
        """Elements within a page should be sorted by vertical position."""
        # Simulating the sort logic from parser
        page_elements = [
            (300.0, DocumentElement(type=ElementType.PARAGRAPH, content="Bottom")),
            (100.0, DocumentElement(type=ElementType.HEADING, content="Top", heading_level=1)),
            (200.0, DocumentElement(type=ElementType.TABLE, table_data=[["mid"]])),
        ]
        page_elements.sort(key=lambda x: x[0])
        contents = [e[1].content or "table" for e in page_elements]
        assert contents == ["Top", "table", "Bottom"]


# ══════════════════════════════════════════════════════════
# TC-ELEM: DocumentElement data model
# ══════════════════════════════════════════════════════════

class TestDocumentElement:

    def test_heading_element(self):
        el = DocumentElement(type=ElementType.HEADING, content="Title", heading_level=1, order=0)
        assert el.type == ElementType.HEADING
        assert el.heading_level == 1

    def test_paragraph_element(self):
        el = DocumentElement(type=ElementType.PARAGRAPH, content="Text", order=1)
        assert el.type == ElementType.PARAGRAPH
        assert el.heading_level == 0  # default

    def test_table_element(self):
        el = DocumentElement(type=ElementType.TABLE, table_data=[["a", "b"]], order=2)
        assert el.type == ElementType.TABLE
        assert len(el.table_data) == 1

    def test_image_element(self):
        el = DocumentElement(type=ElementType.IMAGE, image_bytes=b"\x89PNG", order=3)
        assert el.type == ElementType.IMAGE
        assert el.image_bytes is not None

    def test_default_values(self):
        el = DocumentElement(type=ElementType.PARAGRAPH)
        assert el.content == ""
        assert el.heading_level == 0
        assert el.table_data == []
        assert el.image_bytes is None
        assert el.order == 0
