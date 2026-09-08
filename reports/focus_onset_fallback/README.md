# FOCUS bounded acoustic-event fallback

This experiment tested a deterministic, nonlexical onset fallback using local
spectral onset strength, energy rise, vocal-band energy, pYIN voicing, and a
small temporal prior. The weights were fixed before evaluating the four
unresolved lead lines.

The calibration set contained 20 known direct-ASR lead-line starts. Its median
error was 1.215 seconds and P90 error was 2.23 seconds, so it failed the
120/250 ms acceptance gate. Consequently none of the four target candidates
was promoted to `bounded_acoustic_event`; no estimated timestamps or subtitle
artifacts were generated. Direct token coverage remains 543/602 and the four
lead lines remain unresolved.
