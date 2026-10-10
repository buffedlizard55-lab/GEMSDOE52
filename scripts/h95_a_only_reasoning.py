#!/usr/bin/env python3
"""Refine the A-only reasoning column of the H95 export, deterministically, from the measured columns.

`scripts/run_h95.py gates` writes one row per shipped A-only dot (A rank >= 0.95, B rank in [0.35, 0.65])
with the measured band values and a generic sentence.  The brief asks for geological reasoning for every
A-only candidate, so this script replaces the generic sentence with a reading that depends on the row's own
cover thickness, slope and potential-field gradients, plus a named mimic and an explicit falsifier.  The
thresholds are the ones the gates stage already used (the words thick/thin, strong/moderate, low/high in the
original sentence are parsed back, so no new threshold is introduced).  Idempotent.
"""
import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = json.loads((ROOT / "evidence/h95_gates.json").read_text())
P = ROOT / G["a_only_reasoning_csv"]

rows = list(csv.DictReader(io.StringIO(P.read_text())))
src_col = "measured_summary"
for r in rows:
    base = r.get(src_col) or r["reasoning"].split("; ", 1)[1].split(". Reading")[0]
    r[src_col] = base
    thick = "thick cover" in base
    low_slope = "low slope" in base
    g = "strong gravity gradient" in base
    m = "strong magnetic gradient" in base
    cov, sl, d = float(r["cover_thickness_m_band15"]), float(r["slope_band19"]), float(r["dist_to_catalogue_m"])
    pf = ("coincident gravity and magnetic edges" if g and m else "a gravity edge without a magnetic one" if g
          else "a magnetic edge without a gravity one" if m else "weak potential-field edges")
    if thick:
        reading = (f"Buried normal fault beneath basin fill: {pf} under ~{cov:.0f} m of modelled basin fill (depth to basement, band 15, above the footprint median), where a "
                   f"surface scarp would be buried or eroded, so View B abstaining is expected.")
        mimic = "buried lithological contact or palaeochannel margin within the fill"
        falsifier = "a smooth (non-linear) gravity step, or seismic/well data showing continuous basement"
    elif low_slope:
        reading = (f"Pediment / shallow-bedrock fault where depth to basement is below the footprint median (~{cov:.0f} m): {pf} on low relief "
                   f"(slope {sl:.1f}) where young sediment can mask a small scarp.")
        mimic = "dike or intrusive contact (magnetic) or a buried bedrock bench"
        falsifier = "lidar/field check shows no lineament and the anomaly is equant rather than linear"
    else:
        reading = (f"Range-front or intra-range bedrock structure: {pf} with below-median depth to basement (~{cov:.0f} m) on steep "
                   f"ground (slope {sl:.1f}); the surface view abstains because lithology along strike masks the scarp.")
        mimic = "depositional or intrusive lithologic contact in bedrock (no displacement)"
        falsifier = "geologic map shows a mapped contact along this trend with no offset"
    r["reasoning"] = (f"{reading} Distance to nearest catalogued fault {d:,.0f} m. Named mimic: {mimic}. "
                      f"Falsifier: {falsifier}.")
    r["named_mimic"], r["falsifier"] = mimic, falsifier

fields = [c for c in rows[0].keys() if c not in ("reasoning", src_col, "named_mimic", "falsifier")] + \
         [src_col, "reasoning", "named_mimic", "falsifier"]
out = io.StringIO()
w = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
w.writeheader()
w.writerows(rows)
P.write_text(out.getvalue())
print(f"{len(rows)} A-only rows refined -> {P.relative_to(ROOT)}")
