# FOCUS RoFormer license review

Status: **blocked before weight download or inference**.

The maintained `openmirlab/melband-roformer-infer` repository was inspected at
commit `77ff05e6ce533d85439d1e7a52d8316a2987c1b9`. Its inference code is MIT
licensed, but its registry separately marks the recommended
`melband-roformer-kim-vocals` checkpoint as `CC-BY-NC-SA-4.0`. The registry
identifies the weight as `MelBandRoformer.ckpt`, 913,106,900 bytes, hosted by
`KimberleyJSN/melbandroformer`.

The checkpoint license is therefore not equivalent to the package license and
is not acceptable as a production dependency for this project. The upstream
README/model card did not provide a broader commercial grant that would
override the explicit registry restriction.

Other registry candidates were not treated as safe substitutes: the current
metadata labels most community checkpoints `not-reviewed`; one inspected
repository (`anvuew/dereverb_mel_band_roformer`) declares GPL-3.0 and is not a
vocal model. No clearly permissive, current RoFormer vocal checkpoint was
identified without downloading weights or accepting an unreviewed license.

Consequently no separator package was installed, no checkpoint was downloaded,
and no FOCUS audio was separated. This is a license-gated technical stop, not
an alignment result. A future evaluation needs a checkpoint with an explicit
commercially compatible license or a project-specific legal decision.
