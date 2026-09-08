# Teacher-forced Whisper attention alignment rejection

The official OpenAI Whisper `turbo` checkpoint loaded successfully on CPU and
the upstream `whisper.timing.find_alignment()` implementation ran on bounded
FOCUS clips. The model input was right-padded to Whisper's required 30-second
mel shape while the DTW frame count remained local to each clip.

Calibration on 20 known direct-ASR lines failed the predeclared gate:

- median onset error: 0 ms (boundary snapping, not sufficient by itself)
- mean onset error: 297 ms
- P90 onset error: 800 ms
- maximum error: 1,220 ms
- within 100/150/250 ms: 11/20, 11/20, 11/20
- median teacher-forced word probability: 0.0034
- wrong-word control accuracy: 100% over 8 controls, but probabilities were
  not calibrated and timing error remained unacceptable

Because the calibration timing gate failed, the four unresolved target lines
were not evaluated or promoted. Direct FOCUS coverage remains 78/82 lead lines
and 543/602 tokens. The non-training alignment search is exhausted for this
phase; no fine-tuning or other model search was started.
