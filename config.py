"""
D2S Pipeline — Configuration
All configuration centralized here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Groq LLM ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

LLM_CONFIG = {
    "provider": "groq",
    "model": "meta-llama/llama-4-maverick-17b-128e-instruct",
    "fallback_model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "max_tokens": 2048,
    "temperature": 0.3,
}

# --- TTS ---
TTS_CONFIG = {
    "engine": "edge-tts",
    "voice": os.getenv("TTS_VOICE", "vi-VN-HoaiMyNeural"),
    "rate": "+0%",
    "volume": "+0%",
}

# --- Audio ---
AUDIO_CONFIG = {
    "format": "mp3",
    "bitrate": "192k",
    "sample_rate": 44100,
    "channels": 1,
    "target_lufs": -16,
    "fade_in_ms": 500,
    "fade_out_ms": 1000,
    "gap_between_chunks_ms": 300,
    "gap_between_sections_ms": 800,
}

# --- Concurrency ---
CONCURRENCY_CONFIG = {
    "llm_semaphore": int(os.getenv("CONCURRENT_LLM", "5")),
    "tts_semaphore": int(os.getenv("CONCURRENT_TTS", "10")),
}

# --- Chunker ---
CHUNK_MAX_WORDS = int(os.getenv("CHUNK_MAX_WORDS", "2500"))

# --- URL Download ---
URL_DOWNLOAD_CONFIG = {
    "connect_timeout": 10,
    "download_timeout": 120,
    "max_redirects": 5,
    "max_file_size": 200 * 1024 * 1024,  # 200MB
    "user_agent": "D2S-Pipeline/1.0",
}

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
PROCESSING_DIR = os.path.join(DATA_DIR, "processing")
OUTPUTS_DIR = os.path.join(DATA_DIR, "outputs")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
TTS_CACHE_DIR = os.path.join(CACHE_DIR, "tts")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DB_PATH = os.path.join(DATA_DIR, "d2s.db")

# --- Cache TTL (days) ---
LLM_CACHE_TTL_DAYS = 30
TTS_CACHE_TTL_DAYS = 7

# --- File validation ---
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB

# --- Voice options ---
VOICE_OPTIONS = {
    "vi-VN-HoaiMyNeural": "HoaiMy (Nu)",
    "vi-VN-NamMinhNeural": "NamMinh (Nam)",
}
