# Artist identity and future compilation

The five authoritative source images are preserved byte-for-byte under
`assets/artists/` and registered in `configs/artists.json`. The explicit user
mapping now populates all eight song artist lists in `configs/songs.json`.
Display casing is preserved exactly, including `VonKai` and
`TheSideQuest24`; the image filenames remain independent asset identifiers.

`configs/songs.json` defines the fixed eight-track order and per-song artist
slots. `configs/artists.json` is the auditable artist/PFP registry. The
`artist_lockup` module validates both before exposing identity data and
explicitly reports missing metadata/assets.

`compilation.build_track_plan()` is the future one-file master planning layer:
canonical timing remains local to each song, while actual rendered durations
and an explicit transition duration produce cumulative master offsets. Chapter
rows can be generated from those same real offsets after final rendering.

No full compilation was rendered in this phase.
