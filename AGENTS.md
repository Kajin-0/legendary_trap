# Agent instructions

Work from the repository root and keep project artifacts inside this repository whenever practical.

## Non-negotiable data rule

`input/lyrics/*.txt` is authoritative ground truth. Never replace lyric wording with Whisper/ASR output. ASR is an acoustic locator only.

## Current phase

The project is in bootstrap / alignment-architecture phase. Do not jump directly to styled ASS generation.

The intended sequence is:

1. validate environment and source inventory;
2. parse authoritative lyrics into sections/lead/ad-lib structure without changing text;
3. establish a canonical timing JSON schema;
4. obtain coarse acoustic timing from vocals/audio;
5. sequence-align rough ASR tokens to the authoritative lyric token sequence;
6. perform constrained fine alignment inside coarse windows;
7. validate coverage/order/confidence quantitatively;
8. render ASS/SRT/VTT from canonical timing JSON.

## Single-repository layout

- `source/`: original tracked MP3 files used to transport audio through GitHub to the VPS. Treat these files as immutable source material.
- `input/audio/`: normalized runtime copies, ignored by Git.
- `input/lyrics/`: committed authoritative lyrics.
- `work/`: generated stems, ASR data, alignment scratch data; ignored by Git.
- `output/`: generated deliverables; ignored by Git until a deliberate policy is chosen.
- `src/legendary_trap/`: reusable Python code.
- `scripts/`: thin command-line utilities.

Avoid writing project-specific files into `/tmp`, home-directory scratch folders, or unrelated repositories unless a dependency requires it. Shared ML model caches may live outside the repo to avoid multi-gigabyte duplication.

## Bootstrap

After `git pull`, run:

```bash
python3 scripts/import_suno.py
bash scripts/check_environment.sh
```

The importer must copy from the tracked source MP3s and verify authoritative lyric fingerprints. Do not invent a ZIP/archive dependency unless the repository structure is deliberately changed later.

## Runtime policy

Do not install a large CUDA/PyTorch/Whisper stack until `scripts/check_environment.sh` has been run and the machine capabilities are known.

Prefer deterministic CLI commands and scripts over opaque manual steps. Put explicit timeouts around long-running tests or model experiments whenever the tool supports them. Start with one song and a short diagnostic pass before launching all-song processing.

## Quality gates

A result is not acceptable merely because an ASS/SRT file was produced.

Required invariants:

- authoritative text preserved;
- zero silently missing lyric lines;
- zero silently duplicated lyric lines;
- timestamps monotonic;
- section ordering preserved;
- repeated choruses mapped to the correct occurrence;
- uncertainty explicitly surfaced;
- diagnostics retained in machine-readable form.

Target after fine alignment: median line-start error roughly below 100-150 ms where the vocal onset is acoustically resolvable. Do not fabricate precision when vocals overlap, are heavily effected, or are not independently localizable.

## Legacy ASS files

Existing ASS files from the original source set are unreliable. They may be inspected only as diagnostics. Never use them as training labels, ground truth, or authoritative timing.
