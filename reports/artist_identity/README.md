# Artist identity and future compilation

The five authoritative source images are now preserved byte-for-byte under
`assets/artists/` and registered in `configs/artists.json`. Existing MP3 tags,
song configuration, manifest metadata, and source filenames contain no
authoritative song-to-artist mapping, so all eight song artist lists remain
explicitly empty. No mapping was inferred from image appearance.

`configs/songs.json` defines the fixed eight-track order and per-song artist
slots. `configs/artists.json` is the auditable artist/PFP registry. The
`artist_lockup` module validates both before exposing identity data and
explicitly reports missing metadata/assets.

`compilation.build_track_plan()` is the future one-file master planning layer:
canonical timing remains local to each song, while actual rendered durations
and an explicit transition duration produce cumulative master offsets. Chapter
rows can be generated from those same real offsets after final rendering.

No full compilation was rendered in this phase.
