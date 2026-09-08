# Artist identity and future compilation

The bounded recovery audit found no authoritative artist names or PFPs in the
working tree, ignored project files, reachable Git history, branches, tags,
stashes, unreachable Git objects, or targeted adjacent project directories.
The catalog therefore intentionally contains empty artist lists and no image
files. No unrelated image was reused.

`configs/songs.json` defines the fixed eight-track order and per-song artist
slots. `configs/artists.json` is the auditable artist/PFP registry. The
`artist_lockup` module validates both before exposing identity data and
explicitly reports missing metadata/assets.

`compilation.build_track_plan()` is the future one-file master planning layer:
canonical timing remains local to each song, while actual rendered durations
and an explicit transition duration produce cumulative master offsets. Chapter
rows can be generated from those same real offsets after final rendering.

No full compilation was rendered in this phase.
