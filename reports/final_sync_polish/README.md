# Final sync polish

This pass makes only bounded, song-specific repairs to existing render timing.
It does not run ASR or introduce a new alignment method. Existing acoustic
events outside the named regions are preserved; repaired events are explicitly
marked as estimated or repeated-section cadence timing.

Frozen songs: `chokehold`, `off_the_wave`.

Touched songs and regions:

- `commin_long_ways`: intro and outro edge events
- `focus`: intro and outro residual events
- `we_got_chemistry`: opening and repeated outro hook
- `slidin`: late display pacing
- `you_missed_it`: bracketed intro
- `apple`: second chorus and bridge/verse transition

All six rerendered videos passed the existing authoritative-text and timing
validator. The v3 MP4 package is a temporary distribution artifact and is not
tracked in Git.
