"""
D2S Pipeline — HeadingAwareChunker: split elements into chunks at heading boundaries.
Max 2500 words per chunk. Preserves section context.
"""
from dataclasses import dataclass, field

from config import CHUNK_MAX_WORDS
from logger import logger
from pipeline.parser import DocumentElement, ElementType


@dataclass
class Chunk:
    chunk_id: str = ""
    order: int = 0
    section_id: str = ""
    word_count: int = 0
    elements: list[DocumentElement] = field(default_factory=list)
    chunk_type: str = ""  # set by classifier


def _word_count(elements: list[DocumentElement]) -> int:
    total = 0
    for el in elements:
        if el.content:
            total += len(el.content.split())
        if el.table_data:
            for row in el.table_data:
                for cell in row:
                    total += len(str(cell).split())
    return total


def chunk_elements(elements: list[DocumentElement], max_words: int = CHUNK_MAX_WORDS) -> list[Chunk]:
    """
    Split elements into chunks at heading (H1/H2/H3) boundaries.
    Greedy packing: merge small sections, sub-chunk oversized ones at paragraph boundary.
    """
    if not elements:
        return []

    # Step 1: Split into sections at heading boundaries
    sections: list[list[DocumentElement]] = []
    current_section: list[DocumentElement] = []
    section_counter = 0

    for el in elements:
        if el.type == ElementType.HEADING and el.heading_level <= 3:
            if current_section:
                sections.append(current_section)
            current_section = [el]
        else:
            current_section.append(el)

    if current_section:
        sections.append(current_section)

    # Step 2: Build chunks with greedy packing
    chunks: list[Chunk] = []
    chunk_order = 0
    section_id_counter = 0

    pending_elements: list[DocumentElement] = []
    pending_section_id = "s0"

    for section in sections:
        section_id = f"s{section_id_counter}"
        section_id_counter += 1
        section_words = _word_count(section)

        if section_words == 0:
            continue

        # If adding this section to pending would exceed max, flush pending first
        combined_words = _word_count(pending_elements) + section_words
        if pending_elements and combined_words > max_words:
            # Flush pending as a chunk
            wc = _word_count(pending_elements)
            chunks.append(Chunk(
                chunk_id=f"c{chunk_order:03d}",
                order=chunk_order,
                section_id=pending_section_id,
                word_count=wc,
                elements=list(pending_elements),
            ))
            chunk_order += 1
            pending_elements = []

        if section_words <= max_words:
            if not pending_elements:
                pending_section_id = section_id
            pending_elements.extend(section)
        else:
            # Flush any pending first
            if pending_elements:
                wc = _word_count(pending_elements)
                chunks.append(Chunk(
                    chunk_id=f"c{chunk_order:03d}",
                    order=chunk_order,
                    section_id=pending_section_id,
                    word_count=wc,
                    elements=list(pending_elements),
                ))
                chunk_order += 1
                pending_elements = []

            # Sub-chunk oversized section at paragraph boundaries
            sub_elements: list[DocumentElement] = []
            for el in section:
                sub_elements.append(el)
                if _word_count(sub_elements) >= max_words:
                    wc = _word_count(sub_elements)
                    chunks.append(Chunk(
                        chunk_id=f"c{chunk_order:03d}",
                        order=chunk_order,
                        section_id=section_id,
                        word_count=wc,
                        elements=list(sub_elements),
                    ))
                    chunk_order += 1
                    sub_elements = []

            if sub_elements:
                pending_elements = sub_elements
                pending_section_id = section_id

    # Flush remaining
    if pending_elements:
        wc = _word_count(pending_elements)
        chunks.append(Chunk(
            chunk_id=f"c{chunk_order:03d}",
            order=chunk_order,
            section_id=pending_section_id,
            word_count=wc,
            elements=list(pending_elements),
        ))

    logger.info("Chunked %d elements into %d chunks (max %d words)", len(elements), len(chunks), max_words)
    return chunks
