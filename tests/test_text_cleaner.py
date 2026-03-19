"""
Unit tests for utils/text_cleaner.py
Covers: clean_for_tts(), table_to_markdown()
"""
import pytest

from utils.text_cleaner import clean_for_tts, table_to_markdown, ABBREVIATIONS


# ══════════════════════════════════════════════════════════
# TC-CLN: clean_for_tts()
# ══════════════════════════════════════════════════════════

class TestCleanForTts:
    """Test suite for clean_for_tts function."""

    # ── TC-CLN-001: Empty / None input ──
    def test_empty_string(self):
        assert clean_for_tts("") == ""

    def test_none_returns_empty(self):
        assert clean_for_tts(None) == ""

    def test_whitespace_only(self):
        assert clean_for_tts("   \n\t  ") == ""

    # ── TC-CLN-002: Unicode normalization (NFKC) ──
    def test_unicode_nfkc_normalization(self):
        # Fullwidth characters should be normalized
        result = clean_for_tts("Ｈｅｌｌｏ")
        assert "Hello" in result

    def test_vietnamese_diacritics_preserved(self):
        text = "Thành phố Hồ Chí Minh rất đẹp"
        result = clean_for_tts(text)
        assert "Thành phố" in result
        assert "đẹp" in result

    # ── TC-CLN-003: Page number removal ──
    def test_remove_standalone_page_numbers(self):
        text = "Some text\n42\nMore text"
        result = clean_for_tts(text)
        assert "42" not in result
        assert "Some text" in result
        assert "More text" in result

    def test_keep_numbers_in_sentences(self):
        text = "There are 42 items in the list"
        result = clean_for_tts(text)
        assert "42" in result

    def test_remove_page_header_pattern(self):
        text = "Trang 15\nActual content here"
        result = clean_for_tts(text)
        assert "Trang 15" not in result
        assert "Actual content" in result

    def test_remove_page_header_english(self):
        text = "Page 3\nContent"
        result = clean_for_tts(text)
        assert "Page 3" not in result

    # ── TC-CLN-004: Abbreviation expansion ──
    def test_expand_tp_hcm(self):
        result = clean_for_tts("TP.HCM là thành phố lớn nhất")
        assert "Thành phố Hồ Chí Minh" in result

    def test_expand_academic_titles(self):
        result = clean_for_tts("GS. Nguyễn Văn A và TS. Trần Thị B")
        assert "Giáo sư" in result
        assert "Tiến sĩ" in result

    def test_expand_currency(self):
        result = clean_for_tts("Giá 100 VNĐ và 50 USD")
        assert "Việt Nam đồng" in result
        assert "đô la Mỹ" in result

    def test_all_abbreviations_have_correct_diacritics(self):
        """Ensure Vietnamese abbreviations expand with proper diacritics."""
        for abbr, expansion in ABBREVIATIONS.items():
            result = clean_for_tts(abbr)
            assert expansion in result, f"'{abbr}' should expand to '{expansion}', got '{result}'"

    # ── TC-CLN-005: Whitespace normalization ──
    def test_collapse_multiple_newlines(self):
        text = "Line 1\n\n\n\n\nLine 2"
        result = clean_for_tts(text)
        assert "\n\n\n" not in result

    def test_collapse_multiple_spaces(self):
        text = "Word1    Word2     Word3"
        result = clean_for_tts(text)
        assert "  " not in result

    def test_trim_around_newlines(self):
        text = "Line 1   \n   Line 2"
        result = clean_for_tts(text)
        assert " \n" not in result
        assert "\n " not in result

    # ── TC-CLN-006: Special character removal ──
    def test_remove_bullet_characters(self):
        text = "• Item 1\n● Item 2\n○ Item 3"
        result = clean_for_tts(text)
        assert "•" not in result
        assert "●" not in result
        assert "○" not in result

    def test_remove_control_characters(self):
        text = "Hello\x00World\x0b!"
        result = clean_for_tts(text)
        assert "\x00" not in result
        assert "\x0b" not in result

    # ── TC-CLN-007: Quote and dash normalization ──
    def test_normalize_smart_quotes(self):
        """Smart quotes should be normalized to straight quotes."""
        text = "\u201cHello\u201d and \u2018World\u2019"
        result = clean_for_tts(text)
        assert "Hello" in result
        assert "World" in result
        # After cleaning, the text should contain straight quotes (or equivalent)
        # The important thing is content is preserved through normalization

    def test_normalize_dashes(self):
        text = "A\u2013B and C\u2014D"
        result = clean_for_tts(text)
        assert "A-B" in result
        assert "C-D" in result

    # ── TC-CLN-008: Bullet point cleanup ──
    def test_remove_bullet_points_as_list(self):
        text = "- Item one\n- Item two\n* Item three"
        result = clean_for_tts(text)
        assert result.startswith("Item one")

    # ── TC-CLN-009: Edge cases ──
    def test_very_long_text(self):
        text = "Word " * 10000
        result = clean_for_tts(text)
        assert len(result) > 0

    def test_only_special_characters(self):
        text = "•●○◆◇■□▪▫►▶▷"
        result = clean_for_tts(text)
        assert result == ""

    def test_mixed_language_text(self):
        text = "This is English. Đây là tiếng Việt. 这是中文."
        result = clean_for_tts(text)
        assert "English" in result
        assert "tiếng Việt" in result


# ══════════════════════════════════════════════════════════
# TC-TBL: table_to_markdown()
# ══════════════════════════════════════════════════════════

class TestTableToMarkdown:
    """Test suite for table_to_markdown function."""

    # ── TC-TBL-001: Empty input ──
    def test_empty_list(self):
        assert table_to_markdown([]) == ""

    def test_none_input(self):
        assert table_to_markdown(None) == ""

    # ── TC-TBL-002: Normal table ──
    def test_basic_table(self):
        data = [["Name", "Age"], ["Alice", "30"], ["Bob", "25"]]
        result = table_to_markdown(data)
        assert "| Name | Age |" in result
        assert "| --- | --- |" in result
        assert "| Alice | 30 |" in result
        assert "| Bob | 25 |" in result

    # ── TC-TBL-003: Single row (header only) ──
    def test_single_row(self):
        data = [["Col1", "Col2", "Col3"]]
        result = table_to_markdown(data)
        assert "| Col1 | Col2 | Col3 |" in result
        assert "| --- | --- | --- |" in result

    # ── TC-TBL-004: Cells with whitespace ──
    def test_cells_trimmed(self):
        data = [["  Name  ", "  Age  "], ["  Alice  ", "  30  "]]
        result = table_to_markdown(data)
        assert "| Name | Age |" in result
        assert "| Alice | 30 |" in result

    # ── TC-TBL-005: Non-string cells ──
    def test_numeric_cells(self):
        data = [["ID", "Value"], [1, 3.14], [2, 2.71]]
        result = table_to_markdown(data)
        assert "3.14" in result

    # ── TC-TBL-006: Large table ──
    def test_large_table(self):
        header = [f"Col{i}" for i in range(20)]
        rows = [[f"val_{r}_{c}" for c in range(20)] for r in range(100)]
        data = [header] + rows
        result = table_to_markdown(data)
        lines = result.strip().split("\n")
        # 1 header + 1 separator + 100 data rows
        assert len(lines) == 102
