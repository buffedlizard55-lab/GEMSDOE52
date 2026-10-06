#!/usr/bin/env python3
"""Build the (H, W, F) float32 feature stack used by the holdout harness."""
import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems52 import features  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default="/tmp/gems52/data/training_features.tif")
    ap.add_argument("--out", default="/tmp/gems52/work/feature_stack.npy")
    ap.add_argument("--receipt", default="registry/feature_receipt.json")
    a = ap.parse_args()
    t0 = time.time()
    rec = features.build(a.features, a.out)
    rec["seconds"] = round(time.time() - t0, 1)
    Path(a.receipt).parent.mkdir(parents=True, exist_ok=True)
    Path(a.receipt).write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: v for k, v in rec.items() if k != "channels"}, indent=1))


if __name__ == "__main__":
    main()
