# Reference VPS environment

Audited 2026-09-08 on Ubuntu 25.10, x86_64, 8 exposed AMD EPYC 9354P cores,
31 GiB RAM, 229 GiB free disk, and no NVIDIA driver/GPU. Python is 3.13.7.
The VPS account cannot acquire the system apt lock, so FFmpeg 7.0.2 static is
kept locally under ignored `tools/`; no root package changes are required.

The isolated `.venv` contains the CPU stack selected for the pilot:

- faster-whisper 1.2.1 / CTranslate2 4.8.2 / ONNX Runtime 1.29.0
- base.en (int8 CPU), with tiny.en retained as a faster fallback
- librosa 1.0.0, NumPy 2.5.3, SciPy 1.18.1, SoundFile 0.14.0,
  RapidFuzz 3.14.6
- pytest 9.1.1 and Ruff 0.16.6

For the isolated Apple separation A/B only, Torch 2.7.1+cpu and Demucs 4.1.0
were installed from the PyTorch CPU index. WhisperX remains uninstalled. The
Demucs A/B was negative, so separation remains an optional experiment and is
not a hidden prerequisite of the normal pipeline.
