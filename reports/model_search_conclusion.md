# FOCUS pretrained-model search conclusion

This bounded phase did not process another song. The final large-Whisper
capacity tests were restricted to FOCUS unresolved windows and used no lyric
prompting, Demucs, or alignment-algorithm changes.

| Family/configuration | Result | Decision |
| --- | --- | --- |
| Whisper `base.en`, CPU int8 | 75/82 lead lines; 521/602 direct tokens | Baseline |
| Whisper `small.en` bounded refinement | No lead-line recovery | Rejected as sufficient refinement |
| Prompted/hinted small model | Nominal gains with hallucination risk | Rejected |
| Demucs + Whisper | Worse coverage and chronology failure | Disabled |
| Wav2Vec2 CTC | 0 accepted recovered tokens | Rejected |
| `schufo/lyrics-aligner` | 0 recovered lead lines; 5/258 supported group phonemes | Rejected |
| `distil-whisper/distil-large-v3-ct2` | 3/7 target lines, +22 direct tokens; 78/82 lead lines | Useful optional capacity pass |
| `large-v3-turbo` short micro-window | Stronger recognition of the early target line | No further expansion |

The strongest bounded result is `distil-large-v3`: lead-line coverage rose to
78/82 (95.12%) and direct token coverage to 543/602 (90.20%). This is useful
evidence that model capacity matters, but it does not yet meet the 96% line
target and does not resolve the intro/outro failure modes. The turbo result
confirms the early target is acoustically recoverable, but a single micro-window
does not justify another broad model sweep.

Pretrained-model shopping is exhausted for this phase. The next architectural
branch should be one of: adaptation/fine-tuning on these songs, obtaining
isolated vocal stems, or formally accepting an explicitly provenance-marked
estimated-timing fallback for acoustically unresolved lines. None is started
by this commit.
