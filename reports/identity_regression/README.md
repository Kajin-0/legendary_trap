# Identity regression audit

The FOCUS 20–38 second audit compares canonical timing with the baseline and repaired identity ASS lyric rows. The four positive-duration lyric events are byte-for-byte equivalent in timing and text. The apparent opening silence is canonical: the first positive-duration event starts at absolute 29.98 seconds, or 9.98 seconds into the preview. A zero-duration boundary event at the same timestamp is not a renderable subtitle.

Artist identity is now rendered as an independent final-resolution RGBA overlay. It is not emitted into the lyric ASS and is composited before the lyric ASS, so it cannot alter, hide, retime, or drop lyric rows.
