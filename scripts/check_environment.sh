#!/usr/bin/env bash
set -u

printf '%s\n' '=== legendary_trap environment ==='
printf 'date: '; date -Is 2>/dev/null || date
printf 'pwd:  '; pwd
printf 'os:   '; uname -a
printf '\n'

check_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    printf '%-12s %s\n' "$cmd" "$(command -v "$cmd")"
  else
    printf '%-12s %s\n' "$cmd" 'MISSING'
  fi
}

for cmd in python3 pip3 ffmpeg ffprobe git nvidia-smi; do
  check_cmd "$cmd"
done

printf '\n=== versions ===\n'
python3 --version 2>&1 || true
pip3 --version 2>&1 || true
ffmpeg -version 2>/dev/null | head -n 1 || true
git --version 2>&1 || true

printf '\n=== CPU / memory ===\n'
if command -v lscpu >/dev/null 2>&1; then
  lscpu | grep -E '^(Architecture|CPU\(s\)|Model name|Thread|Core|Socket)' || true
fi
if command -v free >/dev/null 2>&1; then
  free -h
fi

printf '\n=== storage ===\n'
df -h .

printf '\n=== NVIDIA ===\n'
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi
else
  echo 'No nvidia-smi detected.'
fi

printf '\n=== Python ML visibility ===\n'
python3 - <<'PY'
import importlib.util
mods = ["torch", "whisperx", "faster_whisper", "demucs"]
for mod in mods:
    print(f"{mod:16s}", "installed" if importlib.util.find_spec(mod) else "not installed")

try:
    import torch
    print("torch_version     ", torch.__version__)
    print("cuda_available    ", torch.cuda.is_available())
    print("cuda_device_count ", torch.cuda.device_count())
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            p = torch.cuda.get_device_properties(i)
            print(f"cuda_device_{i:02d}  {p.name} | VRAM={p.total_memory / 1024**3:.2f} GiB")
except Exception as exc:
    print("torch_probe_error ", repr(exc))
PY

printf '\n=== project inventory ===\n'
printf 'lyrics: '
find input/lyrics -maxdepth 1 -type f -name '*.txt' 2>/dev/null | wc -l
printf 'audio:  '
find input/audio -maxdepth 1 -type f 2>/dev/null | wc -l

printf '\nEnvironment probe complete.\n'
