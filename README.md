# legendary_trap

Local-first lyric-to-audio alignment pipeline for generated songs.

## Core rule

The lyric `.txt` files are authoritative. ASR output is **never** allowed to replace, rewrite, or "correct" lyric text. Speech recognition is used only to estimate acoustic position; final text always comes from the authoritative lyric files.

Existing `.ass` files from the original source set are intentionally excluded because their transcription/timing quality is inconsistent. They are not ground truth.

## Project layout

```text
legendary_trap/
├── source/             # original tracked MP3 transport copies
├── input/
│   ├── audio/          # normalized runtime copies; gitignored
│   └── lyrics/         # authoritative lyrics; committed
├── src/legendary_trap/
├── scripts/
├── work/               # stems, ASR, alignment intermediates; gitignored
├── output/             # generated timing/subtitle artifacts; gitignored initially
├── song_manifest.json  # canonical song IDs and filename mappings
├── pyproject.toml
└── .gitignore
```

## Intended pipeline

```text
authoritative lyrics.txt
        │
        ├───────────────┐
        │               │
        ▼               ▼
 lyric parser        song audio
                        │
                        ▼
                 vocal separation
                        │
                        ▼
                   rough ASR
                        │
                        ▼
             coarse sequence alignment
                        │
                        ▼
             constrained fine alignment
                        │
                        ▼
              canonical timing JSON
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
             ASS       SRT       VTT
```

The canonical product is timing JSON, not ASS. Subtitle formats are render targets generated from the same timing data.

## VPS bootstrap

Clone the repo into one working directory:

```bash
git clone https://github.com/Kajin-0/legendary_trap.git
cd legendary_trap
```

The original MP3s are already tracked under `source/`. Import them into normalized runtime paths:

```bash
python3 scripts/import_suno.py
```

The importer verifies the authoritative lyric fingerprints and copies the 8 source MP3s into canonical filenames under `input/audio/`.

Then inspect the machine before installing heavy ML dependencies:

```bash
bash scripts/check_environment.sh
```

This keeps model/runtime selection separate from repository bootstrap. The correct Whisper/WhisperX/Demucs stack depends on whether the VPS has CUDA, available RAM/VRAM, and a suitable PyTorch runtime.

## Song IDs

- `apple`
- `chokehold`
- `commin_long_ways`
- `focus`
- `off_the_wave`
- `slidin`
- `we_got_chemistry`
- `you_missed_it`

See `song_manifest.json` for exact source filename mappings.

## Design requirements

1. Preserve authoritative lyric text byte-for-byte unless an explicit normalization view is generated separately.
2. Never silently drop lyric lines.
3. Never silently duplicate lyric lines.
4. Preserve chronological ordering.
5. Treat parenthetical ad-libs/backing vocals as separately alignable content where possible.
6. Prevent repeated chorus sections from cross-aligning to the wrong occurrence by constraining fine alignment to coarse section windows.
7. Emit confidence/diagnostic metadata rather than hiding uncertain alignments.
8. Keep tracked source MP3s immutable; keep stems, model caches, runtime audio copies, and generated work products out of normal Git history.

## Target quality gates

- authoritative lyric preservation: **100%**
- missing lyric lines: **0**
- duplicated lyric lines: **0**
- timestamp monotonicity violations: **0**
- section-order violations: **0**
- low-confidence alignments: explicitly flagged
- target median line-start error after refinement: roughly **<100–150 ms** where acoustically resolvable

The repository is intentionally single-directory and agent-friendly so Chipotlai/OpenCode can inspect source audio, lyrics, manifests, diagnostics, and code without jumping across unrelated locations.
