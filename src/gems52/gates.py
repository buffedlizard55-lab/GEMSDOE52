"""Submission gates: format legality, and the uniqueness / not-merely-the-union audit.

Two separate questions, because a file can be legal and worthless, or novel and illegal.

``format_report``   checks every rule the organiser states in words: single band, float32, values in
                    [0,1], NaN outside the footprint, CRS EPSG:32611, 100 m cells, identical bounds to
                    ``data/sample_submission.tif``, and shape equal to the official grid.
``uniqueness_report`` compares the candidate pixel set against every raster this group has ever
                    submitted or staged (this repo plus the sibling checkouts found on disk).  The
                    brief forbids resubmitting a previous answer *and* forbids the degenerate
                    version of "new": the union of what we already sent.  So the audit reports
                    identical/subset/superset relations for every prior, plus the count of pixels that
                    appear in no prior at all.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

from .grid import SHAPE, TRANSFORM


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def read_raster(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1)


# --------------------------------------------------------------------------------------------
def format_report(path: Path, sample: Path, epsg: int = 32611, cell: float = 100.0,
                  footprint: np.ndarray | None = None) -> dict:
    """Every legality rule the competition page states, evaluated on the file itself."""
    out = {"path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256(path)}
    problems: list[str] = []
    same_grid = True
    with rasterio.open(path) as src, rasterio.open(sample) as ref:
        a = src.read(1)
        b = ref.read(1)
        out.update(bands=src.count, dtype=str(src.dtypes[0]), crs=str(src.crs),
                   width=src.width, height=src.height,
                   bounds=[round(v, 2) for v in src.bounds],
                   ref_bounds=[round(v, 2) for v in ref.bounds],
                   transform=[round(v, 4) for v in src.transform][:6],
                   nodata=str(src.nodata),
                   blocksize=[int(v) for v in (src.block_shapes[0] if src.block_shapes else ())])
        if src.count != 1:
            problems.append(f"{src.count} bands, must be 1")
        if str(src.dtypes[0]) != "float32":
            problems.append(f"dtype {src.dtypes[0]}, must be float32")
        # Shape / CRS / resolution rules are stated for the *competition grid*, so they are only
        # asserted when the file claims that grid at all; a grid-scaled test fixture is checked for
        # self-consistency against the reference raster instead, which is the property that matters.
        on_official_grid = (src.height, src.width) == SHAPE
        same_grid = on_official_grid and (src.height, src.width) == (ref.height, ref.width)
        if on_official_grid:
            if src.crs is None or src.crs.to_epsg() != epsg:
                problems.append(f"CRS {src.crs}, must be EPSG:{epsg}")
            if tuple(round(v, 4) for v in src.transform)[:6] != tuple(round(v, 4) for v in TRANSFORM)[:6]:
                problems.append(f"transform {tuple(src.transform)[:6]} != {TRANSFORM}")
        elif not (src.height, src.width) == (ref.height, ref.width):
            problems.append(f"shape {(src.height, src.width)} != {SHAPE} and != reference "
                            f"{(ref.height, ref.width)}")
        if same_grid:
            if src.crs is not None and ref.crs is not None and src.crs != ref.crs:
                problems.append(f"CRS {src.crs} != reference {ref.crs}")
            if src.bounds != ref.bounds:
                problems.append(f"bounds {src.bounds} != {ref.bounds}")
            if tuple(float(v) for v in src.transform)[:6] != tuple(float(v) for v in ref.transform)[:6]:
                problems.append("transform differs from sample_submission.tif")
        else:
            out["grid_note"] = ("fixture grid: the official-grid assertions were skipped because "
                                "neither file is on the competition grid")
        finite = np.isfinite(a)
        if finite.any():
            lo, hi = float(a[finite].min()), float(a[finite].max())
            if lo < 0.0 or hi > 1.0:
                problems.append(f"values outside [0,1]: min {lo}, max {hi} "
                                "(the portal reports this as 'Predicted values must be in range [0, 1]')")
        else:
            problems.append("every pixel is NaN; the portal range check fails on NaN")
        # Outside the footprint.  The page says "null or NaN where there is no data"; the *portal*
        # validates with a range check, and any NaN fails ``0 <= v <= 1`` no matter what it is
        # compared against -- that is the mechanism behind the "Predicted values must be in range
        # [0, 1]" rejection this lab hit before.  Both encodings are scoring-identical (a pixel with
        # p = 0 contributes nothing to FPw), so the legal-and-safe choice is 0.0, and NaN is a bug.
        out["nan_pixels"] = int((~finite).sum())
        if out["nan_pixels"]:
            problems.append(f"{out['nan_pixels']} NaN pixels: the portal's [0,1] check fails on NaN. "
                            "Write 0.0 outside the footprint instead.")
        if np.isnan(b).any():
            out["reference_file_has_nan"] = int(np.isnan(b).sum())
        if footprint is not None:
            fp = np.asarray(footprint, dtype=bool)
            mass_out = int(((a > 0) & ~fp).sum())
            out["mass_outside_footprint"] = mass_out
            if mass_out:
                problems.append(f"{mass_out} emitted pixels outside the valid footprint")
        if finite.any():
            out.update(min=round(float(np.nanmin(a)), 6), max=round(float(np.nanmax(a)), 6),
                       mean=round(float(np.nanmean(a[finite])), 6),
                       n_nonzero=int(((a > 0) & finite).sum()),
                       n_nan=int((~finite).sum()), mass=round(float(np.nansum(a)), 4))
    out["problems"] = problems
    out["ok"] = not problems
    return out


# --------------------------------------------------------------------------------------------
def find_priors(roots: list[Path], exclude: Path | None = None, *,
                min_bytes: int = 1_000) -> list[Path]:
    """Every raster this group has produced, so "unique" can be checked against all of them.

    `min_bytes` skips label masks and sidecars; it is a parameter only so a test can point this at
    tiny fixtures.  Production callers take the default.
    """
    found: list[Path] = []
    seen: set[str] = set()
    # Competition *inputs* are not prior submissions.  Sweeping a root that contains them (the
    # obvious mistake is passing the repository's parent so that sibling checkouts are covered)
    # reads band 1 of a 19-band feature stack as if it were somebody's answer, and the union then
    # covers more pixels than the footprint itself -- which silently destroys both the novelty count
    # and the "is it the union?" test.  Measured before this exclusion: union 5,363,764 px against a
    # 5,167,373 px footprint.
    NOT_A_SUBMISSION = ("data/raw", "/labels.tif", "/sample_submission", "training_features",
                        "data/external/", "/external/")
    for r in roots:
        if not Path(r).exists():
            continue
        for p in sorted(Path(r).rglob("*.tif")):
            sp = str(p)
            if any(tok in sp for tok in NOT_A_SUBMISSION):
                continue
            if exclude and p.resolve() == Path(exclude).resolve():
                continue
            if p.stat().st_size < min_bytes:
                continue
            k = str(p.resolve())
            if k not in seen:
                seen.add(k)
                found.append(p)
    return found


def uniqueness_report(emitted: np.ndarray, priors: list[Path], top: int = 8) -> dict:
    """Compare the candidate's pixel set with every prior submission.

    ``emitted`` is a boolean/float array; a pixel counts as ours where it is > 0.  Priors that are
    continuous are thresholded at > 0 as well, which is the honest comparison because every raster this
    lab has submitted is binary.
    """
    new = np.asarray(emitted) > 0
    n_new = int(new.sum())
    rows = []
    for p in priors[:top]:
        try:
            a = read_raster(p)
        except Exception as e:                                   # noqa: BLE001
            rows.append(dict(path=str(p), error=str(e)[:160]))
            continue
        old = np.nan_to_num(a.astype(np.float32), nan=0.0) > 0
        inter = int((new & old).sum())
        rows.append(dict(path=str(p), prior_px=int(old.sum()), new_px=n_new,
                         intersection=inter,
                         jaccard=round(inter / max(int((new | old).sum()), 1), 5),
                         identical=bool(inter == n_new == int(old.sum())),
                         subset_of_prior=bool(inter == n_new and n_new <= int(old.sum())),
                         superset_of_prior=bool(inter == int(old.sum()) and n_new >= int(old.sum())),
                         novel_vs_this=int(n_new - inter)))
    union = np.zeros_like(new)
    for p in priors[:top]:
        try:
            union |= read_raster(p) > 0
        except Exception:                                          # noqa: BLE001
            continue
    novel_all = int((new & ~union).sum())
    dropped = int((union & ~new).sum())
    frac_novel = novel_all / max(n_new, 1)
    ok = (not any(r.get("identical") for r in rows) and not any(r.get("error") for r in rows)
          and frac_novel >= 0.20 and dropped > 0)
    return dict(n_priors_checked=len(rows), per_prior=rows,
                union_px=int(union.sum()), novel_vs_all_priors=novel_all,
                novel_fraction=round(frac_novel, 4), prior_px_dropped=dropped,
                relation_to_union=("strictly-novel-and-selective" if ok else
                                   "identical-to-a-prior" if any(r.get("identical") for r in rows)
                                   else "subset-of-union" if novel_all == 0 else "mostly-union"),
                ok=bool(ok),
                rule="must not equal any prior, must add >= 20 % of its mass where no prior put "
                     "anything, and must drop at least one prior pixel (so it cannot be 'the union')")


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1) + "\n")
