# Document-to-Speech Pipeline — Architecture Document (Simplified POC)

| | |
|---|---|
| **Hệ thống** | Document-to-Speech Pipeline (D2S) |
| **Version** | 1.0.0-POC |
| **Date** | 18/03/2026 |
| **Status** | Approved for POC Development |
| **Scope** | Personal use — single user, local machine |

---

## Mục lục

- [1. Executive Summary](#1-executive-summary)
- [2. Bối cảnh & Bài toán](#2-bối-cảnh--bài-toán)
- [3. Phạm vi hệ thống](#3-phạm-vi-hệ-thống)
- [4. Kiến trúc High-Level](#4-kiến-trúc-high-level)
  - [4.1. System Context](#41-system-context)
  - [4.2. Application Architecture](#42-application-architecture)
  - [4.3. Processing Pipeline](#43-processing-pipeline)
  - [4.4. LLM & TTS Configuration](#44-llm--tts-configuration)
  - [4.5. Data Flow tổng quan](#45-data-flow-tổng-quan)
- [5. Sequence Diagrams](#5-sequence-diagrams)
  - [5.1. Upload & Validate](#51-upload--validate)
  - [5.2. Parse, Chunk & Classify](#52-parse-chunk--classify)
  - [5.3. LLM Enrichment](#53-llm-enrichment)
  - [5.4. TTS Synthesis](#54-tts-synthesis)
  - [5.5. Audio Stitch & Delivery](#55-audio-stitch--delivery)
  - [5.6. Error Handling & Retry](#56-error-handling--retry)
- [6. Tech Stack](#6-tech-stack)
- [7. Quyết định kiến trúc (ADRs)](#7-quyết-định-kiến-trúc-adrs)
- [8. Yêu cầu phi chức năng](#8-yêu-cầu-phi-chức-năng)
- [9. API & UI Specification](#9-api--ui-specification)
- [10. Data Models](#10-data-models)
- [11. Caching Strategy](#11-caching-strategy)
- [12. Security Considerations](#12-security-considerations)
- [13. Budget ước tính](#13-budget-ước-tính)
- [14. Roadmap](#14-roadmap)
- [Phụ lục](#phụ-lục)

---

## 1. Executive Summary

Document-to-Speech Pipeline (D2S) là công cụ cá nhân tự động chuyển đổi tài liệu thành audio chất lượng cao. Hệ thống nhận input linh hoạt — upload file (DOCX/PDF) hoặc dán URL trực tiếp tới file — parse cấu trúc document, nhận diện bảng biểu và hình ảnh, sử dụng LLM để diễn giải nội dung phi văn bản thành đoạn tường thuật tự nhiên, sau đó tổng hợp giọng nói.

**Nguyên tắc thiết kế POC:**
- **Đơn giản nhất có thể** — 1 process Python duy nhất, không distributed system
- **Zero infrastructure** — không Docker, không Redis, không MinIO
- **UI nhanh** — Gradio (Python) thay vì React SPA
- **Chạy được ngay** — `pip install` + `python app.py` là xong

---

## 2. Bối cảnh & Bài toán

### 2.1. Problem Statement

Tài liệu (báo cáo, nghiên cứu, sách) nhiều nhưng thời gian đọc hạn chế. Cần chuyển sang dạng audio để nghe khi di chuyển, tập thể dục, hoặc nghỉ mắt.

### 2.2. Giải pháp

Automated pipeline: nhận file DOCX/PDF → xử lý thông minh mọi loại nội dung (text, bảng, ảnh) → xuất audio MP3.

### 2.3. Mục tiêu đo lường

| # | Mục tiêu | KPI |
|---|----------|-----|
| G1 | Tự động hóa 100% doc → audio | Không can thiệp thủ công |
| G2 | Chi phí gần bằng không | Edge TTS free + Groq free tier |
| G3 | Hỗ trợ đa dạng nội dung | Text, table, image |
| G4 | Xử lý chấp nhận được | < 15 phút cho tài liệu 50 trang |
| G5 | Chất lượng nghe được | Giọng tự nhiên, đúng ngữ cảnh |

---

## 3. Phạm vi hệ thống

### 3.1. In Scope (POC)

- **Input linh hoạt**: upload file DOCX/PDF **hoặc** dán URL trực tiếp tới file (auto-download)
- Tách file thành chunks thông minh theo heading
- Nhận diện nội dung: text, bảng, hình ảnh
- Gọi LLM diễn giải bảng/ảnh thành văn bản tường thuật
- Tổng hợp giọng nói (TTS) toàn bộ nội dung
- Xuất file MP3
- Web UI cơ bản: upload/URL input, progress, nghe, tải

### 3.2. Out of Scope (POC)

- Định dạng ngoài DOCX/PDF
- Web page scraping (HTML → text) — chỉ hỗ trợ URL trỏ trực tiếp tới file
- Đa ngôn ngữ nâng cao, clone voice
- Mobile app, user authentication, multi-tenancy
- Streaming audio realtime (nghe từng chunk khi đang xử lý)
- A/B testing giữa các model
- Distributed processing, auto-scaling
- Docker / container deployment

### 3.3. Giả định

- 1 người dùng duy nhất, chạy trên máy cá nhân
- Tài liệu có cấu trúc heading tương đối rõ
- Hình ảnh mang tính thông tin (chart, diagram)
- Mạng internet ổn định cho LLM API và Edge TTS
- Máy tối thiểu 8GB RAM, 4 CPU cores

---

## 4. Kiến trúc High-Level

### 4.1. System Context

```mermaid
graph LR
    User["👤 Người dùng"] -->|"Upload file DOCX/PDF\nHOẶC dán URL tới file\nNghe/Tải audio"| D2S["🎙 D2S\n(Python App)"]

    Web["🌐 External File Server"] -->|"Download DOCX/PDF\n(via URL)"| D2S

    D2S -->|"Image/Table → Text"| Groq["Groq API\n(Llama 4 Maverick)"]
    D2S -->|"Text → Audio"| Edge["Edge TTS\n(free)"]

    style D2S fill:#E6F1FB,stroke:#378ADD,stroke-width:2px
```

External interactions:
- **External File Server** — download file từ URL do user cung cấp (Google Drive, Dropbox share link, direct link...)
- **Groq API** — mô tả ảnh + diễn giải bảng (primary: Llama 4 Maverick, fallback: Llama 4 Scout — cùng provider)
- **Edge TTS** — TTS tiếng Việt miễn phí, chất lượng tốt

### 4.2. Application Architecture

```mermaid
graph TB
    subgraph "Python Application (1 process, asyncio event loop)"
        UI["Gradio UI\n:7860\nUpload · Progress · Audio Player"]
        API["FastAPI\n:8000\n(optional — nếu cần REST API)"]

        subgraph "Pipeline Engine"
            direction TB
            PP["DocumentParser"] --> CH["HeadingAwareChunker"]
            CH --> CL["ContentClassifier"]

            subgraph "Async Concurrent Processing"
                direction LR
                EN["LLMEnricher\n(asyncio)"]
                TTS["TTSSynthesizer\n(asyncio)"]
                EN --> TTS
            end

            CL -->|"fan-out\nchunks"| EN
            TTS -->|"fan-in\nordered results"| ST["AudioStitcher"]
        end

        subgraph "Data Layer"
            DB["SQLite\n(job metadata + LLM/TTS cache)"]
            FS["Local Filesystem\n./data/uploads/\n./data/outputs/"]
        end
    end

    UI --> PP
    EN -->|"async API calls"| ExtLLM["Groq API"]
    TTS -->|"async API calls"| ExtTTS["Edge TTS"]
    EN & TTS -.->|"cache read/write"| DB
    PP -.->|"read file"| FS
    ST -.->|"write audio"| FS

    style UI fill:#E1F5EE,stroke:#5DCAA5
```

**Toàn bộ hệ thống là 1 Python process duy nhất:**

| Component | Công nghệ | Vai trò |
|-----------|-----------|---------|
| UI | Gradio 5 | Upload, progress bar, audio player, download |
| API (optional) | FastAPI + Uvicorn | REST endpoint nếu muốn gọi từ script/CLI |
| Pipeline | Python modules + asyncio | 6 stages: 3 sequential → enrich+TTS concurrent → stitch |
| Database | SQLite (via sqlite3) | Job metadata + cache |
| Storage | Local filesystem | Files upload + audio output |

**Không có:** Redis, MinIO, Celery, Docker, React, Node.js.

### 4.3. Processing Pipeline

Pipeline gồm 6 stages. Trong đó 3 stages đầu chạy tuần tự (cần output của stage trước), còn **Enrich + TTS xử lý song song nhiều chunks cùng lúc** qua `asyncio`:

```mermaid
graph LR
    A["📄 Document\nParser"] --> B["✂️ Heading-Aware\nChunker"]
    B --> C["🏷️ Content\nClassifier"]
    C --> D["🤖 LLM Enricher\n+ 🔊 TTS\n(async concurrent)"]
    D --> F["🎵 Audio\nStitcher"]

    style A fill:#FAEEDA,stroke:#EF9F27
    style B fill:#FAEEDA,stroke:#EF9F27
    style C fill:#FAEEDA,stroke:#EF9F27
    style D fill:#EEEDFE,stroke:#AFA9EC
    style F fill:#FAECE7,stroke:#F0997B
```

| Stage | Module | Input | Output | Processing | Mô tả |
|-------|--------|-------|--------|-----------|-------|
| 1 | `DocumentParser` | file_bytes | `elements[]` | Sequential | Parse cấu trúc DOCX/PDF. Trích xuất text, headings, tables, images |
| 2 | `HeadingAwareChunker` | `elements[]` | `chunks[]` | Sequential | Tách theo heading boundary (H1/H2/H3). Max 2500 từ/chunk |
| 3 | `ContentClassifier` | `chunks[]` | `chunks[]` + type | Sequential | Rule-based: gán TEXT, TABLE, IMAGE, MIXED |
| 4 | `LLMEnricher` | classified chunks | enriched text | **Concurrent** | TEXT → pass-through. TABLE → LLM narrate. IMAGE → LLM describe |
| 5 | `TTSSynthesizer` | enriched text | audio segments | **Concurrent** | Chuyển text thành audio qua Edge TTS |
| 6 | `AudioStitcher` | audio segments | final audio | Sequential | Concat, normalize, silence gaps, fade. Export MP3 |

#### Concurrent Processing Model

Sau khi classify xong, mỗi chunk được xử lý **độc lập** (enrich → TTS) qua `asyncio.gather`. Thứ tự đảm bảo nhờ `chunk.order` — dù chunk nào xong trước/sau, kết quả luôn được collect theo đúng order ban đầu.

```mermaid
graph TB
    CL["Classifier output\nchunks[0..11] with types"] --> FAN["Fan-out\nasyncio.gather"]

    FAN --> T0["chunk[0] TEXT\nclean → TTS"]
    FAN --> T1["chunk[1] TEXT\nclean → TTS"]
    FAN --> T2["chunk[2] IMAGE\nLLM describe → TTS"]
    FAN --> T3["chunk[3] TEXT\nclean → TTS"]
    FAN --> T4["chunk[4] TABLE\nLLM narrate → TTS"]
    FAN --> T5["chunk[5..11]\n..."]

    T0 --> COLLECT["Collect by order\nresults[0..11]"]
    T1 --> COLLECT
    T2 --> COLLECT
    T3 --> COLLECT
    T4 --> COLLECT
    T5 --> COLLECT

    COLLECT --> ST["AudioStitcher\n(sort by order → stitch)"]

    style FAN fill:#EEEDFE,stroke:#AFA9EC
    style COLLECT fill:#E1F5EE,stroke:#5DCAA5
```

**Tại sao không cần Redis/Celery?**

`asyncio` là in-process concurrency — đủ mạnh cho I/O-bound tasks (gọi API, chờ response). Không cần distributed queue vì:
- 1 user, 1 job tại 1 thời điểm
- Bottleneck là network I/O (LLM API, TTS API), không phải CPU
- `asyncio.Semaphore` kiểm soát concurrency (tránh rate limit)
- `asyncio.gather` tự bảo toàn thứ tự kết quả

```python
# Minh họa core logic
async def process_chunk(chunk: Chunk, semaphore: asyncio.Semaphore) -> AudioSegment:
    """Enrich + TTS cho 1 chunk. Chạy concurrent với các chunks khác."""
    async with semaphore:
        # Phase 1: Enrich (rẽ nhánh theo type)
        if chunk.type == "TEXT":
            enriched = clean_for_tts(chunk.text)            # instant
        elif chunk.type == "IMAGE":
            enriched = await llm_describe_image(chunk.image) # ~3-5s
        elif chunk.type == "TABLE":
            enriched = await llm_narrate_table(chunk.table)  # ~3-5s
        elif chunk.type == "MIXED":
            enriched = await enrich_mixed(chunk)             # ~3-5s

        # Phase 2: TTS
        audio = await tts_synthesize(enriched)               # ~2-3s
        return AudioSegment(order=chunk.order, audio=audio)

async def run_pipeline(chunks: list[Chunk]) -> list[AudioSegment]:
    sem = asyncio.Semaphore(5)  # max 5 concurrent API calls

    # Fan-out: tất cả chunks chạy song song
    # Fan-in: gather trả kết quả ĐÚNG THỨ TỰ input
    results = await asyncio.gather(
        *[process_chunk(c, sem) for c in chunks]
    )
    # results[0] = chunk[0], results[1] = chunk[1], ... (guaranteed order)
    return results
```

**Concurrency controls:**

| Resource | Semaphore limit | Lý do |
|----------|----------------|-------|
| Groq API | 5 concurrent | Free tier: 30 RPM → 5 concurrent an toàn |
| Edge TTS | 10 concurrent | Free, không rate limit nghiêm ngặt |

**So sánh hiệu năng (12 chunks, 4 non-text):**

| Mode | Enrich time | TTS time | Total (enrich+TTS) |
|------|-------------|----------|---------------------|
| Sequential | ~16s (4 × 4s) | ~36s (12 × 3s) | ~52s |
| Concurrent (sem=5) | ~8s | ~9s | ~17s |
| **Speedup** | | | **~3x nhanh hơn** |

### 4.4. LLM & TTS Configuration

Không cần Provider Registry pattern phức tạp. Dùng simple config:

```python
# config.py
LLM_CONFIG = {
    "provider": "groq",
    "model": "meta-llama/llama-4-maverick-17b-128e-instruct",
    "fallback_model": "meta-llama/llama-4-scout-17b-16e-instruct",
    "max_tokens": 2048,
    "temperature": 0.3,
}

TTS_CONFIG = {
    "engine": "edge-tts",
    "voice": "vi-VN-HoaiMyNeural",
    "rate": "+0%",
    "volume": "+0%"
}

AUDIO_CONFIG = {
    "format": "mp3",
    "bitrate": "192k",
    "sample_rate": 44100,
    "channels": 1,               # mono
    "target_lufs": -16,
    "fade_in_ms": 500,
    "fade_out_ms": 1000,
    "gap_between_chunks_ms": 300,
    "gap_between_sections_ms": 800
}

CONCURRENCY_CONFIG = {
    "llm_semaphore": 5,          # max concurrent LLM calls (Groq free: 30 RPM)
    "tts_semaphore": 10,         # max concurrent TTS calls (Edge TTS: generous)
}

URL_DOWNLOAD_CONFIG = {
    "connect_timeout": 10,       # seconds — tránh treo khi server không phản hồi
    "download_timeout": 120,     # seconds — đủ cho file 200MB
    "max_redirects": 5,          # Google Drive, short URL thường redirect 2-3 lần
    "max_file_size": 200 * 1024 * 1024,  # 200MB — consistent với upload limit
    "user_agent": "D2S-Pipeline/1.0",
    "supported_content_types": [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",  # Một số server trả generic type
    ],
}
```

**Thêm provider mới khi nào?** Khi POC đã validate xong và cần so sánh chất lượng giữa nhiều engine. Lúc đó refactor sang Registry pattern — có data thực tế để justify complexity.

### 4.5. Data Flow tổng quan

```mermaid
graph TB
    subgraph "① Input & Validate"
        I0A["📁 Upload File"] -->|"validate\n(magic bytes)"| I2["./data/uploads/{job_id}/"]
        I0B["🔗 Dán URL"] -->|"download\n(httpx async)"| I0C["file_bytes"]
        I0C -->|"validate\n(magic bytes)"| I2
    end

    subgraph "② Parse (sequential)"
        I2 -->|"read file"| P1["elements[]\n{text, table, image,\nheading_level, order}"]
    end

    subgraph "③ Chunk + Classify (sequential)"
        P1 -->|"heading-aware split\n+ rule-based classify"| P3["chunks[0..N] with types\nTEXT × 8, TABLE × 2,\nIMAGE × 1, MIXED × 1"]
    end

    subgraph "④⑤ Enrich + TTS (async concurrent)"
        P3 -->|"fan-out\nasyncio.gather"| CONC["Mỗi chunk xử lý độc lập:\nTEXT → clean → TTS\nIMAGE → LLM → TTS\nTABLE → LLM → TTS\n(Semaphore giới hạn concurrent)"]
        CONC -->|"fan-in\nordered results"| P5["audio_segments[0..N]\nMP3 per chunk\n(đúng thứ tự)"]
    end

    subgraph "⑥ Stitch & Deliver (sequential)"
        P5 -->|"concat + normalize"| O1["final_audio.mp3\n./data/outputs/{job_id}/"]
        O1 -->|"Gradio player"| O2["🔊 Play / 📥 Download"]
    end
```

---

## 5. Sequence Diagrams

### 5.1. Upload & Validate

Hệ thống hỗ trợ **2 cách nhập input**: upload file trực tiếp hoặc dán URL tới file. Cả 2 đều hội tụ về cùng pipeline xử lý sau khi file được lưu local.

#### 5.1a. Upload File (Drag & Drop)

```mermaid
sequenceDiagram
    actor User
    participant UI as Gradio UI
    participant Val as File Validator
    participant FS as Local Filesystem
    participant DB as SQLite

    User->>UI: Upload file (drag & drop)
    UI->>Val: validate(file_bytes, filename)
    Val->>Val: Magic bytes check\n(PK→DOCX, %PDF→PDF)
    Val->>Val: File size check (≤ 200MB)

    alt File không hợp lệ
        Val-->>UI: ❌ Invalid
        UI-->>User: ⚠️ "File không hợp lệ"
    else File hợp lệ
        Val-->>UI: ✅ { type: "pdf", size: 2.4MB }
        UI->>FS: Save → ./data/uploads/{job_id}/original.pdf
        UI->>DB: INSERT job { id, file_path, status: "processing" }
        UI-->>User: ✅ "Đang xử lý..."
        UI->>UI: Start pipeline (background thread)
    end
```

#### 5.1b. URL Input (Auto-Download)

```mermaid
sequenceDiagram
    actor User
    participant UI as Gradio UI
    participant DL as URLDownloader
    participant Val as File Validator
    participant FS as Local Filesystem
    participant DB as SQLite

    User->>UI: Dán URL vào ô input
    UI->>UI: Validate URL format\n(https only, domain allowlist optional)

    alt URL format không hợp lệ
        UI-->>User: ⚠️ "URL không hợp lệ"
    else URL hợp lệ
        UI-->>User: ⏳ "Đang tải file..."
        UI->>DL: download(url, timeout=60s)

        DL->>DL: HEAD request\n→ Check Content-Type\n→ Check Content-Length (≤ 200MB)

        alt HEAD check fail
            DL-->>UI: ❌ "File không phải DOCX/PDF\nhoặc quá lớn"
            UI-->>User: ⚠️ Error message
        else HEAD check OK
            DL->>DL: GET request (stream)\n→ Download with progress\n→ Timeout 120s, max 200MB
            DL->>DL: Follow redirects (max 5 hops)
            DL-->>UI: file_bytes + detected_filename

            UI->>Val: validate(file_bytes, filename)
            Val->>Val: Magic bytes check\n(PK→DOCX, %PDF→PDF)

            alt File không hợp lệ
                Val-->>UI: ❌ Invalid
                UI-->>User: ⚠️ "File tải về không phải\nDOCX/PDF hợp lệ"
            else File hợp lệ
                Val-->>UI: ✅ { type: "pdf", size: 2.4MB }
                UI->>FS: Save → ./data/uploads/{job_id}/original.pdf
                UI->>DB: INSERT job { id, file_path, source_url,\nstatus: "processing" }
                UI-->>User: ✅ "Đang xử lý..."
                UI->>UI: Start pipeline (background thread)
            end
        end
    end
```

**URL Download — Chi tiết kỹ thuật:**

| Thông số | Giá trị | Lý do |
|----------|---------|-------|
| HTTP client | `httpx` (async) | Đã có trong dependency, hỗ trợ async + streaming |
| Timeout (connect) | 10s | Tránh treo khi server không phản hồi |
| Timeout (download) | 120s | Đủ cho file 200MB qua mạng trung bình |
| Max redirects | 5 | Xử lý short URL, CDN redirect |
| Max file size | 200MB | Consistent với upload limit |
| Supported protocols | HTTPS only | Bảo mật cơ bản, tránh MITM |
| User-Agent | `D2S-Pipeline/1.0` | Tránh bị block bởi CDN |

**Supported URL patterns:**

| Source | URL pattern | Ghi chú |
|--------|------------|---------|
| Direct link | `https://example.com/file.pdf` | Download trực tiếp |
| Google Drive | `https://drive.google.com/file/d/{id}/...` | Cần convert sang direct download link |
| Dropbox | `https://www.dropbox.com/s/{id}/file.pdf?dl=0` | Đổi `dl=0` → `dl=1` |
| OneDrive | `https://onedrive.live.com/...` | Convert sang direct download link |
| Generic CDN | Bất kỳ URL trả về DOCX/PDF | Dựa vào Content-Type + magic bytes |

**URL conversion logic (pseudo-code):**

```python
def normalize_download_url(url: str) -> str:
    """Convert sharing URLs thành direct download URLs."""
    parsed = urlparse(url)

    # Google Drive: /file/d/{id}/view → direct download
    if "drive.google.com" in parsed.netloc:
        file_id = extract_gdrive_id(url)
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    # Dropbox: dl=0 → dl=1
    if "dropbox.com" in parsed.netloc:
        return url.replace("dl=0", "dl=1").replace("www.dropbox.com", "dl.dropboxusercontent.com")

    # OneDrive: convert to direct
    if "onedrive.live.com" in parsed.netloc or "1drv.ms" in parsed.netloc:
        return convert_onedrive_to_direct(url)

    # Default: dùng URL gốc
    return url
```

### 5.2. Parse, Chunk & Classify

```mermaid
sequenceDiagram
    participant PL as Pipeline
    participant FS as Local Filesystem
    participant P as DocumentParser
    participant C as HeadingAwareChunker
    participant CL as ContentClassifier
    participant UI as Gradio (progress)

    PL->>UI: progress(0.1, "Đang parse document...")
    PL->>FS: Read file_bytes
    FS-->>PL: file_bytes (2.4MB)

    PL->>P: parse(file_bytes, "pdf")
    alt DOCX
        P->>P: python-docx: paragraphs,\nheading styles, tables, images
    else PDF
        P->>P: PyMuPDF: text blocks,\nfont-size heuristic for headings,\nfind_tables(), extract images
    end
    P-->>PL: elements[] — {type, content, table_data,\nimage_bytes, heading_level, order}

    PL->>UI: progress(0.2, "Đang tách chunks...")
    PL->>C: chunk(elements, max_words=2500)
    C->>C: Split at H1/H2/H3 boundaries
    C->>C: Greedy packing: merge small sections,\nsub-chunk oversized ones at paragraph boundary
    C-->>PL: chunks[] — 12 chunks, ordered

    PL->>UI: progress(0.25, "Đang phân loại...")
    PL->>CL: classify(chunks)
    loop Each chunk
        alt Only text + headings
            CL->>CL: type = TEXT
        else Has table elements
            CL->>CL: type = TABLE or MIXED
        else Has image elements
            CL->>CL: type = IMAGE or MIXED
        end
    end
    CL-->>PL: chunks[] with types\n[TEXT×8, TABLE×2, IMAGE×1, MIXED×1]
```

### 5.3. Enrich + TTS (Async Concurrent)

Sau khi classify, tất cả chunks được fan-out xử lý song song. Mỗi chunk đi qua pipeline riêng: **Enrich → TTS**. Kết quả được collect theo đúng thứ tự ban đầu.

```mermaid
sequenceDiagram
    participant PL as Pipeline<br/>(asyncio event loop)
    participant SEM as Semaphore(5)
    participant Cache as SQLite Cache
    participant Groq as Groq API<br/>(Llama 4 Maverick)
    participant TTS as Edge TTS
    participant FS as Local FS
    participant UI as Gradio progress

    PL->>UI: progress(0.3, "Xử lý chunks song song...")

    PL->>PL: asyncio.gather(\n  process_chunk(chunk[0]),\n  process_chunk(chunk[1]),\n  ...\n  process_chunk(chunk[11])\n)

    Note over PL,TTS: ═══ Các chunks chạy SONG SONG ═══\nDưới đây minh họa 3 chunks concurrent

    par chunk[0] — TEXT (nhanh nhất)
        PL->>PL: clean_for_tts(text)\n(instant, không cần LLM)
        PL->>SEM: acquire TTS slot
        SEM-->>PL: OK
        PL->>Cache: SELECT tts cache
        alt Cache MISS
            PL->>TTS: edge_tts.communicate(text, voice)
            TTS-->>PL: audio_bytes ✅
            PL->>Cache: INSERT tts cache
        end
        PL->>FS: Save seg_000.mp3
        PL->>SEM: release TTS slot
        PL->>UI: progress update
    and chunk[2] — IMAGE (cần LLM → TTS)
        PL->>SEM: acquire LLM slot
        SEM-->>PL: OK
        PL->>Cache: SELECT llm cache
        alt Cache MISS
            PL->>Groq: describe_image(bytes, prompt)\n[model: Maverick]
            alt Success
                Groq-->>PL: "Biểu đồ doanh thu Q3..."
            else Fail → retry 3x → fallback model
                PL->>Groq: describe_image(bytes, prompt)\n[model: Scout]
                Groq-->>PL: description
            end
            PL->>Cache: INSERT llm cache (TTL 30d)
        end
        PL->>SEM: release LLM slot
        PL->>SEM: acquire TTS slot
        PL->>TTS: edge_tts.communicate(enriched, voice)
        TTS-->>PL: audio_bytes ✅
        PL->>Cache: INSERT tts cache (TTL 7d)
        PL->>FS: Save seg_002.mp3
        PL->>SEM: release TTS slot
    and chunk[4] — TABLE (cần LLM → TTS)
        PL->>SEM: acquire LLM slot
        SEM-->>PL: OK (hoặc wait nếu đã đủ 5)
        PL->>PL: table_md = table_to_markdown()
        PL->>Cache: SELECT llm cache
        alt Cache MISS
            PL->>Groq: narrate_table(table_md, prompt)\n[model: Maverick]
            Groq-->>PL: "Bảng cho thấy..." ✅
            PL->>Cache: INSERT llm cache
        end
        PL->>SEM: release LLM slot
        PL->>SEM: acquire TTS slot
        PL->>TTS: edge_tts.communicate(narration, voice)
        TTS-->>PL: audio_bytes ✅
        PL->>FS: Save seg_004.mp3
        PL->>SEM: release TTS slot
    end

    Note over PL: asyncio.gather trả về results[0..11]\nĐÚNG THỨ TỰ dù chunk nào xong trước

    PL->>PL: results = [\n  AudioSegment(order=0, audio=...),  ← TEXT, xong sớm\n  AudioSegment(order=1, audio=...),\n  AudioSegment(order=2, audio=...),  ← IMAGE, xong muộn hơn\n  ...\n  AudioSegment(order=11, audio=...)\n]

    PL->>UI: progress(0.85, "12/12 chunks hoàn tất")
```

**Giải thích flow rẽ nhánh:**

```
chunks[0] TEXT  ──→ clean(instant) ──→ TTS ──→ audio ──┐
chunks[1] TEXT  ──→ clean(instant) ──→ TTS ──→ audio ──┤
chunks[2] IMAGE ──→ LLM(~4s) ──→ TTS ──→ audio ───────┤
chunks[3] TEXT  ──→ clean(instant) ──→ TTS ──→ audio ──┤
chunks[4] TABLE ──→ LLM(~4s) ──→ TTS ──→ audio ───────┤ → gather
chunks[5] TEXT  ──→ clean(instant) ──→ TTS ──→ audio ──┤   (order
chunks[6] TEXT  ──→ clean(instant) ──→ TTS ──→ audio ──┤   preserved)
chunks[7] TABLE ──→ LLM(~4s) ──→ TTS ──→ audio ───────┤
chunks[8] TEXT  ──→ clean(instant) ──→ TTS ──→ audio ──┤
chunks[9] TEXT  ──→ clean(instant) ──→ TTS ──→ audio ──┤
chunks[10] TEXT ──→ clean(instant) ──→ TTS ──→ audio ──┤
chunks[11] MIXED──→ LLM+clean ──→ TTS ──→ audio ──────┘
```

- TEXT chunks: skip LLM, chỉ clean text → TTS ngay (~3s total)
- IMAGE/TABLE chunks: LLM enrich (~4s) → TTS (~3s) = ~7s total
- Tất cả chạy song song, tổng thời gian ≈ thời gian chunk chậm nhất (~7-9s)
- Semaphore(5) đảm bảo không quá 5 API calls đồng thời → tránh rate limit

### 5.5. Audio Stitch & Delivery

```mermaid
sequenceDiagram
    actor User
    participant UI as Gradio UI
    participant PL as Pipeline
    participant ST as AudioStitcher\n(pydub + ffmpeg)
    participant FS as Local Filesystem
    participant DB as SQLite

    PL->>UI: progress(0.9, "Đang ghép audio...")

    PL->>ST: stitch(audio_segments[], config)
    ST->>ST: 1. Sort by chunk.order
    ST->>ST: 2. Load all via pydub
    ST->>ST: 3. Normalize → 44.1kHz mono
    ST->>ST: 4. Insert silence gaps\n   300ms giữa chunks cùng section\n   800ms giữa sections (heading change)
    ST->>ST: 5. Concatenate all
    ST->>ST: 6. Volume normalize → -16 LUFS
    ST->>ST: 7. Fade-in 500ms, fade-out 1000ms
    ST->>ST: 8. Export MP3 192kbps
    ST-->>PL: final_audio_path

    PL->>FS: Move → ./data/outputs/{job_id}/audio.mp3
    PL->>DB: UPDATE job SET status="completed",\naudio_path, duration=1845s

    PL->>UI: progress(1.0, "Hoàn tất!")
    UI-->>User: 🎉 Audio Player + Download button

    User->>UI: Play
    UI-->>User: 🔊 Phát audio

    User->>UI: Download
    UI-->>User: 📥 audio.mp3 (18MB)
```

### 5.6. Error Handling & Retry

```mermaid
sequenceDiagram
    participant PL as Pipeline
    participant Svc as External Service\n(Groq / Edge TTS)
    participant FB as Fallback Model\n(Llama 4 Scout)
    participant DB as SQLite

    PL->>Svc: API call

    alt Success
        Svc-->>PL: ✅ Response
    else Transient error (429 / 500 / timeout)
        Svc-->>PL: ❌

        loop attempt < 3
            PL->>PL: Wait: 2^attempt seconds + jitter
            PL->>Svc: Retry
            alt Success
                Svc-->>PL: ✅
            else Still failing
                PL->>PL: attempt++
            end
        end

        alt All retries exhausted (LLM only)
            PL->>FB: Try fallback model (Scout)
            alt Fallback success
                FB-->>PL: ✅ Response
            else Fallback also failed
                PL->>PL: chunk.status = "failed"\nInsert placeholder text
            end
        end
    end

    alt All chunks done, failed < 20%
        PL->>DB: job.status = "completed"
    else failed ≥ 20%
        PL->>DB: job.status = "failed"
    end
```

---

## 6. Tech Stack

### 6.1. Backend Core

| Component | Technology | Vai trò |
|-----------|-----------|---------|
| Language | Python 3.11+ | Runtime duy nhất |
| UI | Gradio 5 | Web UI: upload, progress, audio player |
| API (optional) | FastAPI + Uvicorn | REST endpoint cho CLI/script |
| Database | sqlite3 (built-in) | Job metadata + cache |
| Storage | Local filesystem | File uploads + audio outputs |
| Concurrency | asyncio + Semaphore | Concurrent chunk processing, rate limiting |

### 6.2. Document Processing

| Component | Technology | Vai trò |
|-----------|-----------|---------|
| DOCX Parser | python-docx 1.1 | Extract paragraphs, headings, tables, images |
| PDF Parser | PyMuPDF (fitz) 1.25 | Extract text blocks, images, tables |
| Image Processing | Pillow 11 | Resize images trước khi gửi LLM (max 1024px) |
| Audio Processing | pydub 0.25 + ffmpeg 6 | Stitch segments, normalize volume, export |

### 6.3. LLM Providers

| Provider | Model | Use Case | Cost | Vietnamese |
|----------|-------|----------|------|-----------|
| Groq | Llama 4 Maverick 17B | Image description + Table narration (primary) | Free tier: 30 RPM | ✅ |
| Groq | Llama 4 Scout 17B | Fallback cho cả image lẫn table | Free tier: 30 RPM | ✅ |

Chỉ cần 1 provider (Groq) với 2 models: primary (Maverick) + fallback (Scout). Cả hai đều nằm trong free tier — hoàn toàn miễn phí cho personal use.

### 6.4. TTS Engine

| Engine | Type | Quality | Cost | Vietnamese |
|--------|------|---------|------|-----------|
| Edge TTS | Cloud (free) | ⭐⭐⭐⭐ | $0 | ✅ 4 voices |

Default voice: `vi-VN-HoaiMyNeural` — giọng nữ, tự nhiên, rõ ràng.

> **Tại sao chỉ 1 TTS engine?** Edge TTS free, chất lượng tốt cho tiếng Việt, không rate limit khắt khe. Nếu cần so sánh chất lượng với OpenAI TTS hay ElevenLabs, thêm sau khi POC đã chạy ổn.

### 6.5. Dependency Matrix

| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| Python | 3.11+ | PSF | Runtime |
| gradio | 5.x | Apache-2.0 | Web UI |
| fastapi | 0.115.x | MIT | Optional REST API |
| uvicorn | 0.34.x | BSD | ASGI server |
| python-docx | 1.1.x | MIT | DOCX parsing |
| PyMuPDF | 1.25.x | AGPL-3.0 | PDF parsing |
| Pillow | 11.x | HPND | Image processing |
| httpx | 0.28.x | BSD | Async HTTP (LLM calls) |
| edge-tts | 6.1.x | GPL-3.0 | Microsoft TTS |
| pydub | 0.25.x | MIT | Audio processing |
| ffmpeg | 6.x | LGPL | Audio codec (system dep) |
| groq | latest | Apache-2.0 | Groq API client |

---

## 7. Quyết định kiến trúc (ADRs)

### ADR-001: Asyncio Concurrent Pipeline (thay vì Celery + Redis)

**Context**: POC cho 1 user, xử lý 1 file tại 1 thời điểm. Celery + Redis thêm 2 services, config phức tạp, debug khó. Tuy nhiên, xử lý chunk tuần tự quá chậm (bottleneck ở I/O: gọi LLM API, TTS API).

**Decision**: Dùng `asyncio` event loop cho in-process concurrency. Mỗi chunk được xử lý độc lập (enrich → TTS) qua `asyncio.gather` + `Semaphore` kiểm soát rate limit. Thứ tự đảm bảo nhờ `gather` trả results theo đúng thứ tự input.

**Consequences**: Tăng tốc ~3x so với sequential. Không cần distributed queue. Không xử lý concurrent jobs (chấp nhận cho POC 1 user). 1 process duy nhất, debug dễ dàng.

### ADR-002: Local Filesystem (thay vì MinIO)

**Context**: MinIO là S3-compatible storage, cần thêm 1 container, config access key, presigned URL.

**Decision**: Lưu file trực tiếp vào `./data/`. Gradio serve file qua built-in file server.

**Consequences**: Không có presigned URL, không S3-compatible API. Chấp nhận cho POC local. Migration sang MinIO/S3 khi cần deploy cloud.

### ADR-003: Gradio UI (thay vì React SPA)

**Context**: React SPA cần riêng: Node.js, build pipeline, Dockerfile, WebSocket client. Ước tính 2-3 tuần dev.

**Decision**: Gradio — 1 file Python, có sẵn file upload, progress bar, audio player, download button.

**Consequences**: UI không custom được sâu, nhưng đủ cho POC. Chuyển sang React khi cần UI phức tạp hơn.

### ADR-004: SQLite Cache (thay vì Redis)

**Context**: Redis cần thêm 1 service cho caching. POC chỉ cần cache kết quả LLM và TTS.

**Decision**: Dùng SQLite table `cache` với columns (hash, result_type, result_data, expires_at). Khi query, check `expires_at > now()`.

**Consequences**: Chậm hơn Redis (~1ms vs ~0.1ms) nhưng hoàn toàn đủ cho 1 user. Zero infrastructure thêm.

### ADR-005: Heading-Aware Chunking

**Context**: Fixed-size chunking gây đứt gãy nội dung, người nghe mất ngữ cảnh.

**Decision**: Parse heading structure, tách chunk tại H1/H2/H3 boundary. Max 2500 từ/chunk ≈ 3 phút audio.

**Consequences**: Chunk size không đều nhưng đảm bảo mỗi chunk là đơn vị ngữ nghĩa hoàn chỉnh.

### ADR-006: Simple Config (thay vì Provider Registry Pattern)

**Context**: Provider Registry + Strategy Pattern phù hợp khi có nhiều user cần customize model selection. POC 1 user chỉ cần pick 1 provider.

**Decision**: Config dict trong `config.py`. Fallback logic là simple if/else.

**Consequences**: Thêm provider = sửa code (chấp nhận cho POC). Refactor sang Registry khi có > 3 providers cần dynamic switching.

---

## 8. Yêu cầu phi chức năng

| Attribute | POC Target | Ghi chú |
|-----------|-----------|---------|
| **Performance** | < 5 min cho 50 trang | Async concurrent chunks (Semaphore=5) |
| **Throughput** | 1 job tại 1 thời điểm | Đủ cho 1 user |
| **Availability** | Best-effort | Chạy khi cần, tắt khi không dùng |
| **Storage** | 10 GB local | Xóa thủ công khi đầy |
| **Security** | Không auth (local only) | Chỉ bind localhost |
| **Monitoring** | Print logs to console | Structured logging (Python logging) |
| **Max File Size** | 200 MB | Giới hạn hợp lý cho máy cá nhân |
| **Audio Format** | MP3 192kbps | Cố định cho đơn giản |

---

## 9. API & UI Specification

### 9.1. Gradio UI (Primary Interface)

```
┌──────────────────────────────────────────┐
│  📄 Document-to-Speech                   │
├──────────────────────────────────────────┤
│                                          │
│  ┌─ Input ─────────────────────┐         │
│  │                             │         │
│  │  [Tab: 📁 Upload File]               │
│  │  [Tab: 🔗 Dán URL   ]               │
│  │                             │         │
│  │  ── Tab Upload ──────────── │         │
│  │  ┌───────────────────────┐  │         │
│  │  │  📁 Upload DOCX/PDF   │  │         │
│  │  │  (drag & drop / browse)│  │         │
│  │  └───────────────────────┘  │         │
│  │                             │         │
│  │  ── Tab URL ─────────────── │         │
│  │  ┌───────────────────────┐  │         │
│  │  │ 🔗 https://drive.goo… │  │         │
│  │  └───────────────────────┘  │         │
│  │  Hỗ trợ: Direct link,      │         │
│  │  Google Drive, Dropbox,     │         │
│  │  OneDrive                   │         │
│  │                             │         │
│  └─────────────────────────────┘         │
│                                          │
│  Voice: [vi-VN-HoaiMyNeural ▾]          │
│                                          │
│  [🚀 Bắt đầu xử lý]                    │
│                                          │
│  ████████████░░░░░ 65% - TTS 8/12...    │
│                                          │
│  ┌─────────────────────────────┐         │
│  │ 🔊 ▶ ━━━━━━━●━━━━━ 18:32   │         │
│  │    🔉 ━━━━━━●━ Speed: 1.0x  │         │
│  └─────────────────────────────┘         │
│                                          │
│  [📥 Download MP3]                       │
│                                          │
│  📊 Stats: 12 chunks · 30:45 · 18MB     │
│           Cost: $0.05 · Engine: edge-tts │
│                                          │
│  ┌─ History ───────────────────┐         │
│  │ ✅ report.pdf    30:45  18MB│         │
│  │ 🔗 thesis.docx   45:12  27MB│        │
│  │ ⏳ manual.pdf    processing │         │
│  └─────────────────────────────┘         │
└──────────────────────────────────────────┘
```

### 9.2. REST API (Optional — cho CLI/automation)

| Method | Path | Request | Response | Mô tả |
|--------|------|---------|----------|-------|
| `POST` | `/api/upload` | `multipart/form-data` | `{ job_id, status }` | Upload file + start processing |
| `POST` | `/api/upload-url` | `{ "url": "https://..." }` | `{ job_id, status }` | Download từ URL + start processing |
| `GET` | `/api/jobs/{id}` | — | `{ job_id, status, progress }` | Job status |
| `GET` | `/api/jobs/{id}/audio` | — | `audio/mpeg` | Download audio file |
| `GET` | `/api/health` | — | `{ status: "ok" }` | Health check |

### 9.3. Voice Options

| Voice ID | Giới tính | Mô tả |
|----------|-----------|-------|
| `vi-VN-HoaiMyNeural` | Nữ | Giọng mặc định, tự nhiên |
| `vi-VN-NamMinhNeural` | Nam | Giọng nam |

---

## 10. Data Models

### 10.1. Job State Machine

```mermaid
stateDiagram-v2
    [*] --> PROCESSING: Upload OK
    PROCESSING --> COMPLETED: All done
    PROCESSING --> PARTIAL_FAILURE: Some chunks failed (<20%)
    PROCESSING --> FAILED: Critical error or >20% failed

    PARTIAL_FAILURE --> COMPLETED: Audio vẫn được tạo

    COMPLETED --> [*]
    FAILED --> [*]
```

Đơn giản hóa từ 8 states xuống 4 states. Progress chi tiết thể hiện qua Gradio progress bar, không cần state machine phức tạp.

### 10.2. Database Schema (SQLite)

**jobs** table:

```sql
CREATE TABLE jobs (
    id              TEXT PRIMARY KEY,       -- UUID
    status          TEXT NOT NULL,           -- processing/completed/partial_failure/failed
    source_type     TEXT NOT NULL DEFAULT 'upload',  -- "upload" or "url"
    source_url      TEXT,                    -- URL gốc (NULL nếu upload trực tiếp)
    file_path       TEXT NOT NULL,           -- local path to uploaded/downloaded file
    file_type       TEXT NOT NULL,           -- "docx" or "pdf"
    file_size_bytes INTEGER,
    chunks_total    INTEGER DEFAULT 0,
    chunks_failed   INTEGER DEFAULT 0,
    audio_path      TEXT,                    -- local path to output audio
    audio_duration  REAL,                    -- seconds
    audio_size      INTEGER,                 -- bytes
    tts_voice       TEXT DEFAULT 'vi-VN-HoaiMyNeural',
    estimated_cost  REAL DEFAULT 0,          -- USD
    error_message   TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT
);
```

**cache** table:

```sql
CREATE TABLE cache (
    hash        TEXT PRIMARY KEY,            -- sha256 of input
    type        TEXT NOT NULL,               -- "llm" or "tts"
    result      TEXT,                        -- text result (LLM) or file path (TTS)
    created_at  TEXT DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL                -- datetime for TTL
);

-- Auto-cleanup expired entries
-- Run periodically: DELETE FROM cache WHERE expires_at < datetime('now');
```

### 10.3. Storage Layout (Local Filesystem)

```
./data/
├── uploads/{job_id}/
│   └── original.{docx|pdf}
├── processing/{job_id}/
│   ├── seg_001.mp3
│   ├── seg_002.mp3
│   └── ...
├── outputs/{job_id}/
│   └── audio.mp3
└── cache/
    └── tts/
        ├── {hash1}.mp3
        └── {hash2}.mp3
```

---

## 11. Caching Strategy

| Layer | Key | Value | TTL | Storage |
|-------|-----|-------|-----|---------|
| LLM Cache | `sha256(prompt + content)` | response text | 30 days | SQLite `cache` table |
| TTS Cache | `sha256(text + voice)` | file path (.mp3) | 7 days | SQLite `cache` table + local file |

Cache hit scenarios:

| Scenario | Hit Rate | Impact |
|----------|----------|--------|
| Same document re-uploaded | ~95% | Skip gần toàn bộ pipeline |
| Documents có shared headers/footers | ~15–20% | Tiết kiệm TTS |
| Document hoàn toàn mới | 0% | Không tiết kiệm |

---

## 12. Security Considerations

| Concern | POC Approach |
|---------|-------------|
| Authentication | Không cần — bind `127.0.0.1` only |
| File validation | Extension + magic bytes check |
| URL input | HTTPS only, follow max 5 redirects, HEAD check trước khi download |
| SSRF prevention | Chỉ cho phép HTTPS public URLs, block private IP ranges (127.x, 10.x, 192.168.x) |
| API keys | `.env` file (gitignored) |
| Transport | HTTP localhost |
| Data at rest | Không mã hóa (local machine) |
| Input sanitization | File type + size limit (200MB), URL format validation |

---

## 13. Budget ước tính

### 13.1. Development Cost

| Hạng mục | Thời gian | Ghi chú |
|----------|-----------|---------|
| Pipeline backend (6 stages) | 5–7 ngày | Core logic |
| Gradio UI | 1–2 ngày | Upload, progress, player |
| Integration + testing | 2–3 ngày | End-to-end testing |
| **TOTAL** | **8–12 ngày** | 1 developer |

### 13.2. Operating Cost (Personal Use)

| Hạng mục | Chi phí | Ghi chú |
|----------|---------|---------|
| Groq API (Maverick + Scout) | $0 | Free tier: 30 RPM |
| Edge TTS | $0 | Free, không rate limit |
| Infrastructure | $0 | Chạy local |
| **TOTAL/document** | **$0** | Hoàn toàn miễn phí |

### 13.3. Risk Registry

| Risk | Xác suất | Impact | Mitigation |
|------|----------|--------|------------|
| Edge TTS policy change | Low | High | Thêm Kokoro local fallback (roadmap) |
| Groq free tier limit | Low | Medium | Fallback model Scout cùng provider, hoặc chuyển sang provider khác |
| LLM hallucination on images/tables | Medium | Medium | Prompt engineering, review output |
| Complex PDFs (scanned) | Medium | Medium | Out of scope, OCR in roadmap |

---

## 14. Roadmap

```mermaid
gantt
    title D2S Pipeline — POC Roadmap
    dateFormat YYYY-MM-DD
    axisFormat %d/%m

    section Phase 1 — Core (1.5 tuần)
    Document Parser (DOCX + PDF)       :p1a, 2026-03-18, 3d
    Chunker + Classifier               :p1b, after p1a, 2d
    LLM Enricher (Groq + fallback)    :p1c, after p1b, 2d
    TTS Synthesizer (Edge TTS)         :p1d, after p1c, 1d
    Audio Stitcher                     :p1e, after p1d, 1d

    section Phase 2 — UI + Polish (0.5 tuần)
    Gradio UI                          :p2a, after p1e, 2d
    SQLite cache layer                 :p2b, after p1e, 1d
    End-to-end testing                 :p2c, after p2a, 2d

    section Phase 3 — Enhancement (khi POC ổn)
    Thêm TTS engines (Kokoro local)    :p3a, after p2c, 3d
    Optional REST API (FastAPI)        :p3b, after p2c, 2d
    Docker packaging (1 container)     :p3c, after p3b, 1d
```

---

## Phụ lục

### A. Quick Start

```bash
# 1. Clone & setup
git clone <repo> && cd doc-to-speech
pip install -r requirements.txt

# 2. Cài ffmpeg (nếu chưa có)
# Windows: choco install ffmpeg
# macOS:   brew install ffmpeg
# Linux:   sudo apt install ffmpeg

# 3. Tạo .env
cp .env.example .env
# Thêm GROQ_API_KEY (bắt buộc)

# 4. Chạy
python app.py
# → Mở browser: http://localhost:7860
```

### B. Project Structure

```
doc-to-speech/
├── app.py                      # Entry point — Gradio UI + optional FastAPI
├── config.py                   # All configuration (LLM, TTS, audio, paths)
├── requirements.txt
├── .env.example
│
├── pipeline/
│   ├── __init__.py
│   ├── orchestrator.py         # Run 6 stages sequentially
│   ├── parser.py               # DocumentParser (DOCX + PDF)
│   ├── chunker.py              # HeadingAwareChunker
│   ├── classifier.py           # ContentClassifier (rule-based)
│   ├── enricher.py             # LLMEnricher (Groq + fallback model)
│   ├── synthesizer.py          # TTSSynthesizer (Edge TTS)
│   └── stitcher.py             # AudioStitcher (pydub)
│
├── llm/
│   ├── __init__.py
│   └── groq_client.py          # Groq API client (Maverick + Scout fallback)
│
├── utils/
│   ├── __init__.py
│   ├── validator.py            # File validation (magic bytes + URL format)
│   ├── downloader.py           # URL download (async httpx, streaming, URL normalization)
│   ├── text_cleaner.py         # Unicode normalize, expand abbreviations
│   ├── cache.py                # SQLite cache helper
│   └── retry.py                # Exponential backoff helper
│
├── db/
│   ├── __init__.py
│   └── models.py               # SQLite schema + CRUD
│
├── data/                       # Runtime data (gitignored)
│   ├── uploads/
│   ├── processing/
│   ├── outputs/
│   └── cache/
│
└── tests/
    ├── test_parser.py
    ├── test_chunker.py
    └── test_pipeline.py
```

### C. Environment Variables

```bash
# LLM (bắt buộc)
GROQ_API_KEY=                   # Groq API — free tier

# TTS
TTS_VOICE=vi-VN-HoaiMyNeural   # Default Vietnamese voice

# Pipeline
CHUNK_MAX_WORDS=2500
AUDIO_FORMAT=mp3
AUDIO_BITRATE=192k
CONCURRENT_LLM=5               # Max concurrent LLM API calls
CONCURRENT_TTS=10              # Max concurrent TTS API calls

# URL Download
URL_CONNECT_TIMEOUT=10         # seconds
URL_DOWNLOAD_TIMEOUT=120       # seconds
URL_MAX_REDIRECTS=5

# App
HOST=127.0.0.1
PORT=7860
DATA_DIR=./data
```

### D. So sánh kiến trúc cũ vs mới

| Tiêu chí | Kiến trúc cũ (v0) | Kiến trúc mới (v1-POC) |
|----------|-------------------|------------------------|
| Services | 6 containers | 1 Python process |
| UI | React SPA + WebSocket | Gradio (1 file Python) |
| Task queue | Celery + Redis | asyncio.gather + Semaphore |
| Chunk processing | Sequential (1 chunk tại 1 thời điểm) | Concurrent (fan-out/fan-in, order preserved) |
| Storage | MinIO (S3) | Local filesystem |
| Cache | Redis (3 layers) | SQLite table |
| LLM routing | Provider Registry + 5 strategies | Config dict + if/else |
| TTS engines | 4 (Edge, Kokoro, OpenAI, ElevenLabs) | 1 (Edge TTS) |
| LLM providers | 6 (Gemini, Grok, Claude, GPT, DeepSeek, Ollama) | 1 (Groq — Maverick + Scout fallback) |
| Dev time | 4–6 tuần | 1.5–2 tuần |
| RAM usage | ~4 GB | ~500 MB |
| Dependencies | ~20 packages + Docker | ~12 packages |
| Lines of code | ~5000+ | ~1500–2000 |

---

> **Document version**: 1.1.0 — 18/03/2026
> **Approach**: Simplified POC — validate core pipeline trước, scale sau
> **Next review**: Sau khi Phase 1 hoàn thành
