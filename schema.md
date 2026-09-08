# Canonical timing JSON

Schema version `1.0` is the product of the pipeline. `original_text`, `lead_text`,
and `adlibs` come only from the authoritative lyric file. ASR words are evidence
and are never copied into displayed lyric text.

The document contains `audio`, `alignment`, ordered `sections`, and `diagnostics`.
Each line has stable `line_id`, source line number, exact original text, floating
point `start`/`end` seconds, confidence in `[0,1]`, and optional acoustic words.
Low-confidence values identify interpolation or weak evidence; decimal formatting
does not imply equivalent acoustic accuracy. Repeated sections remain separate by
their source order and section IDs.
