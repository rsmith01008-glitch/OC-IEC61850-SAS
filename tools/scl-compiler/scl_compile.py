#!/usr/bin/env python3
"""SCL -> sas-ied.cfg/sas-scada.cfg compiler CLI.

Usage:
    python3 tools/scl-compiler/scl_compile.py \\
        --scd scl/switchyard.scd --out-dir etc/generated/ \\
        [--validate-xsd] [--check]

See tools/scl-compiler/README.md for the full workflow.
"""

import argparse
import difflib
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scl.parse import parse_file, root
from scl.mapping import map_document, MappingError
from scl.codegen import encode_top_level
from scl.validate import validate_xsd, SclValidationError, DEFAULT_SCHEMA_ROOT

GENERATED_HEADER = (
    "GENERATED FILE -- DO NOT HAND-EDIT.\n"
    "Compiled from {scd} by tools/scl-compiler/scl_compile.py.\n"
    "Edit the SCL source and re-run the compiler instead -- see\n"
    "tools/scl-compiler/README.md.\n"
)


def _out_filename(ied_name, role):
    if role == "scada":
        return "sas-scada.cfg"
    return "sas-ied-%s.cfg" % ied_name.lower()


def compile_scd(scd_path, validate_schema=False, schema_path=DEFAULT_SCHEMA_ROOT):
    """Parses+maps `scd_path`, returns {filename: file_text}."""
    tree = parse_file(scd_path)
    if validate_schema:
        validate_xsd(tree, schema_path)

    mapped = map_document(root(tree))

    out = {}
    for ied_name, entry in mapped.items():
        filename = _out_filename(ied_name, entry["role"])
        header = GENERATED_HEADER.format(scd=Path(scd_path).name)
        out[filename] = encode_top_level(entry["cfg"], header_comment=header)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scd", required=True, help="Path to the SCL .scd source file")
    parser.add_argument("--out-dir", required=True, help="Directory to write generated .cfg files into")
    parser.add_argument("--validate-xsd", action="store_true", help="XSD-validate the .scd against the vendored schema first")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_ROOT), help="Override the vendored schema path")
    parser.add_argument("--check", action="store_true", help="Compile to a temp dir and diff against --out-dir instead of writing (CI mode); nonzero exit on any diff")
    args = parser.parse_args(argv)

    try:
        outputs = compile_scd(args.scd, validate_schema=args.validate_xsd, schema_path=args.schema)
    except (MappingError, SclValidationError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)

    if args.check:
        ok = True
        for filename, text in outputs.items():
            existing_path = out_dir / filename
            existing = existing_path.read_text() if existing_path.exists() else ""
            if existing != text:
                ok = False
                print("--- %s (checked in)\n+++ %s (freshly compiled)" % (existing_path, existing_path))
                diff = difflib.unified_diff(existing.splitlines(True), text.splitlines(True))
                sys.stdout.writelines(diff)
        existing_files = {p.name for p in out_dir.glob("*.cfg")} if out_dir.exists() else set()
        stale = existing_files - set(outputs.keys())
        for filename in stale:
            ok = False
            print("stale generated file with no matching IED: %s" % (out_dir / filename))
        if not ok:
            print("\nGenerated output is out of date -- run without --check to regenerate.", file=sys.stderr)
            return 1
        print("OK: %d generated file(s) match %s" % (len(outputs), args.scd))
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in outputs.items():
        (out_dir / filename).write_text(text)
        print("wrote %s" % (out_dir / filename))
    return 0


if __name__ == "__main__":
    sys.exit(main())
