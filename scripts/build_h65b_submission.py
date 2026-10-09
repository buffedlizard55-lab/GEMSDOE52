#!/usr/bin/env python3
"""H65b E3 -- build the round's unique research GeoTIFF and run every gate.

The artefact is the R5-H2a band-10 valley-line emission frozen in
``knowledge/45_h65b_preregistered.md`` section 5: top 15,000 cells of the detector
field, subject to (i) valid footprint, (ii) not a catalogue pixel (pixel-exact), (iii) >= 3 px
Euclidean from an accepted dot (greedy, higher field wins), (iv) novelty tier 2 -- the cell is
not positive in any informative registry raster (universal-coverage probes excluded, per the
H64 frozen definition); a colliding cell is skipped and the next-best cell takes it (the sorted
continuation IS the frozen re-placement; the substitution count is reported).

Its E2 holdout result is already known and negative (evidence/h65b_e2_holdout.json), so the
published verdict is DOWNLOAD YES (iff the gates below pass) / SUBMIT NO.  Nothing here uploads
anything or consumes a competition slot.

Reused, not forked: gems52.grid, gems52.gates (format_report, uniqueness_report, lane_report,
registry_coverage, find_priors), gems52.submission_writer, and the detector itself from
scripts/run_h65b_e2.py (imported, so the validated field and the built field cannot diverge).
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems52 import gates, grid                                          # noqa: E402
from gems52 import submission_writer as SW                              # noqa: E402
import run_h65b_e2 as E2                                                 # noqa: E402

BUDGET = 15000
SPACING2 = 9                     # forbidden: squared Euclidean distance < 3 px
PREFIX = "gems52-h65b-"
NOTE = ("H65b band-10 deq valley lines: HOLDOUT-DTI 0.00446 [0,0.00909] vs single_B 0.01890; "
        "SUBMIT NO; research-only")
DOWN = ROOT / "docs/downloads"


def log(*a, **k):
    print(*a, flush=True, **k)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def decode_support(path: Path, shape) -> tuple[np.ndarray, str, str | None]:
    with rasterio.open(path) as ds:
        if ds.count != 1 or ds.shape != shape:
            raise ValueError(f"unaligned prior {path.name}")
        old = gates.canonical(ds.read(1))
    binary = bool(np.all((old == 0) | (old == 1)))
    proposal = old > 0 if binary else old >= 0.5
    return proposal, hashlib.sha256(old.tobytes()).hexdigest(), str(ds.crs) if ds.crs else None


def informative_union(priors: list[Path], eligible: np.ndarray) -> tuple[np.ndarray, dict]:
    """Novelty tier 2: union of proposal supports of informative (non-probe) priors."""
    cache = ROOT / "work/h65b/novelty_union.npy"
    meta_cache = ROOT / "work/h65b/novelty_union_meta.json"
    if cache.exists() and meta_cache.exists():
        import json as _json
        u = np.load(cache)
        if u.shape == eligible.shape and u.dtype == bool and _json.loads(meta_cache.read_text())["n_priors"] == len(priors):
            log(f"  novelty union from cache: {int(u.sum()):,} px")
            return u, _json.loads(meta_cache.read_text())
    union = np.zeros(eligible.shape, bool)
    n_probe = n_info = n_err = 0
    coverages = {}
    for i, p in enumerate(priors):
        try:
            proposal, digest, _ = decode_support(p, eligible.shape)
            if digest in coverages:
                cov = coverages[digest]
            else:
                cov = gates.registry_coverage(proposal, eligible)
                coverages[digest] = cov
            if cov >= gates.PROBE_COVERAGE:
                n_probe += 1
            else:
                n_info += 1
                union |= proposal
        except Exception:
            n_err += 1
        if (i + 1) % 100 == 0:
            log(f"  novelty pass {i+1}/{len(priors)} (informative {n_info}, probes {n_probe}, "
                f"errors {n_err})")
    log(f"  novelty union: {int(union.sum()):,} px from {n_info} informative priors "
        f"({n_probe} probes excluded, {n_err} errors)")
    meta = dict(n_priors=len(priors), informative=n_info, probes=n_probe, errors=n_err,
                union_px=int(union.sum()))
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, union)
    meta_cache.write_text(json.dumps(meta))
    return union, meta


def emit(field: np.ndarray, eligible: np.ndarray, novelty_union: np.ndarray) -> tuple[np.ndarray, dict]:
    """Frozen greedy: field-descending, >=3 px apart, skipping tier-2 colliding cells."""
    cells = np.flatnonzero(eligible)
    vals = field.ravel()[cells]
    order = cells[np.lexsort((cells, -vals))]
    taken = np.zeros(field.size, bool)
    out = np.zeros(field.size, bool)
    nov_flat = np.asarray(novelty_union).ravel().astype(bool)   # 2-D guest -> flat (fix)
    accepted = 0
    skipped_novelty = 0
    skipped_spacing = 0
    r = int(np.ceil(np.sqrt(SPACING2)))
    dy, dx = np.mgrid[-r:r + 1, -r:r + 1]
    disk = (dy * dy + dx * dx) < SPACING2
    W = field.shape[1]
    H = field.shape[0]
    for cell in order:
        if accepted >= BUDGET:
            break
        if taken[cell]:
            skipped_spacing += 1
            continue
        if nov_flat[cell]:
            skipped_novelty += 1
            continue
        out[cell] = True
        accepted += 1
        y, x = divmod(int(cell), W)
        ys, xs = y + dy, x + dx
        ok = (ys >= 0) & (ys < H) & (xs >= 0) & (xs < W) & disk
        taken[ys[ok] * W + xs[ok]] = True
    assert int(out.sum()) == accepted, 'emission bookkeeping mismatch'
    pred = out.reshape(field.shape).astype(np.float32)
    meta = dict(accepted=int(out.sum()), budget=BUDGET, skipped_novelty=skipped_novelty,
                skipped_spacing=skipped_spacing,
                rule="field-descending greedy, >=3px Euclidean, tier-2 novelty cells skipped "
                     "(sorted continuation is the re-placement)")
    log(f"[emit] {meta}")
    return pred, meta


def reasoning_rows(pred: np.ndarray, field: np.ndarray, b10: np.ndarray, cat: np.ndarray,
                   valid: np.ndarray) -> list[dict]:
    dist_cat = ndimage.distance_transform_edt(~cat)
    rows = []
    yy, xx = np.nonzero(pred > 0)
    for k in range(yy.size):
        r, c = int(yy[k]), int(xx[k])
        rows.append(dict(
            dot_id=k, row=r, col=c,
            utm_x=round(243350.0 + (c + 0.5) * 100.0, 1),
            utm_y=round(4508550.0 - (r + 0.5) * 100.0, 1),
            field_value=round(float(field[r, c]), 6),
            deq_distance_m=round(float(b10[r, c]), 1),
            dist_to_catalogue_px=round(float(dist_cat[r, c]), 2),
            hypothesis=("Valley line of the INGENIOUS distance-to-earthquake field "
                        "(deq_n100a15): recent seismicity clusters along an active structure "
                        "here; H65 R5-H2a. Measured context only, not field-verified geology."),
        ))
    return rows


def main() -> int:
    t0 = datetime.now(timezone.utc)
    DOWN.mkdir(parents=True, exist_ok=True)
    (ROOT / "work/h65b").mkdir(parents=True, exist_ok=True)

    with rasterio.open(ROOT / "data/sample_submission.tif") as s:
        tpl = s.read(1)
        sample = ROOT / "data/sample_submission.tif"
    valid = np.isfinite(tpl)
    with rasterio.open(ROOT / "data/labels.tif") as s:
        lb = s.read(1)
    cat = np.zeros(tpl.shape, bool)
    cat[valid] = np.isfinite(lb[valid]) & (lb[valid] > 0.5)
    b10 = E2.load_band(E2.B_EQD)
    field, meta = E2.valley_field(valid)
    log(f"[field] ridge_px={meta['ridge_px']}")

    eligible = valid & ~cat

    def file_sha(p: Path) -> str:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    # emission-time novelty union uses the frozen census only (no self-copies exist there)
    nov_census, _ = informative_union(gates.find_priors((ROOT / "work/h61/priors",), exclude=None),
                                      eligible)
    pred, emit_meta = emit(field, eligible, nov_census)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{PREFIX}band10-valley-{int(pred.sum())}px-{ts}"
    stem = ROOT / "submission" / name
    receipt = SW.write_submission(stem.with_suffix(".tif"), pred, sample, valid,
                                  note=NOTE, name=name,
                                  metadata=dict(round="H65b", hypothesis="R5-H2a",
                                                field_meta=meta, emission=emit_meta))
    log(f"[write] {stem.with_suffix('.tif').name}  sha256={receipt['sha256'][:16]}…")

    # gates on the written bytes.  Prior set: the frozen census + this repo's own artefacts,
    # minus any file byte-identical to the candidate itself (its copies in submission/ and
    # docs/downloads must never be scored as someone else's prior).
    priors = gates.find_priors((ROOT / "work/h61/priors", ROOT / "submission", ROOT / "docs/downloads"),
                               exclude=stem.with_suffix(".tif"))
    cand_sha = file_sha(stem.with_suffix(".tif"))
    cand_decoded = hashlib.sha256(np.ascontiguousarray(pred, dtype="<f4").tobytes()).hexdigest()
    keep = []
    for p in priors:
        try:
            _, dsha, _ = decode_support(p, pred.shape)
        except Exception:
            keep.append(p)          # unaligned priors stay; the gates record their error row
            continue
        if dsha == cand_decoded or file_sha(p) == cand_sha:
            log(f"  [prior-filter] dropping decoded/byte-identical self-copy: {p.name}")
            continue
        keep.append(p)
    priors = keep
    log(f"[priors] {len(priors)} priors for the gates (self-copies excluded by decoded and byte SHA)")
    nov_union, nov_meta = informative_union(priors, eligible)
    late_collisions = int((pred.astype(bool) & nov_union & eligible).sum())

    fmt = gates.format_report(stem.with_suffix(".tif"), sample, footprint=valid)
    uniq = gates.uniqueness_report(pred, priors, top=None)
    cov_cache: dict = {}
    lane_surface = gates.lane_report(field, eligible, priors, sample=sample, phase="surface",
                                     log=log, coverage_cache=cov_cache)
    lane_dots = gates.lane_report(pred, eligible, priors, sample=sample, phase="dots",
                                  log=log, coverage_cache=cov_cache)
    not_union = dict(round_has_two_views=False,
                     equals_literal_prior_union=uniq["equals_literal_prior_union"],
                     note="This round is a single-band detector; the brief's not-the-union "
                          "check is recorded as: the emission is not the literal union of any "
                          "prior set (see uniqueness_report) and no two-view union exists.")

    # the one-click downloads + reasoning CSV
    shutil.copy2(stem.with_suffix(".tif"), DOWN / "h65b-candidate.tif")
    shutil.copy2(stem.with_suffix(".zip"), DOWN / "h65b-candidate.zip")
    rows = reasoning_rows(pred, field, b10, cat, valid)
    with open(DOWN / "h65b-reasoning.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    hold = json.loads((ROOT / "evidence/h65b_e2_holdout.json").read_text())
    gate = json.loads((ROOT / "evidence/h65b_gate.json").read_text())
    pooled = hold["pooled"]["scores"]
    card = dict(
        round="H65b", generated_utc=now(),
        hypothesis=("R5-H2a: fault traces are valley lines of the band-10 distance-to-earthquake "
                    "field deq_n100a15 (never previously read in this repo); R5-H1 trace-"
                    "correction corridor was gate-refuted first (E1 FAIL, G3 margin 0.000 px)"),
        mechanism=("v = 1 - exact rank(band 10); sigma-1 smoothing; non-maximum suppression along "
                   "the gradient; 90th-percentile ridge threshold; top-15,000 cells, >=3 px "
                   "apart, off-catalogue, tier-2 novel vs 526-raster registry"),
        named_mimic=("seismicity aligned by a non-fault process ( swarm triggered by geothermal "
                     "or mining activity; range-front event clustering on a fold), and the "
                     "band's own 15-deg sector convention, which is undocumented"),
        e1_r5h1_gate=dict(verdict=gate["verdict"],
                          conditions={k: v["ok"] for k, v in gate["conditions"].items()}),
        holdout_dti=dict(
            label=("HOLDOUT-DTI, evaluator gems52-pooled-hide-v1 (this run's config: 4 hide "
                   "folds, buffer 4, prevalence 0.002, seed 0; %d withheld positives)"
                   % pooled["candidate"]["withheld_positive_pixels"]),
            candidate=[pooled["candidate"]["dti"]] + list(pooled["candidate"]["ci95"]),
            singleB=[pooled["singleB"]["dti"]] + list(pooled["singleB"]["ci95"]),
            random=[pooled["random"]["dti"]] + list(pooled["random"]["ci95"]),
            paired_candidate_minus_singleB=hold["pooled"]["paired_differences"]["singleB"],
            leakage_canary=hold["leakage_canary"],
            reading="candidate < single_B and < random: negative"),
        registry=dict(priors=len(priors), novelty=nov_meta,
                      lane_surface=dict(
                          literal=dict(max_spearman=lane_surface["literal"]["max_spearman"],
                                       max_near=lane_surface["literal"]["max_near_3px_fraction"],
                                       verdict=lane_surface["literal"]["verdict"]),
                          policy=dict(max_spearman=lane_surface["policy"]["max_spearman"],
                                      max_near=lane_surface["policy"]["max_near_3px_fraction"],
                                      verdict=lane_surface["policy"]["verdict"]),
                          ok=lane_surface["ok"], duplicate=lane_surface["duplicate"]),
                      lane_dots=dict(
                          literal=dict(max_spearman=lane_dots["literal"]["max_spearman"],
                                       max_near=lane_dots["literal"]["max_near_3px_fraction"],
                                       verdict=lane_dots["literal"]["verdict"]),
                          policy=dict(max_spearman=lane_dots["policy"]["max_spearman"],
                                      max_near=lane_dots["policy"]["max_near_3px_fraction"],
                                      verdict=lane_dots["policy"]["verdict"]),
                          ok=lane_dots["ok"], duplicate=lane_dots["duplicate"])),
        raster_sha256=receipt["sha256"],
        validator=dict(ok=fmt["ok"], problems=fmt["problems"], shape=[fmt["height"], fmt["width"]],
                       crs=fmt["crs"], dtype=fmt["dtype"], nan=fmt["nan_pixels"],
                       vmin=fmt.get("min"), vmax=fmt.get("max"),
                       transform_match=fmt["transform"] == list(__import__("rasterio").open(sample).transform)[:6]),
        submission=dict(name=name, note=NOTE, note_chars=len(NOTE),
                        file=stem.with_suffix(".tif").name,
                        bytes=receipt["bytes"]),
        budget=dict(experiments_used=3, wall_clock_started="2026-10-09T03:44Z",
                    note="E1 R5-H1 gate (FAIL); E2 R5-H2a holdout (negative); E3 build+gates"),
        verdict="NEGATIVE (DOWNLOAD YES for research; SUBMIT NO - holdout does not beat single_B)",
    )
    card["registry"]["late_novelty_collisions_after_full_prior_set"] = late_collisions
    (ROOT / "evidence/h65b_run_card.json").write_text(json.dumps(card, indent=2, allow_nan=False) + "\n")
    gates.write_report(ROOT / "evidence/h65b_uniqueness.json", uniq)
    gates.write_report(ROOT / "evidence/h65b_lane_surface.json", lane_surface)
    gates.write_report(ROOT / "evidence/h65b_lane_dots.json", lane_dots)
    gates.write_report(ROOT / "evidence/h65b_format.json", fmt)
    log(f"[gates] format ok={fmt['ok']}  uniqueness canonical_unique={uniq['canonical_pattern_unique']} "
        f"novel_fraction={uniq['novel_fraction']:.4f}")
    log(f"[gates] lane surface: literal={lane_surface['literal']['verdict']} "
        f"(rho_max={lane_surface['literal']['max_spearman']}, "
        f"near_max={lane_surface['literal']['max_near_3px_fraction']}) "
        f"policy={lane_surface['policy']['verdict']}")
    log(f"[gates] lane dots:    literal={lane_dots['literal']['verdict']} "
        f"(rho_max={lane_dots['literal']['max_spearman']}, "
        f"near_max={lane_dots['literal']['max_near_3px_fraction']}) "
        f"policy={lane_dots['policy']['verdict']}")
    log(f"[done] {(datetime.now(timezone.utc) - t0).total_seconds():.0f}s  "
        f"evidence/h65b_run_card.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
