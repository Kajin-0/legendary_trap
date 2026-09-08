# FOCUS teacher-forced Whisper attention evaluation

This is a calibration-first evaluation of OpenAI Whisper's internal
teacher-forced cross-attention alignment. It is not ordinary transcription and
does not use lyric prompting. The official `turbo` checkpoint was tested on
bounded FOCUS clips only.

Calibration failed: 20 known lines produced 297 ms mean onset error, 800 ms P90
error, and very low absolute teacher-forced probabilities. The four unresolved
FOCUS targets were therefore left untouched. No candidate timing or subtitle
files were generated.
