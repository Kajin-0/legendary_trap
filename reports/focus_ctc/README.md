# FOCUS transcript-constrained CTC evaluation

This report is a bounded evaluation of a custom monotonic CTC trellis using
`facebook/wav2vec2-base-960h` on the original mix. The authoritative lead
lyrics were used as the forced transcript; no ASR text was promoted into the
output. Three local groups covered the seven unresolved lead lines.

The trellis produced 27 forced word positions, but posterior support was not
credible enough to classify any as direct acoustic recovery. Only three raw
words reached the diagnostic 0.5 posterior threshold, and none formed a
supported line. Therefore the CTC candidate is rejected and the existing
`reports/focus_final/` reference is unchanged.

The ten ad-lib-only lines were intentionally excluded. Interpolated or
line-estimated timing would not count as direct acoustic coverage.

SOFA was reviewed as a singing-specific follow-up, but not installed or run:
its source stack is Python-3.8-era and the available English GTSinger
checkpoint is approximately 1.22 GB. This was not a justified bounded
production experiment after the generic CTC result.
