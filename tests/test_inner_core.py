"""Analytic core fields, native file layout, and transactional incremental reuse."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np
from scipy.io import netcdf_file
try:
    import h5py
except ImportError:
    h5py = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import inner_core as ic
from tools import conversion_cache as cache
from tools.viewer_bundle import validate_bundle, write_f32
import test_converter_package as fixtures


class CoreTransform:
    """Analytic Schmidt l=1,m=0 SHT adapter: Y10=cos(theta)."""
    def __init__(self, *args):
        self.l = np.array([0, 1]); self.m = np.array([0, 0])
        self.cos_theta = np.array([0.8, 0., -0.8]); self.nphi = 4
    def set_grid(self): return 3, self.nphi
    def synth(self, q, s, t):
        cos = self.cos_theta[:, None] * np.ones((1, self.nphi))
        sin = np.sqrt(1 - cos*cos)
        return q[1].real*cos, -s[1].real*sin, t[1].real*sin


def backend():
    return types.SimpleNamespace(
        shtns=types.SimpleNamespace(sht=CoreTransform, sht_schmidt=0, SHT_NO_CS_PHASE=0),
        lsd_to_shtns=lambda a, sh: a[0] + 1j*a[1],
    )


def state_file(path, *, regular=False, centre=False):
    r = np.array([0 if centre else .03, .1, .2, .3, .4, .5])
    # Real Leeds releases can pad the IC arrays to the outer-core radial size.
    with netcdf_file(path, "w") as f:
        f.createDimension("icr", len(r)); f.createDimension("r", len(r)+2)
        f.createDimension("H", 2); f.createDimension("ReIm", 2)
        f.createVariable("icr", "d", ("icr",))[:] = r
        for name in ("icBP", "icBT"):
            var = f.createVariable(name, "d", ("ReIm", "H", "r"))
            var.L = 2; var.M = 1; var.Mp = 1
            var[:] = 9.969e36
            var[..., :len(r)] = 0
            var[0, 1, :len(r)] = (.5 if name == "icBP" else .2) * (np.ones_like(r) if regular else r)
            if regular:
                var.radial_representation = "regular_r_power_g_x"
                var.radial_power_offset = 0
    return r


def outer_bundle(root, source, kind="leeds", *, includes_ic=False):
    root.mkdir(parents=True, exist_ok=True)
    r = [.03, .2, .5, .75, 1.] if includes_ic else [.5, .75, 1.]
    coords = {"r": r, "theta": np.arccos([.8,0,-.8]).tolist(),
              "phi": (np.arange(4)*np.pi/2).tolist()}
    (root / "coordinates.json").write_text(json.dumps(coords))
    fields, ranges = {}, {}
    for name in (*ic.MAGNETIC_FIELDS, "C", "helicity"):
        filename = f"{name}_volume.f32"
        fields[name] = filename
        # Recognisable outer values, deliberately unrelated to the analytic core.
        values = np.arange(len(r)*3*4, dtype=float).reshape(len(r),3,4) * .001 + 1
        ranges[name] = write_f32(root / filename, values)
    (root / "B_lines.json").write_text('[{"line_id": "unchanged"}]')
    (root / "profiles.json").write_text('{"r": [0.5, 0.75, 1.0], "C": [3,2,1]}')
    (root / "view.DTV2").write_text("unchanged view")
    meta = {"source_format": kind, "source_state": str(source), "nr": len(r), "ntheta": 3, "nphi": 4,
        "r_inner": r[0], "r_outer": 1., "r_icb": .5, "has_inner_core": True,
        "spectral_truncation": {"lmax_effective": 1, "mmax_effective": 0},
        "sampling": {"requested_strides": [1,1,1]}, "fields": fields, "ranges": ranges,
        "coordinates": "coordinates.json", "profiles": "profiles.json", "field_lines": {"all": "B_lines.json"}}
    (root / "metadata.json").write_text(json.dumps(meta))
    return meta


def manifest(root, source):
    files = {str(p.relative_to(root)): cache.file_digest(p) for p in root.rglob("*")
             if p.is_file() and p.name not in (cache.MANIFEST, "view.DTV2")}
    (root / cache.MANIFEST).write_text(json.dumps({"version": 1, "request": "old-converter",
        "source_sha256": {str(source.resolve()): cache.file_digest(source)}, "files": files}))


class InnerCoreTests(unittest.TestCase):
    @unittest.skipIf(h5py is None, "h5py optional in the test environment")
    def test_hdf5_reader_honours_markers_and_descending_coordinates(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"state.h5"
            with h5py.File(path,"w") as f:
                f["icr"]=[.5,.2,0.]
                for name in ("icBP","icBT"):
                    values=np.zeros((2,2,3));values[0,1]=[3,2,1]
                    var=f.create_dataset(name,data=values)
                    var.attrs.update(L=[2],M=[1],radial_representation=np.bytes_("regular_r_power_g_x"),radial_power_offset=[0])
            data=ic.read_leeds_inner_core(path)
            np.testing.assert_array_equal(data["r"],[0,.2,.5])
            np.testing.assert_array_equal(data["icBP"][0,1],[1,2,3])
            self.assertEqual(data["representations"]["icBT"]["representation"],"regular_r_power_g_x")

    def test_classic_reader_crops_padding_and_keeps_conventional_potentials(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"state.cdf"; r = state_file(path)
            data = ic.read_leeds_inner_core(path)
            np.testing.assert_array_equal(data["r"], r)
            self.assertEqual(data["icBP"].shape, (2,2,len(r)))
            self.assertEqual(data["representations"]["icBP"]["representation"], "conventional_r_coefficient")
            np.testing.assert_allclose(data["icBP"][0,1], .5*r)

    def test_missing_grid_is_rejected_not_guessed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"bad.cdf"
            with netcdf_file(path,"w") as f:
                f.createDimension("n",2); f.createVariable("icBP", "d", ("n",))[:] = 1
            with self.assertRaisesRegex(ValueError, "icr coordinate is missing"):
                ic.read_leeds_inner_core(path)

    def test_qst_matches_analytic_dipole_quadrupole_and_toroidal_fields(self):
        r = np.linspace(.01,.5,40)
        degree = np.array([0,1,2])
        pol = np.array([r*0, .5*r, .3*r*r], dtype=complex)
        tor = np.array([r*0, .2*r, .4*r*r], dtype=complex)
        reps = {name: {"representation":"conventional_r_coefficient", "power_offset":0} for name in ("icBP","icBT")}
        q,s,t = ic.leeds_inner_qst(pol,tor,degree,r,reps,None)
        np.testing.assert_allclose(q[1], 1, atol=1e-13)
        np.testing.assert_allclose(s[1], 1, atol=1e-13)
        np.testing.assert_allclose(q[2], 1.8*r, atol=1e-13)
        np.testing.assert_allclose(s[2], .9*r, atol=1e-13)
        np.testing.assert_array_equal(t,tor)
        # Solenoidal identity: d(r² Q)/dr = l(l+1) r S, including non-axisymmetric coefficients.
        np.testing.assert_allclose(ic.radial_derivative(r*r*q,r), degree[:,None]*(degree+1)[:,None]*r*s, atol=2e-12)

    def test_regular_qst_has_uniform_cartesian_center_and_correct_radial_powers(self):
        r = np.linspace(0,.5,40); degree=np.array([0,1,2])
        g=np.array([r*0, .5+0*r, .3+.2*r*r], dtype=complex)
        h=np.array([r*0, .2+0*r, .4+0*r], dtype=complex)
        reps={name:{"representation":"regular_r_power_g_x","power_offset":0} for name in ("icBP","icBT")}
        q,s,t=ic.leeds_inner_qst(g,h,degree,r,reps,None)
        np.testing.assert_allclose(q[1],1,atol=1e-13)
        np.testing.assert_allclose(s[1],1,atol=1e-13)
        np.testing.assert_allclose(s[2], .9*r+1*r**3,atol=1e-13)
        np.testing.assert_allclose(t[1], .2*r,atol=1e-13)
        br,bt,bp=CoreTransform().synth(q[:,0],s[:,0],t[:,0])
        cos=CoreTransform().cos_theta[:,None]; sin=np.sqrt(1-cos*cos)
        np.testing.assert_allclose(br*cos-bt*sin,1,atol=1e-13)
        np.testing.assert_allclose(br*sin+bt*cos,0,atol=1e-13)
        np.testing.assert_allclose(bp,0,atol=1e-13)

    def test_additive_update_preserves_outer_bytes_views_profiles_and_lines_without_cache(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root=Path(folder); source=root/"state.cdf"; r=state_file(source)
            out=root/"out"; meta=outer_bundle(out,source); manifest(out,source)
            old={p.name:p.read_bytes() for p in out.iterdir() if p.is_file()}
            args=argparse.Namespace(out=str(out),inner_core_only=True)
            callback=lambda target,meta,sources: ic.extend_leeds_inner_core(target,source,backend(),required=True)
            forbidden=mock.Mock(side_effect=AssertionError("outer conversion must never run"))
            cache.run_conversion(args,"leeds",[source],forbidden,inner_core_update=callback)
            forbidden.assert_not_called()
            validate_bundle(out)
            result=json.loads((out/"metadata.json").read_text())
            self.assertEqual(result["nr"],meta["nr"]+len(r)-1)
            self.assertTrue(result["inner_core"]["available"])
            prefix_bytes=(len(r)-1)*3*4*4
            for name in meta["fields"].values():
                self.assertEqual((out/name).read_bytes()[prefix_bytes:],old[name],name)
            for name in ("view.DTV2","B_lines.json","profiles.json"):
                self.assertEqual((out/name).read_bytes(),old[name])
            values=np.fromfile(out/"Br_volume.f32",dtype="<f4").reshape(result["nr"],3,4)
            np.testing.assert_allclose(values[:len(r)-1], np.broadcast_to(np.array([.8,0,-.8])[None,:,None],(len(r)-1,3,4)),atol=1e-7)
            self.assertEqual(result["field_domains"]["C"]["r_min"],.5)
            # Repeating an update adds no rows and does not call the transform.
            with mock.patch.object(ic,"synthesise_leeds_inner",side_effect=AssertionError("already exported")):
                cache.run_conversion(args,"leeds",[source],forbidden,inner_core_update=callback)
            self.assertEqual(json.loads((out/"metadata.json").read_text())["nr"],result["nr"])

    def test_leeds_entry_point_addition_matches_fresh_output_and_never_reloads_outer_state(self):
        from tools import convert_leeds_to_viewer as leeds
        module=types.ModuleType("modules");module.__file__=__file__
        module.shtns=backend().shtns;module.lsd_to_shtns=backend().lsd_to_shtns
        r=np.array([.5,.75,1.]);theta=np.arccos([.8,0,-.8]);phi=np.arange(4)*np.pi/2
        coefficients=np.ones((2,2,3)); base=np.ones((3,3,4))
        reader=mock.Mock()
        def load_state(path):
            reader()
            return {"uP":coefficients,"uT":coefficients*.1,"BP":coefficients*.3,"BT":coefficients*.2,
                "C":coefficients*.4,"Comp":coefficients*.5,"r":r,"lmax":1,"mmax":0,"t":1.}
        def vector(pol,tor,radius,lmax,mmax,alpha_map=-1):
            return base*.1,base*.2,base*.3,theta,phi
        def scalar(coeff,lmax,mmax):return base*coeff[0,0,0],theta,phi
        def scalar_nom0(coeff,lmax,mmax):return base*0,theta,phi
        module.load_state=load_state;module.PolTor_to_spat=vector
        module.SH_to_spat=scalar;module.SH_to_spat_nom0=scalar_nom0
        module.gradient_spat=leeds.gradient_scalar_3d;module.curl_spat=leeds.compute_induction_from_emf
        with tempfile.TemporaryDirectory() as folder,redirect_stdout(io.StringIO()),mock.patch.dict(sys.modules,{"modules":module}):
            root=Path(folder);source=root/"state00001.cdf.dat";state_file(source)
            args=leeds.build_arg_parser().parse_args(["--state",str(source),"--out",str(root/"old"),
                "--skip-field-lines","--no-earth-br","--no-parameter-prompt",
                "--Ek","1e-4","--Pr","1","--Sc","1","--RaT","1e6","--RaC","0"])
            # Simulate a previous converter that did not append the separate IC arrays.
            with mock.patch.object(ic,"extend_leeds_inner_core"):
                leeds.run_leeds_conversion(args)
            self.assertEqual(reader.call_count,1)
            self.assertEqual(json.loads((root/"old/metadata.json").read_text())["nr"],3)
            args.inner_core_only=True
            leeds.run_leeds_conversion(args)
            self.assertEqual(reader.call_count,1,"the public CLI bypasses load_state and outer transforms")
            self.assertGreater(json.loads((root/"old/metadata.json").read_text())["nr"],3)
            args.inner_core_only=False;args.out=str(root/"fresh");args.geometry="conducting-inner-core"
            leeds.run_leeds_conversion(args)
            for path in (root/"fresh").glob("*.f32"):
                self.assertEqual(path.read_bytes(),(root/"old"/path.name).read_bytes(),path.name)

    def test_mismatched_icb_or_changed_source_does_not_modify_existing_output(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root=Path(folder); source=root/"state.cdf"; state_file(source)
            out=root/"out"; outer_bundle(out,source); manifest(out,source)
            old={p.name:p.read_bytes() for p in out.iterdir()}
            def bad_update(target,meta,sources):
                data=ic.read_leeds_inner_core(source); data["r"]*=2
                ic.extend_leeds_inner_core(target,source,backend(),inner=data)
            args=argparse.Namespace(out=str(out),inner_core_only=True)
            with self.assertRaisesRegex(ValueError,"ICB"):
                cache.run_conversion(args,"leeds",[source],mock.Mock(),inner_core_update=bad_update)
            for name,values in old.items(): self.assertEqual((out/name).read_bytes(),values)
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError,"inputs differ"):
                cache.run_conversion(args,"leeds",[source],mock.Mock(),inner_core_update=bad_update)

    def test_xshells_and_magic_existing_core_get_domains_without_native_calculations(self):
        for kind in ("xshells","magic"):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as folder,redirect_stdout(io.StringIO()):
                root=Path(folder); source=root/"input"; source.touch()
                out=root/"out"; meta=outer_bundle(out,source,kind,includes_ic=True); manifest(out,source)
                old={p.name:p.read_bytes() for p in out.glob("*.f32")}
                forbidden=mock.Mock(side_effect=AssertionError("native calculation"))
                cache.run_conversion(argparse.Namespace(out=str(out),inner_core_only=True),kind,[source],forbidden)
                forbidden.assert_not_called(); validate_bundle(out)
                result=json.loads((out/"metadata.json").read_text())
                self.assertEqual(result["field_domains"]["Br"]["r_min"],.03)
                self.assertEqual(result["field_domains"]["C"]["r_min"],.5)
                for name,values in old.items(): self.assertEqual((out/name).read_bytes(),values)

    def test_padded_below_native_magnetic_domain_is_not_advertised_as_core_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);meta=outer_bundle(root,root/"source","xshells",includes_ic=True)
            meta["field_domains"]={name:{"r_min":.5,"r_max":1.} for name in ("Br","Bt","Bp")}
            (root/"metadata.json").write_text(json.dumps(meta))
            self.assertFalse(ic.describe_inner_core(root))

    def test_magic_actual_adapter_keeps_core_components_and_fluid_domain(self):
        magic=fixtures.load_module("core_magic_test",fixtures.MAGIC_PATH)
        graph=fixtures.ConverterPackageTests.fake_magic_graph()
        graph.radius_ic=np.array([.35,.2,.05]); graph.sigma=1.
        shape=(graph.vr.shape[0],graph.vr.shape[1],3)
        graph.Br_ic=np.full(shape,7.); graph.Btheta_ic=np.full(shape,8.); graph.Bphi_ic=np.full(shape,9.)
        result=magic.adapt_graph(graph)
        self.assertTrue(result["has_conducting_inner_core"])
        for name,value in (("Br",7.),("Bt",8.),("Bp",9.)):
            np.testing.assert_array_equal(result["fields"][name][:2],value)
        self.assertEqual(result["fields"]["ur"].shape[0],len(graph.radius))
        graph.radius_ic[0]=.6
        with self.assertRaisesRegex(ValueError,"outside the ICB"):
            magic.adapt_graph(graph)
        del graph.Bphi_ic
        with self.assertRaisesRegex(ValueError,"incomplete"):
            magic.adapt_graph(graph)

    def test_sequence_update_uses_each_verified_state_and_preserves_frame_views(self):
        with tempfile.TemporaryDirectory() as folder,redirect_stdout(io.StringIO()):
            root=Path(folder); out=root/"out"; sources=[]; frames=[]
            for n in (1,2):
                source=root/f"state{n}.cdf";state_file(source);sources.append(source)
                frame=out/"frames"/f"state{n}"
                outer_bundle(frame,source);manifest(frame,source)
                (frame/"view.DTV2").write_text(f"view {n}")
                frames.append({"path":f"frames/state{n}","state_number":n})
            outer_bundle(out,sources[0])
            (out/"sequence.json").write_text(json.dumps({"frames":frames}))
            manifest(out,sources[0])
            saved=json.loads((out/cache.MANIFEST).read_text())
            saved["source_sha256"]={str(source.resolve()):cache.file_digest(source) for source in sources}
            (out/cache.MANIFEST).write_text(json.dumps(saved))
            seen=[]
            def update(target,meta,hashes):
                source=meta["source_state"];self.assertIn(source,hashes);seen.append(source)
                ic.extend_leeds_inner_core(target,source,backend(),required=True)
            cache.run_conversion(argparse.Namespace(out=str(out),inner_core_only=True),"leeds",sources,mock.Mock(),inner_core_update=update)
            self.assertEqual(seen,[str(s) for s in sources])
            self.assertEqual((out/"view.DTV2").read_text(),"unchanged view")
            for n in (1,2):
                self.assertEqual((out/"frames"/f"state{n}"/"view.DTV2").read_text(),f"view {n}")
            self.assertEqual((out/"Br_volume.f32").read_bytes(),(out/"frames/state1/Br_volume.f32").read_bytes())
            validate_bundle(out)


if __name__=="__main__": unittest.main()
