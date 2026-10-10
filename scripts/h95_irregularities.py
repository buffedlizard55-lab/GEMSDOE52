#!/usr/bin/env python3
"""Record the irregularities H95 found, each verified against bytes on disk or a live official page.

Writes ``evidence/h95_irregularities.json`` (the site reads it) and appends the same entries to the
machine-readable register ``registry/irregularities.json`` without touching any existing entry.

Nothing here is inherited unverified: every claim below was re-measured in this session, and the
command that measured it is written into the entry.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
REG = ROOT / "registry"

FOUND_UTC = "2026-10-10T21:50:00Z"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


# The state of main when this session started. Findings about the site as this round FOUND it are
# detected from this revision, not from the working tree, because a later parallel session may since
# have cleaned the file up - which would silently delete the finding from the register.
BASE_REV = "ebb1d34"


def _show(rev, path):
    import subprocess
    try:
        return subprocess.run(["git", "show", f"{rev}:{path}"], cwd=ROOT, capture_output=True,
                              text=True, timeout=60).stdout
    except Exception:                                                  # noqa: BLE001
        return ""


def measure() -> list[dict]:
    e = []
    dl = ROOT / "docs" / "downloads"

    # ---- IR-H95-001  download path and its adjacent receipt describe different bytes -------------
    tif, rec = dl / "h83-candidate.tif", dl / "h83-candidate.json"
    if tif.exists() and rec.exists():
        j = json.loads(rec.read_text())
        actual, claimed = sha(tif), j.get("sha256")
        ab, cb = tif.stat().st_size, j.get("file_bytes")
        if actual != claimed or ab != cb:
            e.append(dict(
                id="IR-H95-001", round="H95", severity="high", detected_utc=FOUND_UTC,
                status="open - published as a measured manifest; the other round's artefacts were NOT overwritten",
                title="A served download path and its adjacent JSON receipt describe different bytes than the file at that path",
                what_it_is=(
                    f"docs/downloads/h83-candidate.json claims sha256 {claimed} and file_bytes {cb}, "
                    f"submission_name 'h83-structural-concordance-37654px-20261010T200049Z'. The file "
                    f"actually served at docs/downloads/h83-candidate.tif is sha256 {actual}, {ab} bytes, "
                    f"which is the OTHER parallel H83 round's artefact "
                    f"(submission/gems52-h83-structcon-geotherm-37654px-20261010T200310Z.tif). Two "
                    f"parallel sessions merged to main within 43 seconds of each other and both wrote "
                    f"docs/downloads/h83-candidate.tif; the later write silently replaced the earlier "
                    f"one while the earlier one's receipt survived."),
                how_we_know=(
                    "sha256sum docs/downloads/h83-candidate.tif; python3 -c \"import json;"
                    "print(json.load(open('docs/downloads/h83-candidate.json'))['sha256'])\"; "
                    "sha256sum submission/gems52-h83-*.tif; git log --stat -2 d5e61ad 4d06537"),
                why_it_matters=(
                    "This is exactly the defect class that produces a confusing portal rejection: a user "
                    "reads a receipt, downloads a different file, and the name/note/hash they were told "
                    "to paste do not describe the bytes they upload. It also breaks the audit trail, "
                    "because the receipt is the only place the round's method is described."),
                handling=(
                    "Not papered over and not repaired by rewriting another round's artefacts. "
                    "scripts/publish_h95_site.py re-measures EVERY served download from its own bytes "
                    "and writes docs/downloads/MANIFEST.json, flagging receipt_matches_bytes=false "
                    "wherever a receipt has drifted. A manifest derived from the files cannot drift from "
                    "them. The H95 download's own receipt is regenerated from the copied bytes at "
                    "publish time and the copy is re-hashed against submission/ before the page is "
                    "written, so the same defect cannot occur for this round.")))

    # ---- IR-H95-002  promote without a holdout, and a false "no priors" claim -------------------
    rc_txt = _show(BASE_REV, "evidence/h83_run_card.json")
    rc_now = ROOT / "evidence" / "h83_run_card.json"
    if rc_txt:
        j = json.loads(rc_txt)
        verdict = j.get("verdict")
        ho = (j.get("holdout_dti") or {}).get("value")
        corr = (j.get("correlation_vs_registry") or {}).get("note")
        n_sub = len(list((ROOT / "submission").glob("*.tif")))
        n_dl = len(list(dl.glob("*.tif")))
        if verdict == "promote" and ho != "NOT_EVALUATED":
            verdict = None
        if verdict == "promote":
            e.append(dict(
                id="IR-H95-002", round="H95", severity="high", detected_utc=FOUND_UTC,
                status="open - flagged; the artefacts belong to two parallel sessions and were not edited",
                title="evidence/h83_run_card.json records verdict 'promote' with holdout_dti 'NOT_EVALUATED', and claims there are no prior submissions to compare against",
                what_it_is=(
                    f"The run card sets \"verdict\": \"promote\" while its own holdout_dti.value is "
                    f"\"NOT_EVALUATED\" with a null CI and null withheld-positive count, and its "
                    f"correlation_vs_registry.note reads \"{corr}\". docs/index.html, published from the "
                    f"same round, prints \"SUBMIT: YES\" and \"Ready-to-submit GeoTIFF\". Measured in "
                    f"this checkout: {n_sub} TIFFs in submission/ and {n_dl} in docs/downloads/, plus 13 "
                    f"owner-scored and reference rasters restored into data/scored/ and data/reference/. "
                    f"The lane uniqueness gate was not run at all."),
                how_we_know=(
                    f"git show {BASE_REV}:evidence/h83_run_card.json -> verdict, holdout_dti.value and "
                    "correlation_vs_registry.note; ls submission/*.tif | wc -l; "
                    f"ls docs/downloads/*.tif | wc -l; git show {BASE_REV}:docs/index.html | grep -c "
                    "'SUBMIT: YES'. Detected at the revision main held when this session started, so a "
                    "later session cleaning the file cannot silently delete the finding."),
                why_it_matters=(
                    "The brief's rule is explicit: do not spend a submission slot on an idea that has "
                    "not beaten the current holdout best, and check lane uniqueness on the surface "
                    "before placement and on the final dots. A 'promote' verdict with no holdout number "
                    "and no lane check invites a user to spend a scarce weekly slot on an unvalidated "
                    "candidate that may also be a lane duplicate."),
                handling=(
                    "Flagged, not silently corrected. The H95 site states both rounds' dispositions "
                    "side by side and publishes the measured download manifest. H95's own run card "
                    "reports verdict, download_ok and submit_ok as three separate fields computed from "
                    "the gate results, so a 'promote' cannot appear without a holdout number behind it.")))

    # ---- IR-H95-003  projections printed adjacent to scores -------------------------------------
    t = _show(BASE_REV, "docs/index.html")
    if t:
        if "Expected Score Range" in t and "0.30" in t:
            e.append(dict(
                id="IR-H95-003", round="H95", severity="medium", detected_utc=FOUND_UTC,
                status="flagged; superseded for the current round by the H95 pages, which print no "
                       "expected-score table",
                title="docs/index.html publishes an 'Expected Score Range' table putting 0.30-0.38 beside real scores",
                what_it_is=(
                    "The page carries a table headed 'Expected Score Range' with rows 'Concordance + "
                    "geothermal (optimistic) | 0.10-0.14 | 0.30-0.38' and 'h33-2-b2 reference | 0.1387 "
                    "| 0.2778', i.e. a projection printed in the same column as an owner-reported board "
                    "score. A disclaimer follows the table, but the table itself is what a reader "
                    "remembers."),
                how_we_know=(f"git show {BASE_REV}:docs/index.html | grep -o 'Expected Score Range'; "
                             f"git show {BASE_REV}:docs/index.html | grep -o '0.30\u20130.38'. Detected at "
                             "the revision main held when this session started; the working tree may "
                             "since have been rewritten by a later round."),
                why_it_matters=(
                    "The parallel-run protocol's rule 3 is that a projection is never written as a score, "
                    "and every number must be labelled HOLDOUT-DTI, OWNER-REPORTED or "
                    "ORGANIZER-CONFIRMED. An unlabelled 0.30-0.38 next to a real 0.2778 reads as a "
                    "forecast of this file's board performance, which nobody can produce."),
                handling=(
                    "The H95 pages print no expected-score table. Where the algebra is used "
                    "(knowledge/49, and the 'what would actually move the number' section of "
                    "docs/index.html) it is labelled as a bound derived from owner-reported scores, and "
                    "the run card carries is_a_leaderboard_forecast=false explicitly.")))

    # ---- IR-H95-004  the two landing pages disagree ---------------------------------------------
    # Detected from git history, not from the working tree: this session republishes both landing
    # pages, so reading them after the fix would make the finding look as if it had never happened.
    r, d = _show(BASE_REV, "index.html"), _show(BASE_REV, "docs/index.html")
    if r and d:
        if ("H82" in r and "h83-structcon" in d):
            e.append(dict(
                id="IR-H95-004", round="H95", severity="medium", detected_utc=FOUND_UTC,
                status="resolved for the current round - both pages now describe H95",
                title="The repository root landing page and docs/index.html described different rounds as current",
                what_it_is=(
                    "After the two parallel H83 merges, index.html (the GitHub Pages entry point for the "
                    "repository root) still described H82 as the current round and linked "
                    "docs/downloads/h82-candidate.tif, while docs/index.html described an H83 round and "
                    "linked docs/downloads/h83-candidate.tif. A visitor could land on either and be told "
                    "a different file was the current candidate, with different verdicts."),
                how_we_know="git show ebb1d34:index.html | grep -c H82  (-> 3); "
                            "git show ebb1d34:docs/index.html | grep -c h83-structcon  (-> 4); "
                            "ebb1d34 is the merge of PR #82, the state of main when this session started",
                why_it_matters=(
                    "The brief requires that it be obvious, on arriving at the site, which file to "
                    "download and whether it may be submitted. Two entry points disagreeing about the "
                    "current candidate defeats that outright."),
                handling=(
                    "scripts/publish_h95_site.py writes BOTH index.html and docs/index.html from the "
                    "same evidence files in the same run, and re-hashes the copied download against "
                    "submission/ before writing either page, so the two cannot disagree about the "
                    "current round or its bytes.")))

    # ---- IR-H95-005  our own incomplete threshold transcription ---------------------------------
    pre = REG / "h95_preregistration.json"
    if pre.exists():
        j = json.loads(pre.read_text())
        if "thresholds_completion_note" in j:
            e.append(dict(
                id="IR-H95-005", round="H95", severity="low", detected_utc=FOUND_UTC,
                status="resolved before any independence measurement",
                title="H95's own inherited-threshold block was transcribed incompletely and the independence stage raised KeyError",
                what_it_is=(
                    "registry/h95_preregistration.json transcribes its thresholds verbatim from "
                    "registry/h74_preregistration.json but the first transcription omitted "
                    "receiver_rank_interval, min_pseudo_pixels, pseudo_cap_per_fold and "
                    "universal_coverage_probe_threshold. scripts/run_h95.py stage_independence reads "
                    "receiver_rank_interval[1] to set the receiver cut and raised KeyError."),
                how_we_know=(
                    "PYTHONPATH=src python3 scripts/run_h95.py independence -> KeyError: "
                    "'receiver_rank_interval'; json.load of both registry files compared key by key"),
                why_it_matters=(
                    "A threshold that is read at measurement time but was not pinned beforehand is a "
                    "threshold that could have been chosen after seeing the result. The fix had to be "
                    "provably a transcription, not a tune."),
                handling=(
                    "The four keys were copied verbatim from the donor file BEFORE the independence "
                    "stage was re-run, and the edit is recorded inside the pin itself "
                    "(thresholds_completion_note). The abandon bar 0.60, donor rank 0.95, block side "
                    "50 px, minimum 20 blocks and every other threshold were already pinned and were "
                    "not edited. check_prereg() re-validates the runner's constants against the pin on "
                    "every stage.")))

    # ---- IR-H95-006  our own verified-write comparison was wrong --------------------------------
    e.append(dict(
        id="IR-H95-006", round="H95", severity="medium", detected_utc=FOUND_UTC,
        status="resolved in the runner; no number was produced by the defective comparison",
        title="save_verified rejected correct NaN-bearing out-of-fold grids, because np.array_equal reports NaN != NaN",
        what_it_is=(
            "scripts/run_h95.py initialises each out-of-fold prediction grid to NaN off the evaluation "
            "region, then writes it through save_verified(), which re-reads the file and compares "
            "bit-exactly before accepting it. np.array_equal returns False whenever NaNs are present, "
            "so every correct write of a NaN-bearing grid looked like corruption, exhausted three "
            "rewrite attempts and fail-closed with an OSError on fold 0."),
        how_we_know=(
            "PYTHONPATH=src python3 scripts/run_h95.py fit -> OSError: save_verified could not produce "
            "a bit-exact file for work/h95/oofA_f0.npy, preceded by three 'mismatch on attempt N' lines "
            "0.1 s apart, which is a comparison failing, not a disk write failing"),
        why_it_matters=(
            "The verified-write pattern exists so a corrupted channel can never reach a model silently. "
            "A comparison that is wrong in the fail-closed direction stops the round rather than "
            "corrupting it, which is the safe failure - but it also means the check was not actually "
            "checking anything on NaN-bearing arrays, and a genuinely truncated write would have "
            "produced the identical message."),
        handling=(
            "Fixed once, in the runner: np.array_equal(back, want, equal_nan=True), plus the NaN count "
            "is now recorded in the write receipt so the number of deliberately-NaN pixels is visible "
            "rather than hidden inside a comparison. Not forked around, not suppressed. The stage was "
            "re-run from scratch; no result in this round was produced by the defective comparison.")))

    # ---- IR-H95-007  band 6 tag contradiction, independently re-verified -------------------------
    b6 = EVID / "h95_band6_identity_recheck.json"
    if b6.exists():
        j = json.loads(b6.read_text())
        tag = j["tag_in_file"]
        comp = {c.get("external_band", c.get("control")): c["spearman_vs_band6"] for c in j["comparisons"]}
        e.append(dict(
            id="IR-H95-007", round="H95", severity="medium", detected_utc=FOUND_UTC,
            status="open in the organiser's file - re-verified independently this session, and used only under its measured identity",
            title="training_features.tif band 6 is tagged data_category='magnetic_data' / 'Tilt angle or total curvature' but is the aeroradiometric total-count grid",
            what_it_is=(
                f"The organiser's own file tags band 6 with band_name='{tag.get('band_name')}', "
                f"data_category='{tag.get('data_category')}', description='{tag.get('description')}'. "
                f"band_name says total count; the category and description say a magnetic derivative. "
                f"Measured this session on a 1-in-37 subsample: band 6 ranges {j['measured_min']:.2f} to "
                f"{j['measured_max']:.2f} (a tilt angle would span roughly -90 to +90 and a curvature "
                "would be signed), Spearman against geodawn_rad_u8 band 4 is "
                f"{comp.get(4):.6f}, and against TMI (band 14) it is {comp.get('band14_TMI'):.6f}. "
                "Band 6 is radiometric total count; the category and description tags are wrong."),
            how_we_know=(
                "python3 -c reading rasterio tags(6) from data/training_features.tif and Spearman-"
                "correlating band 6 against all four bands of data/external/geodawn_rad_u8.tif and "
                "against band 14; receipt evidence/h95_band6_identity_recheck.json. This re-derives "
                "docs/data/h55_band6_identity.json independently rather than citing it."),
            why_it_matters=(
                "The brief defines View B as surface curvature and slope 'plus any radiometric bands "
                "present in training_features.tif'. Taking the tags at face value puts a radiometric "
                "band into View A as a magnetic edge detector, which would corrupt the view split that "
                "the whole co-training method rests on. It also means any round that used band 6 as a "
                "tilt/curvature channel was testing the wrong physics."),
            handling=(
                "Band 6 is assigned to View B, as radiometric total count, and the assignment is "
                "recorded in evidence/h95_band_tags.json and evidence/h95_band6_identity_recheck.json "
                "with the measurement that justifies it. The residual assumption is stated rather than "
                "hidden: geodawn_rad_u8.tif carries NO band descriptions, so which of its four uint8 "
                "layers is TC is not stated by any source; band 6's identity rests on its own "
                "band_name='tc' tag plus its value range plus a 0.99995 rank match to one of those "
                "layers plus a near-zero match to TMI.")))

    # ---- IR-H95-008  the external rasters are unauditable ---------------------------------------
    e.append(dict(
        id="IR-H95-008", round="H95", severity="medium", detected_utc=FOUND_UTC,
        status="open - worked around by not using them",
        title="The three external uint8 rasters carry no band descriptions at all, so their channels cannot be audited against any source",
        what_it_is=(
            "data/external/lidar_scarp_features_u8.tif (12 bands), geodawn_rad_u8.tif (4 bands) and "
            "geodawn_extensions_u8.tif (4 bands) are all EPSG:32611, 3730x3292, uint8, on the "
            "competition transform - and rasterio tags(i) returns an empty dict for every band of every "
            "one. There is no name, no category, no unit and no source reduction recorded in the bytes. "
            "They are integrity-pinned mirrors of an owner-side CI reduction, not organiser-authenticated "
            "products."),
        how_we_know=(
            "python3 -c \"import rasterio;s=rasterio.open('data/external/lidar_scarp_features_u8.tif');"
            "print([s.tags(i) for i in range(1,s.count+1)])\" -> [{}, {}, ...]; same for the other two"),
        why_it_matters=(
            "The brief requires working line by line from official verified sources with no "
            "hallucinations. A detector built on 20 unlabelled uint8 layers cannot be audited: if it "
            "scores, nobody can say what it detected, and if it leaks, nobody can say from where. The "
            "LiDAR scarp product in particular is the reachable substitute for the 1 m DEM lever that "
            "knowledge/49 identifies as the only one with measured headroom, so this is not a trivial "
            "gap."),
        handling=(
            "H95 uses ONLY bands of training_features.tif whose identity the organiser's own file "
            "states (recorded in evidence/h95_band_tags.json), and does not use the external rasters as "
            "learner inputs. The gap is named as the specific thing a future round must close before it "
            "can use them: a per-band provenance record for the owner's reduction, or a re-reduction "
            "from source that this sandbox can actually reach.")))

    # ---- IR-H95-010  holdout reproducibility discrepancy, mechanism unresolved ---------------
    ho = EVID / "h95_holdout.json"
    if ho.exists():
        j = json.loads(ho.read_text())
        rp = j.get("reproducibility") or {}
        if rp.get("superseded_first_run_pooled_single_B"):
            e.append(dict(
                id="IR-H95-010", round="H95", severity="medium", detected_utc=FOUND_UTC,
                status="open - mechanism UNRESOLVED; inputs now hashed into the receipt so it is attributable",
                title="The seeded holdout stage produced a different pooled control on its first execution than on two bit-identical re-runs, with unchanged inputs",
                what_it_is=(
                    f"stage_holdout is fully seeded (np.random.default_rng(SEED+1), fixed fold order, "
                    f"fixed arm order) and reads only files on disk. Its first execution returned a "
                    f"pooled single_B of {rp['superseded_first_run_pooled_single_B']}; two consecutive "
                    f"re-runs returned {rp['current_pooled_single_B']:.6f} with a maximum absolute "
                    f"difference of {rp['max_abs_difference']} across all 28 arm-by-fold values and all "
                    f"pooled values. The inputs did not change between them: work/h95/oofA_f*.npy and "
                    f"oofB_f*.npy were written by the fit stage and never rewritten, and their SHA-256 "
                    f"is now recorded in evidence/h95_holdout.json -> input_sha256."),
                how_we_know=(
                    "ls -la --time-style=+%H:%M:%S work/h95/oof[AB]_f*.npy (mtimes 21:48-21:49, three "
                    "holdout executions at 21:50, 22:44 and 22:46); the run logs of all three; and the "
                    "diff of evidence/h95_holdout.json between the second and third runs, which is empty "
                    "to 1e-9 on every arm and fold"),
                why_it_matters=(
                    "A number that cannot be reproduced is not a measurement. If the discrepancy came "
                    "from an input, the fit stage is at fault and every downstream number is suspect; "
                    "if it came from the stage, the shared evaluator or the placement helper has a "
                    "nondeterminism that affects every round that uses them. Neither can be ruled out "
                    "from the evidence available, and guessing would be worse than saying so."),
                handling=(
                    "Recorded, not explained. (1) Two consecutive re-runs were diffed and are "
                    "bit-identical, so the stage as it now stands is reproducible. (2) The stage writes "
                    "input_sha256 for every file it consumes plus a reproducibility block, so the next "
                    "occurrence is attributable. (3) Every published H95 number comes from the "
                    "reproducible pair; the first run's values are superseded and appear nowhere else. "
                    "(4) Impact is bounded and stated: about 0.0009 on the control and 0.0012 on the "
                    "paired delta, against a primary arm that sits below random placement by 0.0127, so "
                    "no gate and no verdict depends on it.")))

    # ---- IR-H95-011  namespace collision with a parallel round; identifier-only rename --------
    rr = EVID / "h95_rename_record.json"
    if rr.exists():
        j = json.loads(rr.read_text())
        e.append(dict(
            id="IR-H95-011", round="H95", severity="high", detected_utc=FOUND_UTC,
            status="resolved - round renamed at merge, following the IR-H71-005 / IR-H74-002 / IR-H82-008 precedent",
            title="Namespace collision: this session's round was numbered H84, but origin/main already holds a different H84 round plus H85-H94 from parallel sessions",
            what_it_is=(
                "This session pre-registered, executed and published its signed strain-dipole "
                "co-training round as H84 (runner scripts/run_h84.py, evidence/h84_*.json, submission "
                "prefix gems52-h84-straindipole-). While it ran, parallel sessions merged rounds H84 "
                "(a completely different mechanism: elliptical spatial-covariance anisotropy, "
                "gems52-h84-hva-ellipse-B-37654px-20261010T204630Z) through H94 to main, so PR-level "
                "artefact paths collided outright on 15 files including both landing pages, "
                "docs/downloads/h84-candidate.tif, evidence/h84_run_card.json, "
                "registry/h84_preregistration.json, knowledge/74 and both runners."),
            how_we_know=(
                "git fetch origin; git ls-tree -r --name-only origin/main | grep -i h84 (main's H84 is "
                "the hva-ellipse round); git ls-tree -r --name-only origin/main | grep -oE "
                "'h(8[0-9]|9[0-9])[-_]' shows H81-H94 all taken; git merge origin/main reported 20 "
                "conflicts of which 15 were add/add on h84 paths"),
            why_it_matters=(
                "Two different mechanisms under one identifier would make every later citation "
                "ambiguous, and a merge that silently took one side would delete the other round's "
                "preregistration, receipts and raster. The lane census is also affected: a receipt "
                "taken before the merge was scoped to 66 rasters while main now holds 79."),
            handling=(
                "The merge was resolved by taking main's version of every colliding h84 path, so the "
                "parallel round is intact, and this round was then renamed H84 -> H95 (the next free "
                "identifier) with identifier-only edits, recovered from this branch's own commit "
                "f963831. The rename is provable, not asserted: the GeoTIFF is BYTE-IDENTICAL before "
                "and after (SHA-256 c122a9ff37abf5512bbddf39c9d55c60effb2229ed992d959e357ffb804a50f3, "
                "132,513 bytes, both times) because a TIFF does not store its own filename; only the "
                "ZIP's SHA-256 changed, because a ZIP stores its inner member's filename. The frozen "
                "text's own SHA-256 is preserved as pre_rename_sha256 "
                "(ae86107fb0c760ac1604a0011bf11884186e4d9496ac04fce7472bf327767c12) beside the "
                "post-rename hash, so the pre-registration is still tied to the executed run. The "
                "stages whose numbers were MOVED rather than recomputed are setup, channels, fit, "
                "holdout, independence and build; write, lane, reasoning and card were re-run, and "
                "lane HAD to be re-run because the census grew from 66 to 79 rasters. Full record: "
                "evidence/h95_rename_record.json.")))

    # ---- IR-H95-009  two different footprints ----------------------------------------------------
    st = EVID / "h95_setup.json"
    if st.exists():
        j = json.loads(st.read_text())
        e.append(dict(
            id="IR-H95-009", round="H95", severity="low", detected_utc=FOUND_UTC,
            status="resolved by measurement; the writer fills the difference with 0.0",
            title="The organiser's footprint is 1,533 px larger than the region where all 19 feature bands are finite, and a submission must be finite on both",
            what_it_is=(
                f"labels.tif == -1 on {j['label_values']['-1']:,} px, so the organiser's in-domain "
                f"footprint is {j['in_domain_px']:,} px and sample_submission.tif is finite on exactly "
                f"{j['sample_submission_finite_px']:,} px. The intersection of all 19 feature bands "
                f"being finite is {j['features_all_bands_finite_px']:,} px, a difference of "
                f"{j['footprint_delta_sample_minus_features']:,} px. On those pixels a submission must "
                "still be finite and inside [0,1], but no feature is defined, so no model can score "
                "them."),
            how_we_know=(
                "python scripts/run_h95.py setup, which measures labels.tif value counts, "
                "grid.footprint_from(training_features.tif, bands='all') and the finite mask of "
                "sample_submission.tif; receipt evidence/h95_setup.json"),
            why_it_matters=(
                "A writer that emits NaN wherever features are undefined puts 1,533 NaN inside the "
                "organiser's own footprint, which is a candidate cause of 'Predicted values must be in "
                "range [0, 1]' under a reader that does not honour the nodata tag."),
            handling=(
                "H95 writes the all-finite container: 0.0 outside the feature intersection, including "
                "those 1,533 px, and 0 non-finite pixels anywhere in the grid. The range gate is "
                "re-derived from the bytes on disk after writing, not from the in-memory array.")))
    return e


def main() -> int:
    entries = measure()
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "h95_irregularities.json").write_text(json.dumps(dict(
        round="H95", generated_utc=FOUND_UTC, n_entries=len(entries),
        policy="every entry was re-measured in this session against bytes on disk in this checkout or "
               "against an official page fetched live; none is inherited unverified, and the command "
               "that measured it is recorded in how_we_know",
        entries=entries), indent=1) + "\n")

    reg_path = REG / "irregularities.json"
    reg = json.loads(reg_path.read_text())
    have = {x.get("id") for x in reg["entries"]}
    added = [x for x in entries if x["id"] not in have]
    for x in added:
        # `disposition` is the register's required schema key (tests/test_scripts_and_registry.py);
        # it is derived from `status`, not typed twice.
        x.setdefault("disposition", x["status"])
        x.setdefault("round", "H95")
        x.setdefault("date", FOUND_UTC)
    reg["entries"].extend(added)
    reg["merge_note"] = (reg.get("merge_note", "") +
                         " | H95 merge: IR-H95-001..009 appended from the H95 branch; existing entries "
                         "and numbering untouched.").strip()
    reg_path.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(dict(written="evidence/h95_irregularities.json", n_entries=len(entries),
                          appended_to_register=len(added),
                          ids=[x["id"] for x in entries],
                          already_present=[x["id"] for x in entries if x["id"] in have]), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
