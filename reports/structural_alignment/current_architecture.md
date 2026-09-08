# Current architecture audit

The previous parser is deterministic and preserves `original_text`, `lead_text`,
ad-libs, normalized tokens, and the authoritative SHA-256. Section headings were
recognized only when both brackets were present, so `[Outro` was treated as a
lyric event. Parenthetical text was removed from the lead alignment view, but
parenthetical-only rows remained in the same global line sequence as lead rows.

The previous aligner flattened all authoritative tokens and all ASR words into
one chronology-constrained dynamic program. It retained authoritative wording,
but repeated chorus occurrences had no explicit repeat group or occurrence
window. A line with only middle/end word matches used those timestamps directly
as its display bounds; leading and trailing unmatched tokens were not diagnosed
or reconstructed. Missing lines were filled by local interpolation, and the
renderer had a historical FOCUS fallback for four residual IDs.

This pass adds compatible parser metadata: tolerant known-role headings,
structural role, raw/normalized label, section fingerprints, repeat groups and
occurrence indexes, plus event type and primary/secondary lane. It adds a
shadow structural evaluator that maps existing timing by source line, reports
section occurrences and line-edge coverage, and proposes bounded edge
reconstructions. It does not run ASR and does not overwrite production timing.
