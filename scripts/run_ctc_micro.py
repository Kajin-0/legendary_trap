#!/usr/bin/env python3
"""Bounded FOCUS CTC micro-benchmark for one unresolved lead line."""
from pathlib import Path

from legendary_trap.ctc_alignment import main

ROOT = Path(__file__).resolve().parents[1]
raise SystemExit(main())
