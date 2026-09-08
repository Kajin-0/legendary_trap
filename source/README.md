# Source transport

The original song MP3 files are intentionally tracked in this directory because GitHub is the transport mechanism to the VPS.

Current source files:

- `AppLE.mp3`
- `Chokehold¿.mp3`
- `COMIN LONG WAYS.mp3`
- `FOCUS.mp3`
- `Off the Wave.mp3`
- `slidin.mp3`
- `we got chemistry.mp3`
- `you missed it.mp3`

After cloning or pulling the repository on the VPS, run:

```bash
python3 scripts/import_suno.py
```

The importer verifies that all expected source MP3s exist, verifies the SHA-256 fingerprints of the committed authoritative lyrics, and copies the audio into normalized runtime paths under `input/audio/`.

The source MP3s are the immutable transport copies. `input/audio/`, `work/`, model caches, stems, and generated subtitle/timing artifacts remain runtime data and are not duplicated in Git history.

Do not edit or regenerate the authoritative lyrics from ASR. The committed files under `input/lyrics/` remain ground truth.
