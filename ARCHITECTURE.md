# Pipeline architecture

`input/lyrics/*.txt` is immutable ground truth. `lyrics.py` parses it into
sections and lines while retaining `original_text`; normalization and token
lists are alignment-only views. `asr.py` runs CPU `faster-whisper` and writes
disposable evidence to `work/<song>/asr.json`. `alignment.py` uses weighted
monotonic dynamic programming, so repeated text remains in chronological source
order and cannot jump backward to an earlier chorus. Missing acoustic matches
are retained as low-confidence bounded interpolation, never dropped.

The pilot's fine stage is constrained local word timing: matched authoritative
tokens inherit word timestamps only after the global monotonic pass, and line
windows are built from those matches. The implementation deliberately exposes
confidence and unresolved counts rather than claiming precision. A future CTC,
phoneme, or Demucs stage can be added behind the same evidence boundary.

Run one bounded song:

```bash
PATH="$PWD/tools:$PATH" timeout 15m .venv/bin/python scripts/run_pipeline.py apple
```

Do not run all songs until the Apple report's low-confidence lines have been
reviewed acoustically. The current reference VPS has no NVIDIA GPU; the chosen
CPU stack is `faster-whisper` tiny.en, int8, CPU word timestamps. Demucs and
WhisperX are intentionally not installed because their Torch stacks are not
resource-appropriate for this 8-core CPU pilot.
