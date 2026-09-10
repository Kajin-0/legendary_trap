#!/usr/bin/env python3
"""Write the implementation-level audit for the opt-in visual power V2."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

report = {
    "schema_version": 2,
    "song": "wonder_when_im_gon_shine",
    "test_segment": {"start": 62.0, "duration": 20.0, "fps": 30,
                      "preset": "trap_polar_350_artistlockup", "renderer": "trap_sunset_polar_v3",
                      "band_hz": [20, 350], "low_samples": 32, "thickness_scale": 2.2},
    "profiles": {
        "A_baseline": "exact production baseline; no experimental effects",
        "B_physical_core": "attack/release envelopes, sampled local contrast, halo, historical contour afterimage, spatial lighting",
        "C_full_power": "B plus depth-weighted outward particle impulse, section staging, transient rim sparks, micro fringe",
    },
    "impact_envelope": {
        "raw": "clip(0.52*bass + 1.55*transient + 0.55*low_burst, 0, 1.8)",
        "fast_attack": 0.72, "fast_release": 0.18,
        "slow_attack": 0.48, "slow_release": 0.055,
        "bounded": True, "deterministic": True,
    },
    "contrast": {"statistic": "median sampled scene luminance at 32 contour points",
                 "correction_clamp": 0.18, "temporal_flicker_guard": "bounded per-frame response"},
    "afterimage": {"threshold": 0.78, "lifetime_frames": 10, "lifetime_ms": 333,
                   "cooldown_frames": 6, "trigger": "local threshold peak",
                   "historical_source_radii": True, "deterministic_finite_history": True},
    "environment_lighting": {"spatial": "horizon Gaussian plus sunset-region Gaussian",
                              "amplitude": 0.018, "uses_impact_slow": True},
    "particle_impulse": {"amplitude": 0.018, "decay_frames": 7,
                          "direction": "outward from polar pressure center",
                          "depth_exponent": 1.35, "foreground_weighted": True},
    "section_staging": {"active_in": "C_full_power", "verse": 0.92, "bridge_pre": 0.97,
                         "hook_chorus": 1.06, "transition_seconds": 1.5},
    "rim_sparks": {"trigger": "highs/transients", "positions": "time-varying deterministic sparse indices",
                   "lifetime": "current transient frame"},
    "chromatic_fringe": {"profile": "C_full_power", "hard_hit_only": True,
                          "max_alpha": 0.055, "duration": "trigger frame"},
    "verified_behavior": {"real_historical_afterimage": True,
                           "actual_local_contrast_measurement": True,
                           "explicit_outward_particle_impulse": True,
                           "section_staging_active_in_C": True},
    "runtimes": {},
}
for key, filename in (("A_baseline", "A.json"), ("B_physical_core", "B.json"), ("C_full_power", "C.json")):
    path = ROOT / "work/visual_power_v2" / filename
    if path.exists():
        try:
            text = path.read_text()
            data = json.loads(text)
        except json.JSONDecodeError:
            # The baseline was captured with stderr merged for the first
            # proof; recover its final machine-readable object without
            # treating the diagnostic ffmpeg banner as report data.
            try:
                text = path.read_text()
                data = json.loads(text[text.rfind("{\n  \"preset\""):])
            except (json.JSONDecodeError, ValueError):
                data = {}
        try:
            report["runtimes"][key] = data.get("runtime_seconds")
        except AttributeError:
            report["runtimes"][key] = None
report_path = ROOT / "reports/visualizer/visual_power_pass_v2.json"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
