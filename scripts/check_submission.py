"""Validate a submission GeoTIFF against the competition template."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gemsdoe32.submission import validate_submission_geotiff


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geotiff", type=Path, help="Path to submission GeoTIFF to validate")
    parser.add_argument("--template", type=Path, default=Path("data/raw/sample_submission.tif"), help="Path to reference template")
    parser.add_argument("--strict-finite", action="store_true", help="Check whole-array finite range [0, 1] for portal safety")
    args = parser.parse_args()

    if not args.geotiff.is_file():
        print(f"Error: {args.geotiff} does not exist", file=sys.stderr)
        return 1
    if not args.template.is_file():
        print(f"Error: {args.template} does not exist", file=sys.stderr)
        return 1

    report = validate_submission_geotiff(
        args.geotiff,
        args.template,
        strict_whole_array_finite=args.strict_finite,
    )

    print(json.dumps(report.to_dict(), indent=2))
    if report.passed:
        print(f"\n[PASSED] {args.geotiff.name} is fully valid and ready for submission!")
        return 0
    else:
        print(f"\n[FAILED] {args.geotiff.name} failed one or more validation checks.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
