# Document-to-Speech Pipeline (D2S)

Chuyen doi tai lieu DOCX/PDF thanh file audio MP3 tu dong, su dung AI de mo ta hinh anh va bang bieu thanh loi noi tu nhien.

## Yeu cau he thong

| Thanh phan | Phien ban |
|------------|-----------|
| Python | >= 3.11 |
| FFmpeg | bat ky (can cho xuat MP3) |
| OS | Windows / macOS / Linux |

## Cai dat

### 1. Clone repository

```bash
git clone <repo-url>
cd arxiv-to-speech
```

### 2. Tao virtual environment (khuyen nghi)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Cai dat dependencies

```bash
pip install -r requirements.txt
```

### 4. Cai dat FFmpeg

FFmpeg can thiet de `pydub` xuat file MP3.

**Windows (chon 1 trong 2 cach):**

```bash
# Cach 1: Dung winget
winget install Gyan.FFmpeg

# Cach 2: Dung choco
choco install ffmpeg
```

Sau khi cai, khoi dong lai terminal va kiem tra:

```bash
ffmpeg -version
```

**macOS:**

```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**

```bash
sudo apt update && sudo apt install ffmpeg
```

### 5. Cau hinh environment variables

Copy file `.env.example` thanh `.env` va dien API key:

```bash
cp .env.example .env
```

Mo file `.env` va chinh sua:

```env
# BAT BUOC - Lay tai https://console.groq.com/keys
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx

# TUY CHON - Co the giu mac dinh
TTS_VOICE=vi-VN-HoaiMyNeural
CHUNK_MAX_WORDS=2500
CONCURRENT_LLM=5
CONCURRENT_TTS=10
```

> **Lay Groq API Key:** Truy cap https://console.groq.com/keys, dang ky tai khoan mien phi, tao API key moi.

## Chay ung dung

```bash
python app.py
```

Ung dung se khoi dong tai: **http://127.0.0.1:7860**

Mo trinh duyet va truy cap dia chi tren.

## Huong dan su dung

### Upload file

1. Mo tab **"Upload File"**
2. Keo tha hoac chon file DOCX/PDF (toi da 200MB)
3. Chon giong doc (HoaiMy - Nu / NamMinh - Nam)
4. Bam **"Bat dau xu ly"**
5. Cho pipeline xu ly (co thanh tien trinh)
6. Nghe audio truc tiep hoac tai file MP3 ve

### Dan URL

1. Mo tab **"Dan URL"**
2. Dan link truc tiep toi file DOCX/PDF
   - Ho tro: Google Drive, Dropbox, OneDrive
   - Vi du: `https://drive.google.com/file/d/xxx/view`
3. Bam **"Tai va xu ly"**

## Chay tests

Cai dat test dependencies:

```bash
pip install pytest pytest-asyncio
```

Chay toan bo test suite:

```bash
python -m pytest tests/ -v
```

Chay test cho 1 module cu the:

```bash
# Vi du: chi test phan chunker
python -m pytest tests/test_chunker.py -v

# Chi test phan validator
python -m pytest tests/test_validator.py -v
```

## Cau truc du an

```
arxiv-to-speech/
├── app.py                  # Entry point - Gradio UI (port 7860)
├── config.py               # Cau hinh tap trung
├── logger.py               # Logging voi daily rotation
├── requirements.txt        # Dependencies
├── .env.example            # Template environment variables
├── pytest.ini              # Cau hinh pytest
│
├── db/
│   └── models.py           # SQLite schema + CRUD
│
├── llm/
│   └── groq_client.py      # Groq API client (mo ta hinh/bang)
│
├── pipeline/
│   ├── orchestrator.py     # Dieu phoi pipeline 7 giai doan
│   ├── parser.py           # Parse DOCX/PDF → DocumentElement[]
│   ├── chunker.py          # Tach chunks theo heading (max 2500 words)
│   ├── classifier.py       # Phan loai: TEXT/TABLE/IMAGE/MIXED
│   ├── enricher.py         # LLM enrichment cho hinh anh/bang
│   ├── synthesizer.py      # Edge TTS → MP3
│   └── stitcher.py         # Ghep audio + normalize volume
│
├── utils/
│   ├── text_cleaner.py     # Normalize unicode, expand viet tat
│   ├── validator.py        # Kiem tra magic bytes + file size
│   ├── cache.py            # SQLite cache (LLM 30 ngay, TTS 7 ngay)
│   ├── retry.py            # Exponential backoff
│   └── downloader.py       # Download URL voi SSRF protection
│
└── tests/                  # 208 test cases
    ├── conftest.py
    ├── test_text_cleaner.py
    ├── test_validator.py
    ├── test_cache.py
    ├── test_retry.py
    ├── test_downloader.py
    ├── test_parser.py
    ├── test_chunker.py
    ├── test_classifier.py
    ├── test_enricher.py
    ├── test_synthesizer.py
    ├── test_stitcher.py
    ├── test_groq_client.py
    ├── test_db_models.py
    ├── test_orchestrator.py
    └── test_app.py
```

## Pipeline xu ly

```
Upload/URL → Validate → Parse → Chunk → Classify → Enrich+TTS → Stitch → MP3
               │          │        │        │            │           │
            magic bytes  DOCX/   heading  TEXT/TABLE   LLM cho    ghep audio
            + size check  PDF    boundary  IMAGE/MIXED  hinh/bang  + normalize
                                 max 2500w             Edge TTS    -16 LUFS
```

## Cau hinh nang cao

| Bien moi truong | Mac dinh | Mo ta |
|-----------------|----------|-------|
| `GROQ_API_KEY` | *(bat buoc)* | API key tu Groq |
| `TTS_VOICE` | `vi-VN-HoaiMyNeural` | Giong doc TTS |
| `CHUNK_MAX_WORDS` | `2500` | So tu toi da moi chunk |
| `CONCURRENT_LLM` | `5` | So luong LLM request song song |
| `CONCURRENT_TTS` | `10` | So luong TTS request song song |

## Xu ly su co

| Van de | Nguyen nhan | Cach xu ly |
|--------|-------------|------------|
| `ModuleNotFoundError` | Chua cai dependencies | `pip install -r requirements.txt` |
| `FileNotFoundError: ffmpeg` | Chua cai FFmpeg | Cai FFmpeg theo huong dan o tren |
| `GROQ_API_KEY not set` | Chua cau hinh .env | Tao file `.env` voi API key |
| Pipeline cham | Nhieu hinh/bang can LLM | Tang `CONCURRENT_LLM` (luu y rate limit) |
| Audio bi ngat quang | Chunk bi fail | Kiem tra log tai `logs/d2s.log` |
| Loi "File khong hop le" | Sai dinh dang file | Chi ho tro DOCX va PDF |
