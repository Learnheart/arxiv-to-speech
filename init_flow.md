# Sequence Diagrams — Chi tiết luồng Data (Simplified POC)

> 5 diagrams cho 5 phases của pipeline.
> Kiến trúc đơn giản: 1 Python process, Gradio UI, SQLite, local filesystem.
> **Key design**: Enrich + TTS chạy **async concurrent** (asyncio.gather), không sequential.

---

## 1 / 5 — Upload & Validate

Luồng từ khi user upload file đến khi pipeline bắt đầu chạy.

```mermaid
sequenceDiagram
    actor User
    participant UI as Gradio UI<br/>(:7860)
    participant Val as File Validator
    participant FS as Local Filesystem<br/>(./data/)
    participant DB as SQLite
    participant PL as Pipeline<br/>(background thread)

    User->>UI: Chọn file (drag & drop)
    User->>UI: Chọn voice (dropdown)
    User->>UI: Nhấn "Bắt đầu xử lý"

    UI->>Val: validate(file_bytes, filename)
    Val->>Val: Check magic bytes<br/>(PK → DOCX, %PDF → PDF)
    Val->>Val: Check file size < 200MB

    alt File không hợp lệ
        Val-->>UI: ❌ Invalid (format hoặc size)
        UI-->>User: ⚠️ "File không hợp lệ.\nChỉ hỗ trợ DOCX và PDF dưới 200MB."
    else File hợp lệ
        Val-->>UI: ✅ { type: "pdf", size: 2.4MB }

        UI->>FS: Save → ./data/uploads/{job_id}/original.pdf
        FS-->>UI: OK

        UI->>DB: INSERT INTO jobs\n{ id, file_path, file_type, status: "processing" }
        DB-->>UI: OK

        UI-->>User: ✅ "Đang xử lý... Vui lòng chờ."
        UI->>UI: progress(0.05, "Khởi tạo pipeline...")

        UI->>PL: Start background thread\n→ run_pipeline(job_id, file_path, config)

        Note over PL: Pipeline chạy async.\nGradio progress bar cập nhật\nrealtime qua callback.
    end
```

---

## 2 / 5 — Parse, Chunk & Classify

Pipeline đọc file, parse cấu trúc, tách chunks theo heading, classify content type.

```mermaid
sequenceDiagram
    participant PL as Pipeline
    participant FS as Local Filesystem
    participant P as DocumentParser<br/>(PyMuPDF / python-docx)
    participant C as HeadingAware<br/>Chunker
    participant CL as Content<br/>Classifier
    participant UI as Gradio progress

    PL->>UI: progress(0.1, "Đang parse document...")

    PL->>FS: Read ./data/uploads/{job_id}/original.pdf
    FS-->>PL: file_bytes (2.4MB)

    PL->>P: parse(file_bytes, "pdf")

    alt DOCX file
        P->>P: python-docx:\n• Iterate paragraphs\n• Detect heading styles (Heading 1/2/3)\n• Extract tables (rows × cells)\n• Extract embedded images (relationships)
    else PDF file
        P->>P: PyMuPDF:\n• get_text("dict") → text blocks\n• Font-size heuristic for headings\n  (size > 14pt → H1, > 12pt → H2)\n• find_tables() → table data\n• extract_image(xref) → image bytes
    end

    P-->>PL: elements[] = [\n  { type: HEADING, level: 1,\n    content: "Chương 1: Tổng quan", order: 0 },\n  { type: PARAGRAPH,\n    content: "Nội dung đoạn văn...", order: 1 },\n  { type: TABLE,\n    table_data: [["Quý","DT"],["Q1","100"]], order: 5 },\n  { type: IMAGE,\n    image_bytes: <binary>, order: 8 },\n  ... (sorted by order)\n]

    PL->>UI: progress(0.2, "Đang tách chunks...")

    PL->>C: chunk(elements, max_words=2500)

    C->>C: Step 1: Xác định section boundaries\n• Mỗi H1/H2/H3 bắt đầu section mới\n• Elements giữa 2 headings = 1 section

    C->>C: Step 2: Greedy packing\n• section ≤ 2500 words → 1 chunk\n• section > 2500 words → sub-chunk\n  tại paragraph boundary\n• Merge sections nhỏ nếu cùng parent heading

    C->>C: Step 3: Gán metadata\n• chunk_id, order, word_count\n• section_id (để biết heading change\n  khi stitch audio)

    C-->>PL: chunks[] = [\n  { chunk_id: "c01", order: 0,\n    word_count: 2100, elements: [...],\n    section_id: "s1" },\n  { chunk_id: "c02", order: 1,\n    word_count: 1800, elements: [...],\n    section_id: "s1" },\n  ... total: 12 chunks\n]

    PL->>UI: progress(0.25, "Đang phân loại chunks...")

    PL->>CL: classify(chunks)

    loop Mỗi chunk
        CL->>CL: Scan element types trong chunk

        alt Chỉ PARAGRAPH + HEADING
            CL->>CL: chunk_type = TEXT
        else Có TABLE element (không kèm IMAGE)
            CL->>CL: chunk_type = TABLE
        else Có IMAGE element (không kèm TABLE)
            CL->>CL: chunk_type = IMAGE
        else Có cả TABLE lẫn IMAGE, hoặc kèm text đáng kể
            CL->>CL: chunk_type = MIXED
        end
    end

    CL-->>PL: chunks[] with types assigned\n[TEXT×8, TABLE×2, IMAGE×1, MIXED×1]

    Note over PL: TEXT chunks → trực tiếp qua TTS.\nNon-text chunks → cần LLM enrichment.
```

---

## 3 / 5 — Enrich + TTS (Async Concurrent)

Sau khi classify, tất cả chunks được **fan-out xử lý song song**. Mỗi chunk chạy pipeline riêng: Enrich → TTS. `asyncio.gather` đảm bảo kết quả trả về **đúng thứ tự** dù chunk nào xong trước.

### 3a. Tổng quan flow concurrent

```mermaid
sequenceDiagram
    participant PL as Pipeline<br/>(asyncio event loop)
    participant UI as Gradio progress

    PL->>UI: progress(0.3, "Xử lý 12 chunks song song...")

    PL->>PL: results = await asyncio.gather(\n  process_chunk(chunk[0]),   # TEXT\n  process_chunk(chunk[1]),   # TEXT\n  process_chunk(chunk[2]),   # IMAGE → LLM → TTS\n  process_chunk(chunk[3]),   # TEXT\n  process_chunk(chunk[4]),   # TABLE → LLM → TTS\n  ...\n  process_chunk(chunk[11]),  # MIXED\n)

    Note over PL: 12 coroutines chạy concurrent.\nSemaphore(5) giới hạn API calls đồng thời.\nMỗi process_chunk() = enrich + TTS cho 1 chunk.

    PL->>PL: results[0..11] — ordered AudioSegments\n(thứ tự luôn đúng dù thời gian xử lý khác nhau)

    PL->>UI: progress(0.85, "12/12 chunks hoàn tất")
```

**Timeline minh họa (12 chunks, 5 concurrent slots):**

```
t=0s   t=3s   t=6s   t=9s
│      │      │      │
├─ chunk[0]  TEXT:  clean→TTS ──→ ✅ done (3s)
├─ chunk[1]  TEXT:  clean→TTS ──→ ✅ done (3s)
├─ chunk[2]  IMAGE: LLM────→TTS ──→ ✅ done (7s)
├─ chunk[3]  TEXT:  clean→TTS ──→ ✅ done (3s)
├─ chunk[4]  TABLE: LLM────→TTS ──→ ✅ done (7s)
│  ── sem=5, slot freed ──
├─ chunk[5]  TEXT:  clean→TTS ──→ ✅ done (3s)
├─ chunk[6]  TEXT:  clean→TTS ──→ ✅ done (3s)
├─ chunk[7]  TABLE: LLM────→TTS ────→ ✅ done (7s)
├─ chunk[8]  TEXT:  clean→TTS ──→ ✅
├─ chunk[9]  TEXT:  clean→TTS ──→ ✅
├─ chunk[10] TEXT:  clean→TTS ──→ ✅
├─ chunk[11] MIXED: LLM+clean→TTS ──→ ✅
│                              │
Total: ~9s (thay vì ~52s sequential)
```

### 3b. Chi tiết process_chunk() — rẽ nhánh theo type

```mermaid
sequenceDiagram
    participant PC as process_chunk()\n(1 coroutine per chunk)
    participant SEM as Semaphore(5)
    participant Cache as SQLite Cache
    participant Gemini as Gemini Flash
    participant Claude as Claude Haiku<br/>(fallback)
    participant TTS as Edge TTS
    participant FS as Local FS

    Note over PC: ═══ PHASE 1: ENRICH ═══\n(rẽ nhánh theo chunk_type)

    alt chunk_type = TEXT
        PC->>PC: enriched = clean_for_tts(text)\n• Normalize unicode (NFKC)\n• Expand abbreviations\n• Remove page numbers\n(instant, không cần semaphore)

    else chunk_type = IMAGE
        PC->>SEM: acquire LLM slot
        SEM-->>PC: OK (hoặc wait nếu đã 5 concurrent)

        PC->>Cache: SELECT llm cache WHERE hash=sha256(image+prompt)
        alt Cache HIT ✅
            Cache-->>PC: cached description
        else Cache MISS
            PC->>PC: Resize image (max 1024px, < 4MB)
            PC->>Gemini: describe_image(bytes,\nprompt: "Mô tả hình ảnh cho audiobook...")

            alt Gemini ✅
                Gemini-->>PC: "Biểu đồ doanh thu Q3..."
            else Gemini ❌ → retry 3x → fallback
                PC->>Claude: describe_image(bytes, prompt)
                alt Claude ✅
                    Claude-->>PC: description
                else All fail
                    PC->>PC: "[Hình ảnh không thể mô tả]"
                end
            end
            PC->>Cache: INSERT llm cache (TTL 30d)
        end
        PC->>SEM: release LLM slot

    else chunk_type = TABLE
        PC->>SEM: acquire LLM slot
        PC->>PC: table_md = table_to_markdown(data)
        PC->>Cache: SELECT llm cache WHERE hash=sha256(table+prompt)
        alt Cache MISS
            PC->>Gemini: narrate_table(table_md,\nprompt: "Diễn giải bảng dữ liệu...")
            alt Gemini ✅
                Gemini-->>PC: "Bảng cho thấy doanh thu..."
            else Fail → fallback
                PC->>Claude: narrate_table(table_md, prompt)
                alt Claude ✅
                    Claude-->>PC: narration
                else All fail
                    PC->>PC: Raw readout: "Bảng gồm N hàng..."
                end
            end
            PC->>Cache: INSERT llm cache
        end
        PC->>SEM: release LLM slot

    else chunk_type = MIXED
        PC->>SEM: acquire LLM slot
        PC->>PC: Split sub-elements by type\nProcess text/table/image separately\nMerge in original order
        PC->>SEM: release LLM slot
    end

    PC->>PC: Compose enriched_text =\nheading + paragraphs + [image desc] + [table narr]

    Note over PC: ═══ PHASE 2: TTS ═══

    PC->>SEM: acquire TTS slot
    PC->>Cache: SELECT tts cache WHERE hash=sha256(text+voice)

    alt Cache HIT ✅
        Cache-->>PC: cached audio_path
        PC->>FS: Read cached audio
        Note over PC: Cost = $0

    else Cache MISS
        alt text ≤ 5000 chars
            PC->>TTS: edge_tts.Communicate(text,\nvoice="vi-VN-HoaiMyNeural")
            TTS-->>PC: audio_bytes (MP3)
        else text > 5000 chars
            PC->>PC: Split at sentence boundaries
            loop Each sub-segment
                PC->>TTS: Communicate(segment, voice)
                TTS-->>PC: audio_bytes
            end
            PC->>PC: Concat sub-segments (pydub)
        end

        PC->>FS: Save cache → ./data/cache/tts/{hash}.mp3
        PC->>Cache: INSERT tts cache (TTL 7d)
    end

    PC->>FS: Save → ./data/processing/{job_id}/seg_{order}.mp3
    PC->>SEM: release TTS slot

    PC-->>PC: return AudioSegment(\n  order=chunk.order,\n  audio=audio_bytes,\n  section_id=chunk.section_id\n)
```

### 3c. Cơ chế bảo toàn thứ tự

```python
# asyncio.gather BẢO TOÀN THỨ TỰ input → output
results = await asyncio.gather(
    process_chunk(chunks[0]),   # → results[0], dù xong lúc t=3s
    process_chunk(chunks[1]),   # → results[1], dù xong lúc t=3s
    process_chunk(chunks[2]),   # → results[2], dù xong lúc t=7s (IMAGE, chậm hơn)
    process_chunk(chunks[3]),   # → results[3], dù xong lúc t=3s
    ...
)
# results[i] luôn = output của chunks[i]
# Không cần sort lại — thứ tự tự đảm bảo

# AudioStitcher nhận results[] đã đúng order
stitcher.stitch(results)  # seg_0 + gap + seg_1 + gap + seg_2 + ...
```

**Tại sao TEXT chunks không bị block bởi IMAGE/TABLE chunks?**

- `asyncio.gather` fire **tất cả** coroutines cùng lúc
- TEXT chunk: `clean_for_tts()` (instant) → TTS (~3s) → done (~3s total)
- IMAGE chunk: wait semaphore → LLM (~4s) → TTS (~3s) → done (~7s total)
- Chúng chạy **đồng thời**, TEXT chunk không chờ IMAGE chunk
- `gather` chỉ chờ **tất cả** xong rồi trả kết quả theo thứ tự

---

## 5 / 5 — Audio Stitch & Delivery

Gom segments, stitch thành file hoàn chỉnh, hiển thị audio player cho user.

```mermaid
sequenceDiagram
    actor User
    participant UI as Gradio UI
    participant PL as Pipeline
    participant ST as AudioStitcher<br/>(pydub + ffmpeg)
    participant FS as Local Filesystem
    participant DB as SQLite

    PL->>UI: progress(0.9, "Đang ghép audio cuối cùng...")

    PL->>ST: stitch(audio_segments[], audio_config)

    Note over ST: === Audio Processing Pipeline ===

    ST->>ST: 1. Sort segments by chunk.order\n   [seg_00, seg_01, ..., seg_11]

    ST->>ST: 2. Load tất cả segments via pydub\n   • Auto-detect format (MP3/WAV)\n   • Failed chunks → 1s AudioSegment.silent()

    ST->>ST: 3. Normalize sample rate\n   → Tất cả convert sang 44.1kHz mono\n   (pydub: set_frame_rate + set_channels)

    ST->>ST: 4. Insert silence gaps\n   • So sánh section_id giữa chunk[n] và chunk[n+1]\n   • Cùng section: chèn 300ms silence\n   • Khác section (heading change): chèn 800ms silence

    ST->>ST: 5. Concatenate tất cả theo order\n   result = seg[0] + gap + seg[1] + gap + ...

    ST->>ST: 6. Volume normalization\n   → Target -16 LUFS (broadcast standard)\n   • Tính current loudness\n   • Apply gain adjustment

    ST->>ST: 7. Apply effects\n   • Fade-in: 500ms ở đầu file\n   • Fade-out: 1000ms ở cuối file

    ST->>ST: 8. Export MP3 192kbps\n   result.export(path, format="mp3",\n   bitrate="192k")

    ST-->>PL: final_audio_path\n(size: ~18MB, duration: 30m45s)

    PL->>FS: Move → ./data/outputs/{job_id}/audio.mp3
    FS-->>PL: OK

    PL->>DB: UPDATE jobs SET\nstatus = "completed",\naudio_path = "./data/outputs/{job_id}/audio.mp3",\naudio_duration = 1845.5,\naudio_size = 18874368,\nchunks_failed = 1,\nestimated_cost = 0.05,\ncompleted_at = datetime('now')

    alt chunks_failed > 0 AND < 20%
        PL->>DB: status = "partial_failure"
        Note over PL: Audio vẫn được tạo,\nnhưng có 1 số đoạn bị thiếu
    else chunks_failed ≥ 20%
        PL->>DB: status = "failed"
    end

    PL->>UI: progress(1.0, "Hoàn tất! 🎉")

    UI-->>User: Hiển thị:\n• Audio player (play/pause/seek)\n• Duration: 30:45\n• File size: 18MB\n• Download button\n• Stats: 12 chunks, 1 failed, cost $0.05

    User->>UI: Nhấn Play ▶
    UI->>FS: Read audio.mp3
    FS-->>UI: audio stream
    UI-->>User: 🔊 Phát audio

    User->>UI: Nhấn Download 📥
    UI-->>User: 📥 Tải file audio.mp3 (18MB)

    Note over User,DB: Job hoàn tất.\nLLM cache: 30 ngày.\nTTS cache: 7 ngày.\nAudio output: giữ vĩnh viễn\n(user tự xóa khi cần).
```

---

## Bảng tổng hợp data transformation qua từng phase

| Phase | Input | Output | Processing | Xử lý bởi |
|-------|-------|--------|-----------|-----------|
| **1. Upload** | Raw file (DOCX/PDF) | Validated file trên disk | Sequential | File Validator |
| **2. Parse** | File binary | `elements[]` | Sequential | DocumentParser |
| **3. Chunk** | `elements[]` | `chunks[]` (max 2500 words, ordered) | Sequential | HeadingAwareChunker |
| **4. Classify** | `chunks[]` | `chunks[]` + `chunk_type` | Sequential | ContentClassifier |
| **5+6. Enrich → TTS** | Classified chunks | `audio_segments[]` (ordered) | **Concurrent** (asyncio.gather) | process_chunk() per chunk |
| **7. Stitch** | Audio segments | Final `audio.mp3` — 192kbps, -16 LUFS | Sequential | AudioStitcher + pydub |
| **8. Deliver** | Final audio path | Gradio audio player + download | Sequential | Gradio UI |

---

## Error handling summary

```mermaid
flowchart TD
    A[API Call] --> B{Success?}
    B -->|Yes| C[Use result]
    B -->|No| D{Attempt < 3?}
    D -->|Yes| E[Wait 2^attempt seconds]
    E --> A
    D -->|No| F{Has fallback?}
    F -->|Yes| G[Try Claude Haiku]
    G --> H{Success?}
    H -->|Yes| C
    H -->|No| I[Use placeholder]
    F -->|No| I

    I --> J{Failed chunks < 20%?}
    J -->|Yes| K[Job: completed / partial_failure]
    J -->|No| L[Job: failed]

    style C fill:#E1F5EE,stroke:#5DCAA5
    style I fill:#FFF3CD,stroke:#EF9F27
    style L fill:#FAECE7,stroke:#F0997B
```

| Error type | Handling |
|-----------|----------|
| Gemini timeout/429 | Retry 3x exponential backoff → Claude fallback |
| Claude fail | Placeholder text cho LLM chunks |
| Edge TTS fail | Retry 3x → silence placeholder |
| Parse error | Job failed |
| File corrupt | Reject at validation |

---

> **Rendering**: Tất cả diagrams dùng Mermaid.js, tương thích GitHub, GitLab, VS Code (Markdown Preview Mermaid), và hầu hết Markdown viewers.
