#!/usr/bin/env python3
"""Idempotently publish the parallel H97-RDVA negative archive.

This publisher never changes docs/data/submission.json or either global LATEST pointer. Main acquired an
independent H97 through H102 before this isolated branch integrated, so this run is namespaced H97-RDVA.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = json.loads((ROOT / "evidence/h97_rdva_run_card.json").read_text())
STEM = CARD["unique_submission_name"]
SHA = CARD["raster"]["sha256"]
NOTE = CARD["note"]
START = "<!--H97-RDVA-ARCHIVE-START-->"
END = "<!--H97-RDVA-ARCHIVE-END-->"
DATA_FILES = [
    "h97_rdva_build.json", "h97_rdva_canary.json", "h97_rdva_channels.json",
    "h97_rdva_exchange.json", "h97_rdva_fit.json", "h97_rdva_holdout.json",
    "h97_rdva_lane_dots.json", "h97_rdva_lane_surface.json",
    "h97_rdva_run_card.json", "h97_rdva_uniqueness.json",
]


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def portable(value):
    if isinstance(value, dict):
        return {key: portable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portable(item) for item in value]
    if isinstance(value, str):
        return value.replace(str(ROOT) + "/", "")
    return value


def replace_html_block(path: Path, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    wrapped = START + "\n" + block.strip() + "\n" + END
    if START in text and END in text:
        begin = text.index(START)
        finish = text.index(END, begin) + len(END)
        text = text[:begin] + wrapped + text[finish:]
    else:
        anchor = "</main>"
        if anchor not in text:
            raise ValueError(f"{path}: missing </main> archive insertion anchor")
        text = text.replace(anchor, wrapped + "\n" + anchor, 1)
    path.write_text(text, encoding="utf-8")


def replace_readme_block(block: str) -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    wrapped = START + "\n" + block.strip() + "\n" + END
    if START in text and END in text:
        begin = text.index(START)
        finish = text.index(END, begin) + len(END)
        text = text[:begin] + wrapped + text[finish:]
    else:
        # Preserve the true current round first; insert after its generated README block.
        match = re.search(r"<!--H\d+(?:-[A-Z0-9]+)?-README-->.*?<!--/H\d+(?:-[A-Z0-9]+)?-README-->", text, re.S)
        at = match.end() if match else 0
        text = text[:at] + "\n\n" + wrapped + "\n" + text[at:]
    path.write_text(text, encoding="utf-8")


def publish_files() -> dict:
    submission = ROOT / "submission"
    downloads = ROOT / "docs/downloads"
    data = ROOT / "docs/data"
    tif = submission / f"{STEM}.tif"
    archive = submission / f"{STEM}.zip"
    if hashlib.sha256(tif.read_bytes()).hexdigest() != SHA:
        raise ValueError("canonical H97-RDVA TIFF differs from its run-card SHA-256")
    for src, dest in (
        (tif, downloads / tif.name), (tif, downloads / "h97-rdva-candidate.tif"),
        (archive, downloads / archive.name), (archive, downloads / "h97-rdva-candidate.zip"),
    ):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    for suffix in ("-a-only-reasoning.csv", "-pseudo-segments.csv"):
        src = submission / f"{STEM}{suffix}"
        shutil.copyfile(src, downloads / src.name)
    for name in DATA_FILES:
        shutil.copyfile(ROOT / "evidence" / name, data / name)
    shutil.copyfile(ROOT / "registry/h97_rdva_preregistration.json",
                    data / "h97_rdva_preregistration.json")

    raw = portable(json.loads((ROOT / "evidence" / f"submission_{STEM}.json").read_text()))
    raw.update(round="H97-RDVA", original_frozen_round="H97",
               run_card="evidence/h97_rdva_run_card.json")
    write_json(submission / f"{STEM}.json", raw)
    public = dict(raw)
    public.update(
        stem=STEM, marker="submission/H97_RDVA_LATEST.txt", exists=True,
        download=f"downloads/{STEM}.tif", download_zip=f"downloads/{STEM}.zip",
        submission_note=NOTE, submission_note_chars=len(NOTE),
        published_byte_hash_matches_receipt=True,
    )
    write_json(downloads / f"{STEM}.json", public)
    write_json(data / f"submission_{STEM}.json", public)
    (submission / "H97_RDVA_LATEST.txt").write_text(f"{STEM}.tif\n")
    return public


def main() -> int:
    publication = publish_files()
    style = """<style>.h97rdva{max-width:1040px;margin:20px auto;padding:20px;border:1px solid #3d5275;border-radius:14px;background:#111c2d;color:#edf4ff;font:15px/1.55 system-ui}.h97rdva h2{margin:.1rem 0 .5rem;color:#78dcff}.h97rdva a{color:#78dcff;font-weight:750}.h97rdva code{overflow-wrap:anywhere}.h97rdva .yes{color:#7cedaa;font-weight:850}.h97rdva .no{color:#ff9ca4;font-weight:850}</style>"""
    card = f"""{style}<section class="h97rdva"><h2>Parallel archive · H97-RDVA radiometric-DVA co-training</h2><p>This experiment was frozen as H97 on an isolated branch before main independently acquired H97–H102. It is namespaced H97-RDVA and <strong>does not replace the global current artifact</strong>.</p><p><span class="yes">OK TO DOWNLOAD: YES</span> · <span class="no">OK TO SUBMIT: NO — DO NOT UPLOAD</span> · negative · slots used 0.</p><p>Primary HOLDOUT-DTI 0.185090 [0.164740, 0.205110] did not beat single B 0.186482 or the frozen 0.192829 bar; final-dot lane is DUPLICATE/STOP.</p><p><a href="downloads/h97-rdva-candidate.tif" download>Download research TIFF</a> · <a href="downloads/h97-rdva-candidate.zip" download>ZIP</a> · <a href="h97-rdva.html">full evidence</a> · <a href="h97-rdva-executive-summary.html">submission warning/instructions</a></p><small><code>{STEM}.tif</code> · SHA-256 <code>{SHA}</code></small></section>"""
    replace_html_block(ROOT / "docs/index.html", card)
    replace_html_block(ROOT / "docs/executive-summary.html", card)
    replace_html_block(ROOT / "docs/irregularities.html", card)
    downloads_card = card.replace('href="downloads/', 'href="').replace('href="h97-rdva', 'href="../h97-rdva')
    replace_html_block(ROOT / "docs/downloads/index.html", downloads_card)
    root_card = card.replace('href="downloads/', 'href="docs/downloads/').replace('href="h97-rdva', 'href="docs/h97-rdva')
    replace_html_block(ROOT / "index.html", root_card)
    readme = f"""## Parallel negative archive — H97-RDVA

This experiment was frozen/executed as H97 on an isolated branch before `main` independently acquired H97–H102. It is namespaced **H97-RDVA** and does **not** replace the global current pointer.

**OK TO DOWNLOAD: YES (research/audit). OK TO SUBMIT: NO — DO NOT UPLOAD. Slots used: 0.**

[Download TIFF](docs/downloads/h97-rdva-candidate.tif) · [ZIP](docs/downloads/h97-rdva-candidate.zip) · [full evidence](docs/h97-rdva.html) · [run card](evidence/h97_rdva_run_card.json)

`{STEM}.tif` · SHA-256 `{SHA}` · primary HOLDOUT-DTI 0.185090 [0.164740, 0.205110], below single B 0.186482 and the 0.192829 bar; final-dot lane DUPLICATE/STOP.
"""
    replace_readme_block(readme)
    print(f"published H97-RDVA archive without changing current {publication['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
