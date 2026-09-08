# FOCUS distil-large-v3 bounded capacity experiment

`distil-whisper/distil-large-v3-ct2` was loaded through faster-whisper on CPU/int8 without lyric prompting. The first 14.82-second micro-window clearly recognized the target early chorus line. Three bounded groups were then evaluated with the existing weighted monotonic matcher.

Three early-section unresolved lead lines were recovered with strong direct ASR evidence. Intro `focus` matches were low-probability repeated-word artifacts, and the outro `Focus` match was below the acceptance gate. No full-song inference or subtitle replacement was performed.
