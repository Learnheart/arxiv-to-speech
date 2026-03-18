"""
D2S Pipeline — DocumentParser: extract elements from DOCX and PDF.
"""
import io
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from logger import logger


class ElementType(Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    IMAGE = "image"


@dataclass
class DocumentElement:
    type: ElementType
    content: str = ""
    heading_level: int = 0  # 1, 2, 3 for headings
    table_data: list[list[str]] = field(default_factory=list)
    image_bytes: Optional[bytes] = None
    order: int = 0


def parse_docx(file_bytes: bytes) -> list[DocumentElement]:
    """Parse DOCX file using python-docx."""
    from docx import Document
    from docx.opc.constants import RELATIONSHIP_TYPE as RT

    doc = Document(io.BytesIO(file_bytes))
    elements: list[DocumentElement] = []
    order = 0

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = (para.style.name or "").lower()

        if "heading" in style_name:
            # Extract heading level
            level = 1
            for i in range(1, 4):
                if str(i) in style_name:
                    level = i
                    break
            elements.append(DocumentElement(
                type=ElementType.HEADING,
                content=text,
                heading_level=level,
                order=order,
            ))
        else:
            elements.append(DocumentElement(
                type=ElementType.PARAGRAPH,
                content=text,
                order=order,
            ))
        order += 1

    # Extract tables
    for table in doc.tables:
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows.append(cells)
        if rows:
            elements.append(DocumentElement(
                type=ElementType.TABLE,
                table_data=rows,
                order=order,
            ))
            order += 1

    # Extract images
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            try:
                image_bytes = rel.target_part.blob
                elements.append(DocumentElement(
                    type=ElementType.IMAGE,
                    image_bytes=image_bytes,
                    order=order,
                ))
                order += 1
            except Exception as e:
                logger.warning("Failed to extract DOCX image: %s", e)

    elements.sort(key=lambda e: e.order)
    logger.info("DOCX parsed: %d elements", len(elements))
    return elements


def parse_pdf(file_bytes: bytes) -> list[DocumentElement]:
    """Parse PDF file using PyMuPDF with font-size heuristic for headings."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    elements: list[DocumentElement] = []
    order = 0

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Extract text with font info
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        for block in blocks:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    text_parts = []
                    max_font_size = 0
                    for span in line["spans"]:
                        text_parts.append(span["text"])
                        max_font_size = max(max_font_size, span["size"])

                    text = " ".join(text_parts).strip()
                    if not text:
                        continue

                    # Font-size heuristic for headings
                    if max_font_size > 16:
                        elements.append(DocumentElement(
                            type=ElementType.HEADING,
                            content=text,
                            heading_level=1,
                            order=order,
                        ))
                    elif max_font_size > 13:
                        elements.append(DocumentElement(
                            type=ElementType.HEADING,
                            content=text,
                            heading_level=2,
                            order=order,
                        ))
                    elif max_font_size > 11.5:
                        elements.append(DocumentElement(
                            type=ElementType.HEADING,
                            content=text,
                            heading_level=3,
                            order=order,
                        ))
                    else:
                        elements.append(DocumentElement(
                            type=ElementType.PARAGRAPH,
                            content=text,
                            order=order,
                        ))
                    order += 1

            elif block["type"] == 1:  # Image block
                try:
                    xref = block.get("image", None)
                    if xref:
                        img = doc.extract_image(block["image"])
                        if img:
                            elements.append(DocumentElement(
                                type=ElementType.IMAGE,
                                image_bytes=img["image"],
                                order=order,
                            ))
                            order += 1
                except Exception as e:
                    logger.warning("Failed to extract PDF image on page %d: %s", page_num + 1, e)

        # Extract tables
        try:
            tables = page.find_tables()
            for table in tables:
                rows = []
                for row in table.extract():
                    cells = [str(cell) if cell is not None else "" for cell in row]
                    rows.append(cells)
                if rows:
                    elements.append(DocumentElement(
                        type=ElementType.TABLE,
                        table_data=rows,
                        order=order,
                    ))
                    order += 1
        except Exception as e:
            logger.warning("Failed to extract tables from page %d: %s", page_num + 1, e)

    doc.close()
    elements.sort(key=lambda e: e.order)
    logger.info("PDF parsed: %d elements from %d pages", len(elements), len(doc))
    return elements


def parse_document(file_bytes: bytes, file_type: str) -> list[DocumentElement]:
    """Parse a document file and return ordered elements."""
    if file_type == "docx":
        return parse_docx(file_bytes)
    elif file_type == "pdf":
        return parse_pdf(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")
