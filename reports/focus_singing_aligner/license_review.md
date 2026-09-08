# `schufo/lyrics-aligner` license review

Reviewed upstream commit `72be8a14b9126c201e0b8920513764c44ccd3f9`.

## Code

The repository contains an MIT `LICENSE` naming Kilian Schulze-Forster
(2021). The adapter does not copy upstream implementation code into
`src/legendary_trap`; the source checkout is retained only as an ignored
compatibility reference under `third_party/lyrics-aligner/`.

## Checkpoint

`model_parameters.pth` is a 40,357,640-byte Git blob (about 38.5 MiB) tracked
by the upstream repository. No separate checkpoint license, model card, or
non-commercial restriction is included in the checkout. The README describes
the model and cites the associated paper, but also includes a copyright notice
for the project. The model was trained using MUSDB18 plus its lyric extension;
those upstream data terms are not reproduced here.

Conclusion: there is no explicit non-commercial checkpoint restriction that
requires stopping this evaluation, so a bounded research/evaluation run is
permitted under the upstream repository's stated terms. Commercial production
redistribution of the checkpoint should still receive a separate provenance
review because the repository does not provide an explicit standalone model
license or a grant for the training data.
