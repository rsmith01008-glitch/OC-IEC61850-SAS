"""Writes a Station's .scd + one-line-diagram .svg to disk, XSD-validates
the .scd (reusing tools/scl-compiler/scl/validate.py directly), prints a
summary, and offers to compile it immediately via the real
tools/scl-compiler/scl_compile.py -- closing the loop from "answered some
questions" to "here's a compiled sas-ied.cfg/sas-scada.cfg" in one run.
"""

import sys
from pathlib import Path

from . import naming, prompts, scl_writer
from .diagram import onelinediagram
from .topology import Station

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scl-compiler"))


def _confirm_overwrite(path: Path) -> bool:
    if not path.exists():
        return True
    return prompts.ask_yes_no("%s already exists -- overwrite it?" % path, default=False)


def write_station(station: Station, out_dir: Path) -> int:
    """Returns a process exit code (0 = success)."""
    if station is None:
        print("Aborted -- nothing generated.")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    base = naming.sanitize_identifier(station.name).lower()
    scd_path = out_dir / ("%s.scd" % base)
    svg_path = out_dir / ("%s-oneline.svg" % base)

    for path in (scd_path, svg_path):
        if not _confirm_overwrite(path):
            print("Aborted -- not overwriting %s" % path)
            return 1

    tree = scl_writer.write(station)
    scd_path.write_bytes(scl_writer.to_string(tree))
    print("wrote %s" % scd_path)

    svg_path.write_text(onelinediagram.render(station))
    print("wrote %s" % svg_path)

    from scl.validate import validate_xsd, SclValidationError
    try:
        validate_xsd(tree)
        print("XSD validation: OK")
    except SclValidationError as e:
        print("XSD validation FAILED:\n%s" % e)
        print("(the .scd/.svg were still written -- fix the wizard's inputs and re-run, "
              "or hand-edit the .scd; see tools/scl-compiler/README.md)")
        return 1

    if prompts.ask_yes_no("\nCompile now via tools/scl-compiler?", default=True):
        from scl_compile import compile_scd
        compiled_dir = Path(prompts.ask_str("Compile output directory", default="etc/generated"))
        compiled_dir.mkdir(parents=True, exist_ok=True)
        outputs = compile_scd(str(scd_path), validate_schema=True)
        for filename, text in outputs.items():
            (compiled_dir / filename).write_text(text)
            print("wrote %s" % (compiled_dir / filename))

    return 0
