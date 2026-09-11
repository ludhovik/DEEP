"""Independent Fortran-record fixtures for archived MagIC shells."""
import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import convert_magic_to_viewer as converter
from tools.magic_graph_compat import read_v9_shell_without_ic
from tools.viewer_bundle import validate_bundle
from tools import conversion_cache as cache


def fixture(endian="<", word=4, minc=1, blocks=1, nr_ic=16):
    """Encode canonical asymmetric fields into legacy alternating hemispheres."""
    nr, nt, full_phi = 3, 8, 16
    nphi = full_phi // minc
    dt = np.dtype(endian + ("f4" if word == 4 else "f8"))
    radius = np.array([1.0, .6, .2], dtype=dt)
    theta = np.arccos(np.polynomial.legendre.leggauss(nt)[0][::-1]).astype(dt)
    arrays = {}
    for k, name in enumerate(("entropy", "vr", "vtheta", "vphi", "Br", "Btheta", "Bphi")):
        p, t, r = np.indices((nphi, nt, nr))
        arrays[name] = (k + p * .03125 + t * .125 + r * .5).astype(dt)
    stream = io.BytesIO()
    offsets = []
    def record(data):
        offsets.append(stream.tell())
        marker = struct.pack(endian + "i", len(data))
        stream.write(marker + data + marker)
    def nums(data):
        return np.asarray(data, dtype=dt).tobytes()
    record(b"Graphout_Version_9".ljust(20))
    record(b"independent asymmetric fixture".ljust(64))
    record(nums([18.5, nr, nt, full_phi, nr_ic, minc, blocks,
                 6e7, 1e-4, .1, 2, .2, 1]))
    record(nums(theta))
    # Assign geographic north/south rows into the stored interleaving.
    stored = {}
    for name, a in arrays.items():
        b = np.empty_like(a)
        for t in range(nt // 2):
            b[:, 2*t, :] = a[:, t, :]
            b[:, 2*t+1, :] = a[:, nt-1-t, :]
        stored[name] = b
    for r in range(nr):
        for b in range(blocks):
            lo, hi = b * nt // blocks, (b+1) * nt // blocks
            record(nums([r, radius[r], lo+1, hi]))
            for a in stored.values():
                record(nums(a[:, lo:hi, r].T))
    return stream.getvalue(), arrays, radius, theta, offsets


class MagicArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "G_a60.example"

    def read(self, payload, dtype=np.float32):
        self.path.write_bytes(payload)
        with warnings.catch_warnings(record=True) as messages:
            warnings.simplefilter("always")
            graph = read_v9_shell_without_ic(self.path, dtype)
        return graph, messages

    def test_fields_coordinates_symmetry_precision_and_byte_order(self):
        for endian in ("<", ">"):
            for word in (4, 8):
                for minc in (1, 2):
                    for blocks in (1, 2):
                        with self.subTest(endian=endian, word=word, minc=minc, blocks=blocks):
                            payload, expected, radius, theta, _ = fixture(endian, word, minc, blocks)
                            dtype = np.float32 if word == 4 else np.float64
                            graph, messages = self.read(payload, dtype)
                            self.assertEqual(len(messages), 1)
                            self.assertEqual(graph.sigma, 1)
                            self.assertFalse(hasattr(graph, "Br_ic"))
                            self.assertEqual(graph.deepscope_reader_metadata["declared_inner_radial_points"], 16)
                            for name, values in expected.items():
                                np.testing.assert_array_equal(getattr(graph, name), values)
                            np.testing.assert_array_equal(graph.colatitude, theta)
                            np.testing.assert_allclose(graph.radius, radius / (1-float(dtype(.2))))
                            adapted = converter.adapt_graph(graph)
                            self.assertTrue(adapted["has_conducting_inner_core"])
                            self.assertFalse(adapted["magnetic_extends_inner_core"])
                            wanted = np.tile(expected["Br"][:, :, ::-1].transpose(2, 1, 0), (1, 1, minc))
                            np.testing.assert_array_equal(adapted["fields"]["Br"], wanted)

    def test_truncated_shell_and_partial_ic_are_never_accepted(self):
        payload, *_ = fixture()
        for data in (payload[:-1], payload[:-100], payload + b"partial IC"):
            graph, messages = self.read(data)
            self.assertIsNone(graph)
            self.assertFalse(messages)

    def test_same_size_corruption_and_duplicate_coverage_rejected(self):
        payload, _, _, _, offsets = fixture(blocks=2)
        bad_marker = bytearray(payload)
        bad_marker[-1] ^= 1
        bad_coverage = bytearray(payload)
        # Give the second theta block exactly the first block's bounds.
        offset = offsets[12] + 4
        bad_coverage[offset:offset+16] = payload[offsets[4]+4:offsets[4]+20]
        bad_field = bytearray(payload)
        bad_field[offsets[5]+4:offsets[5]+8] = struct.pack("<f", float("nan"))
        for data in (bad_marker, bad_coverage, bad_field):
            with self.assertRaises(ValueError):
                self.read(data)

    def test_precision_mismatch_explained_before_field_allocations(self):
        with self.assertRaisesRegex(ValueError, "--precision float64"):
            self.read(fixture(word=8)[0])

    def test_other_formats_and_normal_graphs_use_official_reader(self):
        for payload in (b"modern stream header", fixture(nr_ic=2)[0], fixture()[0]+b"IC records"):
            self.path.write_bytes(payload)
            fake = mock.Mock(radius=[1, .2], colatitude=[.2, 2.8], vr=[], vtheta=[], vphi=[])
            factory = mock.Mock(return_value=fake)
            with mock.patch.object(converter, "import_magic_graph", return_value=factory):
                self.assertIs(converter.load_graph(self.path, None, "float32"), fake)
            self.assertEqual(factory.call_args.kwargs["ivar"], "a60")
            self.assertFalse(factory.call_args.kwargs["ave"])

    def test_archived_name_does_not_change_numeric_sequence_selection(self):
        self.path.write_bytes(b"archive")
        for name in ("G_1.example", "G_60.example", "G_ave.example"):
            self.path.with_name(name).write_bytes(b"regular")
        self.assertEqual(converter.parse_graph_filename(self.path), ("a60", "example", False))
        selected = converter.discover_graph(self.path.parent, "example", None, False)
        self.assertEqual(selected.name, "G_60.example")
        self.assertEqual(converter.parse_graph_filename(self.path.with_name("G_ave.example")), (None, "example", True))

    def test_bundle_provenance_and_incremental_reader_reuse(self):
        self.path.write_bytes(fixture()[0])
        original = self.path.read_bytes()
        out = Path(self.tmp.name) / "output"
        args = converter.build_arg_parser().parse_args([
            "--graph", str(self.path), "--out", str(out), "--incremental",
            "--skip-field-lines", "--no-earth-br", "--no-gradients", "--no-m0-fields",
        ])
        # Exercise real read_graph_data caching without requiring external MagIC.
        calc = cache.CalculationCache(Path(self.tmp.name)/"cache", "fixture")
        token = cache._active_cache.set(calc)
        try:
            with mock.patch.object(converter, "import_magic_graph", side_effect=AssertionError("must not modify or call MagIC")):
                with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
                    warnings.simplefilter("ignore")
                    a, _ = converter.read_graph_data(self.path, None, "float32")
                    b, _ = converter.read_graph_data(self.path, None, "float32")
                self.assertEqual(calc.hits, 1)
                np.testing.assert_array_equal(a["fields"]["Br"], b["fields"]["Br"])
                with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
                    warnings.simplefilter("ignore")
                    converter.convert_graph(self.path, out, args)
        finally:
            cache._active_cache.reset(token)
        validate_bundle(out)
        meta = json.loads((out/"metadata.json").read_text())
        self.assertEqual(meta["source_reader"]["sigma"], 1)
        self.assertEqual(meta["source_reader"]["inner_core_records"], "absent")
        self.assertTrue(meta["has_conducting_inner_core"])
        self.assertFalse(meta["inner_core"]["available"])
        self.assertFalse(meta["magnetic"]["extends_into_inner_core"])
        self.assertEqual(meta["r_inner"], meta["r_icb"])
        self.assertIn("T", meta["fields"])
        self.assertNotIn("C", meta["fields"])
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
