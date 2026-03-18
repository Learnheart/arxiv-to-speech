"""
D2S Pipeline — ContentClassifier: rule-based classification of chunk types.
Types: TEXT, TABLE, IMAGE, MIXED
"""
from logger import logger
from pipeline.chunker import Chunk
from pipeline.parser import ElementType


class ChunkType:
    TEXT = "TEXT"
    TABLE = "TABLE"
    IMAGE = "IMAGE"
    MIXED = "MIXED"


def classify_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Assign chunk_type to each chunk based on its element composition."""
    type_counts = {ChunkType.TEXT: 0, ChunkType.TABLE: 0, ChunkType.IMAGE: 0, ChunkType.MIXED: 0}

    for chunk in chunks:
        has_table = False
        has_image = False

        for el in chunk.elements:
            if el.type == ElementType.TABLE:
                has_table = True
            elif el.type == ElementType.IMAGE:
                has_image = True

        if has_table and has_image:
            chunk.chunk_type = ChunkType.MIXED
        elif has_table:
            chunk.chunk_type = ChunkType.TABLE
        elif has_image:
            chunk.chunk_type = ChunkType.IMAGE
        else:
            chunk.chunk_type = ChunkType.TEXT

        type_counts[chunk.chunk_type] += 1

    logger.info(
        "Classified %d chunks: TEXT=%d, TABLE=%d, IMAGE=%d, MIXED=%d",
        len(chunks),
        type_counts[ChunkType.TEXT],
        type_counts[ChunkType.TABLE],
        type_counts[ChunkType.IMAGE],
        type_counts[ChunkType.MIXED],
    )
    return chunks
