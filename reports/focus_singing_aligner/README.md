# FOCUS singing-specific alignment evaluation

The isolated `schufo/lyrics-aligner` checkpoint was loaded successfully by modern PyTorch 2.7 CPU after a local compatibility patch to the upstream STFT call. CMUdict plus g2p-en generated the ARPAbet alignment view; authoritative lyric text was not changed.

The model produced monotonic placements, but evidence was weak: only 5 of 258 group phonemes met the diagnostic support threshold, no target word met the direct evidence gate, and none of the seven unresolved lead lines was recovered. The candidate is therefore rejected and `reports/focus_final/` remains unchanged.

Ad-libs were excluded. No candidate timing/subtitle files were generated.
