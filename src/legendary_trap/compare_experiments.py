"""Compare two Apple experiment or baseline directories."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    if path.is_file(): return json.loads(path.read_text())
    for name in ("summary.json", "diagnostics.json"):
        if (path / name).exists():
            data=json.loads((path/name).read_text())
            if name == "diagnostics.json" and "diagnostics" in data: return data["diagnostics"]
            return data
    raise FileNotFoundError(path)


def compare(base: Path, candidate: Path) -> dict:
    a,b=load(base),load(candidate)
    def timing(path: Path) -> dict:
        p=path if path.is_file() and path.name == "timing.json" else (path.parent if path.is_file() else path) / "timing.json"
        return json.loads(p.read_text()) if p.exists() else {"sections":[]}
    at,bt=timing(base),timing(candidate)
    def metric(data: dict, key: str, aliases: tuple[str, ...] = ()) -> float:
        for name in (key, *aliases):
            if name in data: return data[name]
        nested=data.get("diagnostics", {})
        for name in (key, *aliases):
            if name in nested: return nested[name]
        return 0.0
    al={l["line_id"]:l for s in at.get("sections",[]) for l in s.get("lines",[])}
    bl={l["line_id"]:l for s in bt.get("sections",[]) for l in s.get("lines",[])}
    line_deltas=[{"line_id":k,"confidence_delta":bl[k]["confidence"]-al[k]["confidence"],
                  "start_delta":bl[k]["start"]-al[k]["start"],"end_delta":bl[k]["end"]-al[k]["end"]}
                 for k in sorted(al.keys() & bl.keys())]
    return {"base":str(base),"candidate":str(candidate),"deltas":{
                "token_coverage":metric(b,"token_coverage",("token_acoustic_coverage",))-metric(a,"token_coverage",("token_acoustic_coverage",)),
                "line_coverage":metric(b,"line_coverage",("line_acoustic_coverage",))-metric(a,"line_coverage",("line_acoustic_coverage",)),
                "unresolved_tokens":metric(b,"unresolved_tokens")-metric(a,"unresolved_tokens"),
                "runtime_seconds":metric(b,"runtime_seconds")-metric(a,"runtime_seconds")},
            "base_low_confidence":a.get("low_confidence_line_ids",a.get("validation",{}).get("low_confidence_line_ids",[])),
            "candidate_low_confidence":b.get("low_confidence_line_ids",b.get("validation",{}).get("low_confidence_line_ids",[])),
            "base_validation_failures":a.get("validation_failures",a.get("validation",{}).get("failures",[])),
            "candidate_validation_failures":b.get("validation_failures",b.get("validation",{}).get("failures",[])),
            "line_deltas":line_deltas}


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("base",type=Path); p.add_argument("candidate",type=Path); args=p.parse_args()
    print(json.dumps(compare(args.base,args.candidate),indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
