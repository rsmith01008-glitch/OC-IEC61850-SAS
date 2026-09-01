"""XSD validation against the vendored SCL2007B4 schema."""

from pathlib import Path
from lxml import etree

DEFAULT_SCHEMA_ROOT = Path(__file__).resolve().parent.parent / "schema" / "SCL.xsd"


class SclValidationError(Exception):
    pass


def validate_xsd(tree, schema_path=DEFAULT_SCHEMA_ROOT):
    """Raises SclValidationError with every schema violation listed if
    `tree` (an lxml ElementTree, already parsed from the .scd file) does
    not conform to SCL.xsd. Our own Private extension content is opaque to
    the base SCL schema (Private is xs:any-open), so this only checks the
    real SCL structure -- it does NOT validate oc:* content.
    """
    schema_doc = etree.parse(str(schema_path))
    schema = etree.XMLSchema(schema_doc)
    if not schema.validate(tree):
        errors = "\n".join(
            "  line %d: %s" % (e.line, e.message) for e in schema.error_log
        )
        raise SclValidationError("SCL document is not schema-valid:\n%s" % errors)
