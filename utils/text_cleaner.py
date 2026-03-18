"""
D2S Pipeline — Text cleanup for TTS input.
Normalize unicode, expand common abbreviations, remove noise.
"""
import re
import unicodedata


# Vietnamese-specific abbreviations
ABBREVIATIONS = {
    "TP.": "Thanh pho",
    "TP.HCM": "Thanh pho Ho Chi Minh",
    "Tp.": "Thanh pho",
    "Q.": "Quan",
    "P.": "Phuong",
    "TX.": "Thi xa",
    "TT.": "Thi tran",
    "Đ.": "Duong",
    "PGS.": "Pho Giao su",
    "GS.": "Giao su",
    "TS.": "Tien si",
    "ThS.": "Thac si",
    "CN.": "Cu nhan",
    "KS.": "Ky su",
    "BS.": "Bac si",
    "VNĐ": "Viet Nam dong",
    "VND": "Viet Nam dong",
    "USD": "do la My",
    "tr.": "trieu",
    "tỷ": "ty",
    "PGĐ": "Pho Giam doc",
    "GĐ": "Giam doc",
    "HĐQT": "Hoi dong quan tri",
    "CEO": "Tong Giam doc",
    "CFO": "Giam doc tai chinh",
}


def clean_for_tts(text: str) -> str:
    """Clean and normalize text for TTS synthesis."""
    if not text:
        return ""

    # 1. Unicode normalize (NFKC)
    text = unicodedata.normalize("NFKC", text)

    # 2. Remove page numbers (standalone numbers on a line)
    text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.MULTILINE)

    # 3. Remove headers/footers patterns
    text = re.sub(r"^(Trang|Page)\s*\d+.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)

    # 4. Expand abbreviations
    for abbr, full in ABBREVIATIONS.items():
        text = text.replace(abbr, full)

    # 5. Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)  # max 2 consecutive newlines
    text = re.sub(r"[ \t]+", " ", text)  # collapse spaces
    text = re.sub(r" *\n *", "\n", text)  # trim around newlines

    # 6. Remove special characters that TTS struggles with
    text = re.sub(r"[•●○◆◇■□▪▫►▶▷]", "", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)  # control chars

    # 7. Normalize quotes and dashes
    text = text.replace(""", '"').replace(""", '"')
    text = text.replace("'", "'").replace("'", "'")
    text = text.replace("–", "-").replace("—", "-")

    # 8. Clean up bullet points → sentence
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)

    return text.strip()


def table_to_markdown(table_data: list[list[str]]) -> str:
    """Convert table data (list of rows) to a markdown table string."""
    if not table_data:
        return ""

    lines = []
    for i, row in enumerate(table_data):
        line = "| " + " | ".join(str(cell).strip() for cell in row) + " |"
        lines.append(line)
        if i == 0:
            # Header separator
            lines.append("| " + " | ".join("---" for _ in row) + " |")

    return "\n".join(lines)
