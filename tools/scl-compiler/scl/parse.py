"""XML parsing helpers: namespace-qualified element lookup, plus finding
this project's `Private` extension blocks.

Real SCL is namespaced (xmlns="http://www.iec.ch/61850/2003/SCL"); every
tag lookup in this compiler goes through `q()` rather than bare string
tags so it works regardless of prefix choice in the authored .scd file.
"""

from lxml import etree

SCL_NS = "http://www.iec.ch/61850/2003/SCL"
OC_NS = "urn:oc-iec61850-sas:v1"
OC_PRIVATE_TYPE = "oc-iec61850-sas"

_NSMAP = {"scl": SCL_NS, "oc": OC_NS}


def q(tag):
    """Qualify a bare local tag name with the SCL namespace, e.g. q("IED") -> "{ns}IED"."""
    return "{%s}%s" % (SCL_NS, tag)


def oc_q(tag):
    """Qualify a bare local tag name with our Private extension namespace."""
    return "{%s}%s" % (OC_NS, tag)


def parse_file(path):
    parser = etree.XMLParser(remove_blank_text=False)
    return etree.parse(str(path), parser)


def root(tree):
    return tree.getroot()


def children(elem, tag):
    """All direct children of `elem` named `tag` (SCL namespace)."""
    return elem.findall(q(tag))


def child(elem, tag):
    """First direct child of `elem` named `tag` (SCL namespace), or None."""
    return elem.find(q(tag))


def find_all(elem, tag):
    """All descendants of `elem` named `tag` (SCL namespace), any depth."""
    return elem.findall(".//" + q(tag))


def find_private(elem, type_=OC_PRIVATE_TYPE):
    """The first direct-child `<Private type="...">` of `elem` matching
    `type_`, or None. Real SCL allows multiple `Private` children (one per
    vendor namespace) -- we only ever look for our own.
    """
    for p in children(elem, "Private"):
        if p.get("type") == type_:
            return p
    return None
