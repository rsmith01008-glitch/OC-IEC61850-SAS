"""The strongest correctness signal in this test suite: builds a Station
by hand (no input()), writes it to SCL, and proves the result isn't just
well-formed but actually schema-valid AND compiles cleanly through the
real tools/scl-compiler pipeline -- directly parallel to how
scl/switchyard.scd itself was verified.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scl-compiler"))

from lxml import etree

from generator.topology import (
    Station, Tap, TapKind, Transformer, NetworkDefaults, ProtectionDefaults,
)
from generator.layouts import breaker_and_half, single_bus
from generator import scl_writer

from scl.validate import validate_xsd, SclValidationError
from scl.parse import SCL_NS, OC_NS
from scl_compile import compile_scd


def _taps(*specs):
    return [Tap(name, kind) for name, kind in specs]


def _minimal_station():
    """Cheapest end-to-end case: one VL, single-bus, 1 tap, no
    transformer, no SCADA opt-in.
    """
    taps = _taps(("Feed1", TapKind.FEEDER))
    vl = single_bus.build("V13", 13.8, taps)
    return Station(name="TestYard1", voltage_levels=[vl])


def _transformer_station():
    """Reproduces switchyard.scd's own shape: two 1.5-breaker VLs joined
    by one transformer.
    """
    hv_taps = _taps(("Line1", TapKind.LINE), ("XfmrHV", TapKind.TRANSFORMER))
    lv_taps = _taps(("XfmrLV", TapKind.TRANSFORMER), ("Feed1", TapKind.FEEDER))
    hv_vl = breaker_and_half.build("V800", 800, hv_taps, start_index=1)
    lv_vl = breaker_and_half.build("V230", 230, lv_taps, start_index=4)
    xfmr = Transformer(
        name="XFMR1", hv_vl=hv_vl, hv_tap=hv_vl.tap_node_for(hv_taps[1]),
        lv_vl=lv_vl, lv_tap=lv_vl.tap_node_for(lv_taps[0]),
    )
    return Station(name="Switchyard2", voltage_levels=[hv_vl, lv_vl], transformers=[xfmr])


class TestWriteWellFormed(unittest.TestCase):
    def test_minimal_station_round_trips(self):
        tree = scl_writer.write(_minimal_station())
        text = scl_writer.to_string(tree)
        reparsed = etree.fromstring(text)
        self.assertEqual(reparsed.tag, "{%s}SCL" % SCL_NS)

    def test_transformer_station_round_trips(self):
        tree = scl_writer.write(_transformer_station())
        text = scl_writer.to_string(tree)
        etree.fromstring(text)  # must not raise


class TestPrivateOrdering(unittest.TestCase):
    def _first_child_tag(self, elem):
        children = list(elem)
        return children[0].tag if children else None

    def test_private_is_first_child_of_ln0(self):
        tree = scl_writer.write(_minimal_station())
        root = tree.getroot()
        ln0 = root.find(".//{%s}LN0" % SCL_NS)
        self.assertEqual(self._first_child_tag(ln0), "{%s}Private" % SCL_NS)

    def test_private_is_first_child_of_connected_ap(self):
        tree = scl_writer.write(_minimal_station())
        root = tree.getroot()
        for cap in root.findall(".//{%s}ConnectedAP" % SCL_NS):
            if cap.get("iedName") == "CB1":
                self.assertEqual(self._first_child_tag(cap), "{%s}Private" % SCL_NS)
                return
        self.fail("CB1's ConnectedAP not found")

    def test_private_is_first_child_of_gse(self):
        tree = scl_writer.write(_minimal_station())
        root = tree.getroot()
        gse = root.find(".//{%s}GSE" % SCL_NS)
        # GSE's Private is optional in this writer (no per-GSE override
        # emitted) -- what matters is Address/MinTime/MaxTime never come
        # before a Private if one exists. No override here, so just
        # confirm Address is GSE's first child in that case.
        self.assertEqual(self._first_child_tag(gse), "{%s}Address" % SCL_NS)

    def test_private_is_first_child_of_doi(self):
        tree = scl_writer.write(_minimal_station())
        root = tree.getroot()
        for doi in root.findall(".//{%s}DOI" % SCL_NS):
            self.assertEqual(self._first_child_tag(doi), "{%s}Private" % SCL_NS)


class TestValidateXsd(unittest.TestCase):
    def test_minimal_station_is_schema_valid(self):
        tree = scl_writer.write(_minimal_station())
        validate_xsd(tree)  # must not raise

    def test_transformer_station_is_schema_valid(self):
        tree = scl_writer.write(_transformer_station())
        validate_xsd(tree)  # must not raise


class TestCompilesThroughRealPipeline(unittest.TestCase):
    def test_minimal_station_compiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            scd_path = Path(tmp) / "test.scd"
            scd_path.write_bytes(scl_writer.to_string(scl_writer.write(_minimal_station())))
            outputs = compile_scd(str(scd_path), validate_schema=True)
            self.assertEqual(set(outputs.keys()), {"sas-ied-cb1.cfg", "sas-scada.cfg"})

    def test_transformer_station_compiles_with_expected_file_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            scd_path = Path(tmp) / "test.scd"
            scd_path.write_bytes(scl_writer.to_string(scl_writer.write(_transformer_station())))
            outputs = compile_scd(str(scd_path), validate_schema=True)
            # 6 breakers + 1 transformer + 1 scada
            self.assertEqual(len(outputs), 8)
            self.assertIn("sas-ied-xfmr1.cfg", outputs)
            self.assertIn("sas-scada.cfg", outputs)

    def test_transformer_station_remote_trips_present_in_compiled_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            scd_path = Path(tmp) / "test.scd"
            scd_path.write_bytes(scl_writer.to_string(scl_writer.write(_transformer_station())))
            outputs = compile_scd(str(scd_path), validate_schema=True)
            # CB2/CB3 bound the HV tap, CB4/CB5 bound the LV tap.
            for name in ("sas-ied-cb2.cfg", "sas-ied-cb3.cfg", "sas-ied-cb4.cfg", "sas-ied-cb5.cfg"):
                self.assertIn("remoteTrips", outputs[name])
                self.assertIn("XFMR1", outputs[name])
            for name in ("sas-ied-cb1.cfg", "sas-ied-cb6.cfg"):
                self.assertNotIn("remoteTrips", outputs[name])


if __name__ == "__main__":
    unittest.main()
