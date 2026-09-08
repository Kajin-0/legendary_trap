# Source transport

GitHub's web uploader limits individual files to 25 MB, while the original `Suno.zip` is about 31.4 MB. Therefore the archive is transported as two tracked parts:

- `source/Suno.zip.part-000` — 20 MiB
- `source/Suno.zip.part-001` — about 9.9 MiB

Upload both files to this directory through GitHub's web UI. The integrity values for both parts and the reconstructed archive are stored in `source/archive_manifest.json`.

On the VPS, after `git pull`, run:

```bash
python3 scripts/import_suno.py
```

The importer will automatically:

1. verify the size and SHA-256 of both uploaded parts;
2. concatenate them in order into `work/Suno.zip`;
3. verify the reconstructed archive's size and SHA-256;
4. verify ZIP lyrics against the committed authoritative lyrics;
5. extract the 8 canonical MP3 files into `input/audio/`;
6. ignore legacy ASS/image files.

`work/Suno.zip` and `input/audio/` are runtime artifacts and remain untracked.

Do not edit or regenerate the authoritative lyrics from ASR. The committed files under `input/lyrics/` remain ground truth.
