#!/usr/bin/env python3
"""Interactive SCL generator CLI: walks the user through substation
layout/bay/voltage questions and writes an IEC 61850-6 `.scd` file plus a
one-line diagram SVG. See tools/scl-generator/README.md for the full
workflow; see tools/scl-compiler/README.md for what happens to the `.scd`
this produces (it does not run on OC hardware either).

Usage:
    python3 tools/scl-generator/scl_generate.py [--out-dir scl/]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir", default="scl",
        help="Directory to write the generated .scd and .svg into (default: scl/)",
    )
    args = parser.parse_args(argv)

    from generator.wizard import run_wizard
    from generator.output import write_station

    station = run_wizard()
    return write_station(station, Path(args.out_dir))


if __name__ == "__main__":
    sys.exit(main())
