#!/usr/bin/env python3
"""Compatibility entry point for the byte-frozen H97-RDVA preregistration.

The isolated branch registered ``scripts/run_h97.py`` before main independently acquired another H97.
The implementation now lives at ``run_h97_rdva.py`` to avoid namespace collisions; behavior is unchanged.
"""
from run_h97_rdva import main


if __name__ == "__main__":
    raise SystemExit(main())
