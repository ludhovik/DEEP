"""Reuse must agree with fresh calculations, including native precision and pairing."""
import argparse
from contextlib import contextmanager, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import conversion_cache as cc
import test_converter_package as fixtures


@contextmanager
def active(cache):
    token = cc._active_cache.set(cache)
    try:
        yield cache
    finally:
        cc._active_cache.reset(token)


@cc.cached_calculation
def square(values, scale=1.0):
    return scale * values**2


class IncrementalTests(unittest.TestCase):
    def test_sequence_extension_reuses_frames_and_preserves_root_and_frame_views(self):
        magic = fixtures.load_module("incremental_magic_sequence_test", fixtures.MAGIC_PATH)
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder); inputs = root / "inputs"; inputs.mkdir()
            for number in (1, 2, 3): (inputs / f"G_{number}.test").touch()
            cli = ["--folder", str(inputs), "--out", str(root / "out"), "--tag", "test", "--incremental",
                   "--sequence-first", "1", "--sequence-last", "2"]
            def convert(path, output, args):
                fixtures.ConverterPackageTests.minimal_bundle(output)
                meta_path = output / "metadata.json"
                metadata = json.loads(meta_path.read_text()); metadata["time"] = float(path.name.split(".")[0][2:])
                meta_path.write_text(json.dumps(metadata)); return metadata
            with mock.patch.object(magic, "import_magic_graph"), \
                 mock.patch.object(magic, "convert_graph", side_effect=convert) as conversion:
                with mock.patch.object(sys, "argv", ["converter"] + cli): magic.main()
                (root / "out" / "view.DTV2").write_text("root view")
                frame_view = root / "out" / "frames" / "G_00001" / "view.DTV2"
                frame_view.write_text("frame view")
                cli[-1] = "3"
                with mock.patch.object(sys, "argv", ["converter"] + cli): magic.main()
                self.assertEqual(conversion.call_count, 3, "only the new third frame is converted")
                self.assertEqual((root / "out" / "view.DTV2").read_text(), "root view")
                self.assertEqual(frame_view.read_text(), "frame view")
                index = json.loads((root / "out" / "sequence.json").read_text())
                self.assertEqual(len(index["frames"]), 3)

    def test_lossless_reuse_and_copy_on_write(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            values = np.array([1 + 1e-12, 2 + 3e-12], dtype=np.float64)
            with active(cc.CalculationCache(folder, "source")) as cache:
                expected = square(values)
                result = square(values)
                self.assertEqual(result.dtype, np.dtype("float64"))
                np.testing.assert_array_equal(result, expected)
                self.assertFalse(np.array_equal(result, expected.astype("float32")))
                result[0] = 999
                np.testing.assert_array_equal(square(values), expected)
                self.assertEqual((cache.hits, cache.misses), (2, 1))
                np.testing.assert_array_equal(square(values, 2), 2 * expected)
                changed = values.copy(); changed[0] += 1e-12
                np.testing.assert_array_equal(square(changed), changed**2)
                self.assertEqual(cache.misses, 3)

    def test_damaged_native_array_is_recomputed(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            with active(cc.CalculationCache(folder, "source")) as cache:
                square(np.arange(4.0))
                array_path = next(Path(folder).rglob("*.npy"))
                with array_path.open("r+b") as stream:
                    stream.seek(-8, 2); stream.write(b"12345678")
                np.testing.assert_array_equal(square(np.arange(4.0)), np.arange(4.0)**2)
                self.assertEqual(cache.misses, 2)

    def test_changed_algorithm_and_source_do_not_reuse(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            c = cc.CalculationCache(folder, "source1")
            self.assertEqual(c.call("f", lambda: 1, {}, "v1"), 1)
            self.assertEqual(c.call("f", lambda: 2, {}, "v2"), 2)
            c = cc.CalculationCache(folder, "source2")
            self.assertEqual(c.call("f", lambda: 3, {}, "v2"), 3)
            c = cc.CalculationCache(folder, "source2", force=True)
            self.assertEqual(c.call("f", lambda: 4, {}, "v2"), 4)

    def test_complete_skip_and_corrupt_output_repair(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "state"; source.write_bytes(b"a")
            args = argparse.Namespace(out=str(root / "out"), incremental=True, cache_dir=None, force=False)
            def convert(opts):
                fixtures.ConverterPackageTests.minimal_bundle(Path(opts.out), 2)
            convert = mock.Mock(side_effect=convert)
            cc.run_conversion(args, "test", [source], convert)
            view = root / "out" / "view.DTV2"; view.write_text("preserve this view")
            cc.run_conversion(args, "test", [source], convert)
            self.assertEqual(convert.call_count, 1)
            (root / "out" / "C_volume.f32").write_bytes(b"bad")
            cc.run_conversion(args, "test", [source], convert)
            self.assertEqual(convert.call_count, 2)
            self.assertEqual(view.read_text(), "preserve this view")
            source.write_bytes(b"b")
            cc.run_conversion(args, "test", [source], convert)
            self.assertEqual(convert.call_count, 3)
            args.force = True
            cc.run_conversion(args, "test", [source], convert)
            self.assertEqual(convert.call_count, 4)

    def test_failed_reconversion_keeps_previous_bundle_and_view(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder)
            source = root / "state"; source.touch()
            out = root / "out"
            fixtures.ConverterPackageTests.minimal_bundle(out, 1)
            (out / "view.DTV2").write_text("saved view")
            args = argparse.Namespace(out=str(out), incremental=True, cache_dir=None, force=False)
            def fail(opts):
                fixtures.ConverterPackageTests.minimal_bundle(Path(opts.out), 2)
                raise RuntimeError("conversion failed")
            with self.assertRaisesRegex(RuntimeError, "conversion failed"):
                cc.run_conversion(args, "test", [source], fail)
            np.testing.assert_array_equal(np.fromfile(out / "C_volume.f32", dtype="<f4"), np.ones(8))
            self.assertEqual((out / "view.DTV2").read_text(), "saved view")

    def test_cache_stays_outside_published_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / ".git").mkdir()
            out = root / "public" / "data"
            self.assertEqual(cc.cache_directory(out), root / ".deepscope-cache")
            for bad in (out / "cache", root / "public" / "cache"):
                with self.assertRaises(ValueError):
                    cc.cache_directory(out, bad)

    def test_real_line_tracing_cache_restores_statuses_and_return_pairing(self):
        from tools import convert_leeds_to_viewer as leeds
        r = np.linspace(0.35, 1, 12)
        theta = np.linspace(0.05, np.pi - 0.05, 24)
        phi = np.linspace(0, 2*np.pi, 32, endpoint=False)
        b = fixtures.ConverterPackageTests.dipole_grid(r, theta, phi)
        re = np.geomspace(1, 8, 32)
        be = fixtures.ConverterPackageTests.dipole_grid(re, theta, phi)
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            with active(cc.CalculationCache(folder, "dipole")) as cache:
                def lines():
                    shell = leeds.compute_shell_field_lines_from_cmb(*b, r, theta, phi,
                        ntheta_seed=4, nphi_seed=3, max_steps=800, step_size=0.015, seed_offset=0.025)
                    arcs = leeds.compute_external_field_lines_from_cmb(*be, re, theta, phi,
                        ntheta_seed=4, nphi_seed=3, max_steps=800, step_size=0.015, seed_records=shell)
                    extra, counts = leeds.connect_exterior_return_footpoints(shell, arcs, *b, r, theta, phi, 0.015, 800)
                    return shell, arcs, extra, counts, leeds.compute_external_field_lines_from_cmb.last_status_counts
                expected = lines()
                leeds.compute_external_field_lines_from_cmb.last_status_counts = {"wrong": 99}
                actual = lines()
                self.assertEqual(actual, expected)
                self.assertEqual(cache.hits, 3)
                self.assertGreater(len(actual[1]), 0)
                for arc in actual[1]:
                    if arc.get("return_connection_status") == "connected":
                        self.assertIn("paired_shell_return_line_id", arc)

    def test_magic_added_diagnostic_reuses_native_data_and_matches_fresh_output(self):
        magic = fixtures.load_module("incremental_magic_test", fixtures.MAGIC_PATH)
        graph = fixtures.ConverterPackageTests.fake_magic_graph()
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder); source = root / "G_1.test"; source.touch()
            args = magic.build_arg_parser().parse_args(["--graph", str(source), "--out", str(root / "out"),
                "--incremental", "--skip-field-lines", "--no-earth-br", "--downsample-theta", "2"])
            def convert(opts):
                return magic.convert_graph(source, Path(opts.out), opts)
            with mock.patch.object(magic, "load_graph", return_value=graph) as reader:
                cc.run_conversion(args, "magic", [source], convert)
                args.emf = args.induction = True
                cc.run_conversion(args, "magic", [source], convert)
                self.assertEqual(reader.call_count, 1, "new diagnostics reuse the original graphic arrays")
                args.out = str(root / "fresh"); args.incremental = False
                cc.run_conversion(args, "magic", [source], convert)
                for path in (root / "fresh").glob("*.f32"):
                    self.assertEqual(path.read_bytes(), (root / "out" / path.name).read_bytes(), path.name)
                self.assertTrue((root / "out" / "Ir_volume.f32").exists())
                self.assertEqual(json.loads((root / "fresh" / "metadata.json").read_text()),
                                 json.loads((root / "out" / "metadata.json").read_text()))

    def test_leeds_added_diagnostic_reuses_transforms_and_matches_fresh_output(self):
        from tools import convert_leeds_to_viewer as leeds
        graph = fixtures.ConverterPackageTests.fake_magic_graph()
        r = graph.radius[::-1].copy(); theta = graph.colatitude
        phi = np.linspace(0, 2*np.pi, graph.vr.shape[0], endpoint=False)
        spatial = tuple(np.transpose(v[:, :, ::-1], (2, 1, 0)).copy() for v in (graph.vr, graph.vtheta, graph.vphi))
        coefficients = np.ones((2, 6, len(r)))
        transform_spy = mock.Mock()
        reader_spy = mock.Mock()
        backend = types.ModuleType("modules")
        backend.__file__ = __file__
        def load_state(path):
            reader_spy()
            return {"uP": coefficients, "uT": coefficients * 0.1, "BP": coefficients * 2,
                    "BT": coefficients * 0.2, "C": coefficients * 0.3, "Comp": coefficients * 0.4,
                    "r": r, "lmax": 2, "mmax": 2, "t": 1.25}
        def vector_transform(pol, tor, radius, lmax, mmax, alpha_map=-1):
            transform_spy()
            return *(v * pol[0, 0, 0] for v in spatial), theta, phi
        def scalar_transform(coeff, lmax, mmax):
            return spatial[0] * coeff[0, 0, 0], theta, phi
        def scalar_nom0(coeff, lmax, mmax):
            scalar = spatial[0] * coeff[0, 0, 0]
            return scalar - scalar.mean(axis=-1, keepdims=True), theta, phi
        backend.load_state = load_state
        backend.PolTor_to_spat = vector_transform
        backend.SH_to_spat = scalar_transform
        backend.SH_to_spat_nom0 = scalar_nom0
        backend.gradient_spat = leeds.gradient_scalar_3d
        backend.curl_spat = leeds.compute_induction_from_emf
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder); source = root / "state00001.cdf.dat"; source.touch()
            args = leeds.build_arg_parser().parse_args(["--state", str(source), "--out", str(root / "out"),
                "--incremental", "--skip-field-lines", "--no-earth-br", "--downsample-theta", "2",
                "--Ek", "1e-4", "--Pr", "1", "--Sc", "1", "--RaT", "1e6", "--RaC", "0"])
            with mock.patch.dict(sys.modules, {"modules": backend}), \
                 mock.patch.object(leeds, "read_state_radial_representations", return_value={}), \
                 mock.patch.object(leeds, "read_netcdf_attributes", return_value={}):
                leeds.run_leeds_conversion(args)
                args.emf = args.induction = True
                leeds.run_leeds_conversion(args)
                self.assertEqual(reader_spy.call_count, 1)
                self.assertEqual(transform_spy.call_count, 2)
                args.out = str(root / "fresh"); args.incremental = False
                leeds.run_leeds_conversion(args)
                for path in (root / "fresh").glob("*.f32"):
                    self.assertEqual(path.read_bytes(), (root / "out" / path.name).read_bytes(), path.name)

                args.output = ["ur", "Br", "C", "vort_r"]; args.out = str(root / "selected")
                leeds.run_leeds_conversion(args)
                selected = json.loads((root / "selected" / "metadata.json").read_text())
                self.assertEqual(set(selected["fields"]), set(args.output))
                for filename in selected["fields"].values():
                    np.testing.assert_allclose(np.fromfile(root / "selected" / filename, dtype="<f4"),
                        np.fromfile(root / "fresh" / filename, dtype="<f4"), rtol=2e-5, atol=2e-6)
                for name, filename in json.loads((root / "fresh/metadata.json").read_text())["fields"].items():
                    with self.subTest(selected_leeds=name):
                        args.output = [name]
                        leeds.run_leeds_conversion(args)
                        np.testing.assert_allclose(np.fromfile(root / "selected" / filename, dtype="<f4"),
                            np.fromfile(root / "fresh" / filename, dtype="<f4"), rtol=2e-5, atol=2e-6)
                transform_spy.reset_mock(); args.output = ["C"]
                leeds.run_leeds_conversion(args)
                self.assertEqual(transform_spy.call_count, 0, "C-only export must not synthesize velocity or B")
                args.output = None
                args.Pr = None; args.no_parameter_prompt = True; args.out = str(root / "unknown")
                leeds.run_leeds_conversion(args)
                unknown = json.loads((root / "unknown" / "metadata.json").read_text())
                self.assertIsNone(unknown["parameters"]["Pr"])
                self.assertNotIn("N2_full", unknown["fields"])
                self.assertIn("vort_z", unknown["fields"])
                self.assertNotIn("N2", json.loads((root / "unknown" / "profiles.json").read_text()))

    def test_xshells_added_diagnostic_reuses_synthesis_and_matches_fresh_output(self):
        # Native readers/transforms are fixtures; all remapping, derivatives,
        # diagnostics, sampling, validation and cache operations are real.
        sys.modules.setdefault("pyxshells", types.ModuleType("pyxshells"))
        sys.modules.setdefault("shtns", types.ModuleType("shtns"))
        sys.modules.setdefault("h5py", types.ModuleType("h5py"))
        xs = fixtures.load_module("incremental_xshells_test", fixtures.XSHELLS_PATH)
        graph = fixtures.ConverterPackageTests.fake_magic_graph()
        r = graph.radius[::-1].copy(); theta = graph.colatitude
        phi = np.linspace(0, 2*np.pi, graph.vr.shape[0], endpoint=False)
        transform_spy = mock.Mock()
        class Transform:
            def set_grid(self, *args): return len(theta), len(phi)
        class PolTor:
            def __init__(self, arrays):
                self.arrays = arrays; self.sht = Transform()
                self.lmax = self.mmax = 2; self.mres = 1
                self.grid = types.SimpleNamespace(r=r)
                self.irs = 0; self.ire = len(r) - 1; self.time = 1.25
            def theta_array(self): return theta
            def phi_array(self): return phi
            def spat_full(self):
                transform_spy()
                return np.stack([np.transpose(a[:, :, ::-1], (2, 1, 0)) for a in self.arrays], axis=1)
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder)
            for name in ("fieldU.test", "fieldB.test"):
                (root / name).touch()
            args = xs.build_arg_parser().parse_args(["--velocity", str(root / "fieldU.test"),
                "--magnetic", str(root / "fieldB.test"), "--out", str(root / "out"),
                "--incremental", "--skip-field-lines", "--no-earth-br", "--downsample-theta", "2",
                "--Ek", "1e-4", "--Pr", "1", "--Sc", "1", "--RaT", "1e6", "--RaC", "0"])
            def load(path, lazy=True):
                return PolTor((graph.vr, graph.vtheta, graph.vphi) if "fieldU" in str(path)
                              else (graph.Br, graph.Btheta, graph.Bphi))
            def convert(opts): return xs.convert_xshells(opts)
            with mock.patch.object(xs.pyxshells, "PolTor", PolTor, create=True), \
                 mock.patch.object(xs.pyxshells, "load_field", side_effect=load, create=True):
                cc.run_conversion(args, "xshells", xs.resolve_inputs(args).values(), convert)
                args.emf = args.induction = True
                cc.run_conversion(args, "xshells", xs.resolve_inputs(args).values(), convert)
                self.assertEqual(transform_spy.call_count, 2)
                args.out = str(root / "fresh"); args.incremental = False
                cc.run_conversion(args, "xshells", xs.resolve_inputs(args).values(), convert)
                for path in (root / "fresh").glob("*.f32"):
                    self.assertEqual(path.read_bytes(), (root / "out" / path.name).read_bytes(), path.name)

                args.output = ["ur", "Br", "vort_r"]; args.out = str(root / "selected")
                cc.run_conversion(args, "xshells", xs.resolve_inputs(args).values(), convert)
                selected = json.loads((root / "selected" / "metadata.json").read_text())
                self.assertEqual(set(selected["fields"]), set(args.output))
                for filename in selected["fields"].values():
                    np.testing.assert_allclose(np.fromfile(root / "selected" / filename, dtype="<f4"),
                        np.fromfile(root / "fresh" / filename, dtype="<f4"), rtol=2e-5, atol=2e-6)
                for name, filename in json.loads((root / "fresh/metadata.json").read_text())["fields"].items():
                    with self.subTest(selected_xshells=name):
                        args.output = [name]
                        cc.run_conversion(args, "xshells", xs.resolve_inputs(args).values(), convert)
                        np.testing.assert_allclose(np.fromfile(root / "selected" / filename, dtype="<f4"),
                            np.fromfile(root / "fresh" / filename, dtype="<f4"), rtol=2e-5, atol=2e-6)
                transform_spy.reset_mock(); args.output = ["Br"]
                cc.run_conversion(args, "xshells", xs.resolve_inputs(args).values(), convert)
                self.assertEqual(transform_spy.call_count, 1, "Br-only export must skip velocity synthesis")


if __name__ == "__main__":
    unittest.main()
