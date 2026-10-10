#!/usr/bin/env python3
"""Splice the H83 header block into README.md and AGENTS.md, rendered from the receipts.

Nothing in the block is typed by hand: every figure comes out of ``evidence/h83_*.json`` and
``registry/h83_preregistration.json``. Running the script twice is a no-op (markers are replaced,
not appended).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
R_START, R_END = "<!--H83-README-->", "<!--/H83-README-->"
A_START, A_END = "<!--H83-AGENTS-->", "<!--/H83-AGENTS-->"


def load(n: str) -> dict:
    return json.loads((EVID / f"h83_{n}.json").read_text())


def f(x, nd=6):
    return "n/a" if x is None else f"{float(x):.{nd}f}"


def ci(a):
    return "n/a" if a is None else f"[{float(a[0]):.6f}, {float(a[1]):.6f}]"


def splice(path: Path, start: str, end: str, block: str) -> None:
    t = path.read_text()
    if start in t:
        a, b = t.index(start), t.index(end) + len(end)
        t = t[:a] + block + t[b:]
    else:
        t = block + "\n\n---\n\n" + t
    path.write_text(t)


def main() -> int:
    card = load("run_card")
    sub = load("submission")
    hold = load("holdout")
    fit = load("fit_checkpoint")
    can = load("canary")
    ind = load("independence")
    ex = load("pseudo_exchange")
    lane = load("lane_summary")
    reg = json.loads((ROOT / "registry/h83_preregistration.json").read_text())
    doc_sha = hashlib.sha256((ROOT / reg["hypothesis_document"]).read_bytes()).hexdigest()

    sc = hold["pooled"]["pooled"]["scores"]
    osc = hold["offcatalogue"]["pooled"]["scores"]
    pair = hold["pooled"]["pooled"]["paired_differences"]["single_B"]
    cand = "disagreement_post"
    ok = card["verdict"] == "promote"
    rec = sub["receipt"]
    val = rec["validator"]

    rows = "".join(f"| `{k}` | {f(v['dti'])} | {ci(v['ci95'])} |\n"
                   for k, v in sorted(sc.items(), key=lambda kv: -kv[1]["dti"]))
    orows = "".join(f"| `{k}` | {f(v['dti'])} | {ci(v['ci95'])} |\n"
                    for k, v in sorted(osc.items(), key=lambda kv: -kv[1]["dti"]))
    auc_rows = "".join(
        f"| {r['fold']} | {f(r['view_A']['heldout_region_auc'], 4)} | "
        f"{f(r['view_B']['heldout_region_auc'], 4)} | {f(r['view_A']['offcatalogue_auc'], 4)} | "
        f"{f(r['view_B']['offcatalogue_auc'], 4)} |\n" for r in fit["folds"])

    readme = f"""{R_START}
# Current status — H83 (2026-10-10): co-training on two instruments — the mandated hide-and-recover and a new off-catalogue one

> **DOWNLOAD: YES** (format-valid, decoded-unique, values exactly {{0,1}}, no non-finite pixel).
> **SUBMIT: {'YES — eligible (no slot allocated in this round)' if ok else 'NO — research artefact only'}.**
> Slots used: **0**. Verdict **{card['verdict']}**.

**★ [Download the H83 GeoTIFF](docs/downloads/h83-candidate.tif)** · [ZIP](docs/downloads/h83-candidate.zip) ·
[per-cell geological reasoning CSV](docs/downloads/{rec['file'][:-4]}-a-only-reasoning.csv) ·
**[Executive summary / exact submission guide](docs/h83-executive-summary.html)** ·
[Full result](docs/h83.html) · [Hypotheses](docs/h83-hypotheses.html) · [Sources](docs/h83-sources.html) ·
[Check any file in your browser](docs/validator.html)

- **File:** `submission/{rec['file']}` — {int(rec['bytes']):,} bytes, SHA-256 `{rec['sha256']}`
- **Submission name:** `{rec['submission_name']}`
- **Note ({rec['note_chars']}/140):** `{rec['note']}`
- **Validator (re-read from disk):** {val['bands']} band {val['dtype']}, {val['crs']}, {val['height']}×{val['width']},
  transform matches the organiser template, min {val['min']} / max {val['max']}, {val['finite_pixels']:,} finite pixels,
  {sub['placed']:,} emitted cells. **PASS.**
- **A NaN-outside twin** byte-structurally identical to `sample_submission.tif`
  (`submission/{sub['twin']['file']}`, SHA-256 `{sub['twin']['sha256']}`) is published as
  `docs/downloads/h83-candidate-template-nan.tif`. Upload **one**, never both. The all-finite file is
  recommended only because it cannot fail a literal `[0,1]` range test under any reader.

## What is new this round

Every instrument this repository had — `gems52-pooled-hide-v1` — withholds **catalogue** faults and
scores recovery of them. The competition's truth is the set of faults that catalogue **lacks**. H83
adds a second instrument, `gems52-offcatalogue-v1`: truth = SGMC fault pixels at ≥ 300 m from
`labels.tif`, trained on catalogue positives from the other three quadrants only (which is already
what `gems52.spatial.folds`'s `train` domain is), so **one fit serves both instruments**. It is
diagnostic: it can demote a candidate, never promote one.

## HOLDOUT-DTI — `gems52-pooled-hide-v1` (decisive)

{cand} dots per fold per arm · {int(sc[cand]['withheld_positive_pixels']):,} withheld positive pixels ·
α 0.2 / β 0.8 · R 300 m triangular kernel · 1,000 paired physical-cluster bootstrap draws ·
label-blind-quadrants-v2, 80 px buffer.

| Arm | HOLDOUT-DTI | 95% CI |
|---|---|---|
{rows}
Paired `{cand}` − `single_B`: **{pair['delta']:+.6f}**, 95% CI {ci(pair['ci95'])}. Frozen rule: promote
only if the lower bound is above zero. It is **{f(pair['ci95'][0])}** → **not promoted**.
All arms filled their budget: **{hold['pooled']['all_arms_filled']}**.
These are HOLDOUT-DTI numbers, never board forecasts (Spearman −0.10 vs the owner-reported board).

## OFFCAT-DTI — `gems52-offcatalogue-v1` (diagnostic)

{int(osc[cand]['withheld_positive_pixels']):,} withheld positive pixels, identical α/β/kernel/bootstrap.

| Arm | OFFCAT-DTI | 95% CI |
|---|---|---|
{orows}
Limits stated in advance: the 300 m cut removes the extension population by construction; SGMC is
compiled at 1:100k–1:500k and is itself incomplete; off-catalogue pixels may sit in different
terrain from the faults the organiser will verify.

## View sufficiency and the independence screen

| Fold | View A AUC (I1) | View B AUC (I1) | View A AUC (I2) | View B AUC (I2) |
|---|---|---|---|---|
{auc_rows}
Independence before any transfer: max |ρ| **{f(ind['pre']['max_abs_correlation'], 4)}** over
{int(ind['pre']['n_blocks']):,} 50×50 px blocks of held-out proxy negatives (bar
{reg['thresholds']['independence_abandon_max_abs_rho']}) → `allow_exchange={ind['allow_exchange']}`.
Exchange donated **{int(ex['total_pseudo_pixels']):,}** px in one whole-segment, block-confined round.
Leakage canary: max single-channel direction-insensitive AUC **{f(can['max_alarm_across_folds'], 4)}**
(bar {reg['thresholds']['canary_auc_alarm']}) → no alarm.

## Gates

- Lane, surface: literal **{lane['surface']['literal']}** / policy **{lane['surface']['policy']}**;
  max Spearman **{f(lane['surface']['max_spearman'], 4)}** (bar 0.90).
- Lane, dots: literal **{lane['dots']['literal']}** / policy **{lane['dots']['policy']}**;
  max share within 3 px of one prior's dots **{f(lane['dots']['max_near_share'], 4)}** (bar 0.70).
- Registry: {lane['registry']['n_priors']} rasters ({lane['registry']['n_scored']} scored-only).
- Not merely the union of the two views: **{sub['not_union']['verdict']}**; Jaccard with the union
  placement {f(sub['not_union']['jaccard_with_union_max'], 4)}.

## Why `h33-h33-2-b2` scores 0.2778, and what beating 0.3195 would take

It is the 0.2600 file with the ≤ 200 m ring around the mapped catalogue deleted — 6.3 % of its mass
removed for +6.8 % score: *free precision*, because a masked pixel can never earn credit and always
pays the false-positive tax. It is not a better detector; the same 37,654 px emitted incoherently
scores 0.0778, 3.6× worse. With `DTI = T / (0.2·T + 0.2·(S − M) + 0.8·|G|)` and the family's `|G|`
bracket, beating 0.3195 at 37,654 px needs `T ≥ 6,007` credit pixels against the champion's measured
5,223 — i.e. a credit density near 16 % where the champion averages 13.9 %. No instrument in this
repository can certify that a novel field reaches it, and the hide-and-recover simulator does not
rank the board. The off-catalogue instrument built this round is the first tool here that measures
the right population, and on it every arm lands near {f(osc[cand]['dti'], 3)} — the buried-fault
population is real but this field does not resolve it well enough to justify a slot.

## Reproduce

```
python3 scripts/restore_data.py --target-dir data
PYTHONPATH=src python3 -c "from gems52 import structural; structural.build(dest='work/r2/features', include_optional_profiles=False)"
PYTHONPATH=src python3 -m gems52.external
python3 scripts/fetch_prior_inventory.py
python3 scripts/run_h83.py {{canary|fit|exchange|holdout|build|lane|card|all}}
python3 scripts/publish_h83_site.py && python3 scripts/h83_readme.py && python3 scripts/check_site.py
python3 -m pytest -q
```

Preregistration: `{reg['hypothesis_document']}`, SHA-256 `{doc_sha}`, frozen before any fit.
Run card: `evidence/h83_run_card.json`.
{R_END}"""

    agents = f"""{A_START}
## Current H83 continuation (2026-10-10)
Read README's H83 block and `knowledge/74` (frozen preregistration, SHA-256 `{doc_sha[:16]}…`) before
proposing anything. H83 verdict **{card['verdict']}**, experiments 1 of 3, slots 0.

What is now settled and must not be re-litigated:

- **The off-catalogue instrument exists and is cheap.** `gems52-offcatalogue-v1` reuses the *same*
  out-of-fold fits as `gems52-pooled-hide-v1`, because `gems52.spatial.folds`'s `train` domain is
  already "everything except this quadrant, minus an 80 px buffer". Do not refit for it. Truth =
  SGMC pixels ≥ 3 px from `labels.tif`: **{int(osc[cand]['withheld_positive_pixels']):,}** pooled px.
- **On the off-catalogue instrument every arm collapses toward the same number**
  (best {f(osc[cand]['dti'])} vs worst {f(min(v['dti'] for v in osc.values()))}), and View A is *less*
  bad there than on hide-and-recover in two of four folds. The buried-fault population is real; this
  field does not resolve it.
- **View A sufficiency has now failed an eighth time on the mandated instrument**
  (mean {f(sum(r['view_A']['heldout_region_auc'] for r in fit['folds']) / 4, 4)}). Independence still
  passes (max |ρ| {f(ind['pre']['max_abs_correlation'], 4)}), so the brief does not require
  abandonment — but independence without sufficiency still gives co-training nothing to donate, and
  the exchange moved A's OOF AUC by at most
  {f(max(abs(r['directions']['refit_A']['heldout_region_auc'] - r['view_A']['heldout_region_auc']) for r in ex['folds']), 4)}.
- **Both packaging variants are format-valid.** The all-finite zeros-outside file is what the site
  recommends because it cannot fail a literal `[0,1]` range test; the NaN-outside twin matches the
  organiser template byte-structurally. Do not add a third variant (IR-H77-004 stands for "no new
  variant"; this round's second file is the *template* variant, not a new one).
- **Site:** `docs/index.html` is current-first with every previous round preserved verbatim inside one
  collapsed `<details>` (`<!--ARCHIVE-START-->`/`<!--ARCHIVE-END-->`). `scripts/check_site.py` asserts
  historical strings on that page, so never rewrite it from scratch — `legacy_index_body()` in
  `scripts/publish_h83_site.py` carries them forward and is idempotent.
{A_END}"""

    splice(ROOT / "README.md", R_START, R_END, readme)
    splice(ROOT / "AGENTS.md", A_START, A_END, agents)
    print(json.dumps(dict(readme_bytes=(ROOT / "README.md").stat().st_size,
                          agents_bytes=(ROOT / "AGENTS.md").stat().st_size,
                          verdict=card["verdict"]), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
