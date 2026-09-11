"""Calypso native ASCII, analytic harmonics and transactional export tests.

Set CALYPSO_SAMPLE_DIR to dynamobench_case_1 to run the supplied-file checks.
The optional samples are not redistributed in the repository.
"""
from contextlib import redirect_stdout
import gzip
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import calypso_data as native
from tools import convert_calypso_to_viewer as converter
from tools import convert_magic_to_viewer as magic
from tools.viewer_bundle import validate_bundle


def write_ascii(path, fields, counts, step=0):
    counts = np.cumsum(counts)
    with Path(path).open("wb") as f:
        f.write((f"! domain ID\n{len(counts)}\n! step\n{step}\n! time, dt\n{step*.1} .1\n"
                 + " ".join(map(str, counts)) + f"\n{len(fields)}\n"
                 + " ".join(str(a.shape[1]) for a in fields.values()) + "\n").encode())
        for name, a in fields.items():
            f.write((name + "\n" + " ".join(map(str, counts*(25*a.shape[1]+1))) + "\n").encode())
            for row in a:
                f.write(("".join(f"{v:25.15E}" for v in row) + "\n").encode())


def make_run(root, geometry="shell", steps=(0,), magnetic=True, radius=None):
    """Independent one-rank native encoding of Cartesian B=(.4,-.2,1),
    solid rotation u=(-y,x,0), T=1-r²+.1x and composition=2+.1r².
    """
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    r = np.array([.05, .15, .35, .5, .7, 1.]) if geometry != "shell" else np.array([.35,.5,.7,1.])
    if radius is not None:
        r = np.asarray(radius, dtype=float)
    icb = 2 if geometry == "core" else 0
    centre = geometry != "shell"
    extra = "sph_coef_type_ctl with_center\n" if centre else ""
    bc = "bc_velocity sph_to_center ICB 0\n" if geometry == "full" else ""
    control = f"""begin MHD_control
restart_file_prefix rst
begin spherical_shell_ctl
num_radial_domain_ctl 1
num_horizontal_domain_ctl 1
truncation_level_ctl 4
ngrid_meridonal_ctl 8
ngrid_zonal_ctl 12
radial_grid_type_ctl explicit
{extra}array r_layer {len(r)}
""" + "".join(f"r_layer {i+1} {x}\n" for i,x in enumerate(r)) + f"""end array r_layer
array boundaries_ctl 2
boundaries_ctl ICB {icb+1}
boundaries_ctl CMB {len(r)}
end array boundaries_ctl
end spherical_shell_ctl
{bc}dimless_ctl Ekman_number .01
dimless_ctl Prandtl_number 2
dimless_ctl Schmidt_number 3
dimless_ctl modified_Rayleigh 20
coef_4_velocity_ctl Ekman_number 1
coef_4_coriolis_ctl Two 1
coef_4_thermal_buoyancy_ctl modified_Rayleigh 1
coef_4_composit_buoyancy_ctl One 1
end MHD_control
"""
    (root / "control_MHD").write_text(control)
    # Direct table from the documented native order, independent of reader.
    modes = [(l,m) for m in range(4,-5,-1) for l in range(abs(m),5)]
    spectra = {name: np.zeros((len(r),25,nc)) for name,nc in
               (("velocity",3),("temperature",1),("composition",1),("magnetic_field",3))}
    for j,(l,m) in enumerate(modes):
        if (l,m)==(1,0): spectra["velocity"][:,j,1]=r*r
        if l == 1:
            b = {1:.4,-1:-.2,0:1.}[m]
            spectra["magnetic_field"][:,j,0]=.5*b*r*r
            spectra["magnetic_field"][:,j,2]=b*r
        if (l,m)==(0,0):
            spectra["temperature"][:,j,0]=1-r*r
            spectra["composition"][:,j,0]=2+.1*r*r
        if (l,m)==(1,1): spectra["temperature"][:,j,0]=.1*r
    if not magnetic: spectra.pop("magnetic_field")
    fields = {}
    for name,a in spectra.items():
        values = a.reshape(-1,a.shape[-1])
        if centre:
            c = np.zeros((1,a.shape[-1]))
            if name == "temperature": c[0,0] = 1
            if name == "composition": c[0,0] = 2
            values = np.concatenate((values,c))
        fields[name]=values
    for step in steps:
        write_ascii(root / f"rst.{step}.fst", fields, [len(next(iter(fields.values())))], step)
    return r


class CalypsoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_converter(self, *options, geometry="shell", steps=(0,), magnetic=True):
        source = self.root / "run"
        if not source.exists(): make_run(source, geometry, steps, magnetic)
        output = self.root / "out"
        with redirect_stdout(io.StringIO()) as log:
            converter.main(["--folder",str(source),"--out",str(output),"--skip-field-lines",
                            "--cache-dir",str(self.root/"cache"),*options])
        validate_bundle(output)
        return output, json.loads((output/"metadata.json").read_text()), log.getvalue()

    def test_shared_options_and_full_resolution_default(self):
        own = converter.build_arg_parser()
        generic = magic.add_viewer_arguments(__import__("argparse").ArgumentParser(), "out")
        self.assertTrue(set(generic._option_string_actions) <= set(own._option_string_actions))
        output, meta, _ = self.run_converter()
        self.assertEqual((meta["nr"],meta["ntheta"],meta["nphi"]),(4,8,16))
        self.assertEqual(meta["spectral"]["lmax"],4)
        self.assertFalse(meta["spectral_truncation"]["enabled"])
        self.assertEqual(meta["source_format"],"calypso")
        self.assertIsNone(meta["parameters"]["RaT"], "modified Ra must not masquerade as conventional Ra")

    def test_scalar_vector_phase_normalization_and_potential_derivative(self):
        output,meta,_ = self.run_converter("--emf","--induction")
        coords = json.loads((output/"coordinates.json").read_text())
        r=np.array(coords["r"])[:,None,None]; t=np.array(coords["theta"])[None,:,None]
        p=np.array(coords["phi"])[None,None,:]
        shape=(meta["nr"],meta["ntheta"],meta["nphi"])
        field=lambda name:np.fromfile(output/meta["fields"][name],dtype="<f4").reshape(shape)
        expected=(.4*np.sin(t)*np.cos(p)-.2*np.sin(t)*np.sin(p)+np.cos(t),
                  .4*np.cos(t)*np.cos(p)-.2*np.cos(t)*np.sin(p)-np.sin(t),
                  -.4*np.sin(p)-.2*np.cos(p))
        for name,a in zip(("Br","Bt","Bp"),expected):
            np.testing.assert_allclose(field(name),np.broadcast_to(a,shape),atol=1e-7)
        np.testing.assert_allclose(field("T"),1-r*r+.1*r*np.sin(t)*np.cos(p),atol=1e-7)
        np.testing.assert_allclose(field("up"),np.broadcast_to(r*np.sin(t),shape),atol=1e-7)
        np.testing.assert_allclose(field("Uabs"),field("up"),atol=1e-7)
        np.testing.assert_allclose(field("Babs"),np.sqrt(1.2),atol=1e-7)
        np.testing.assert_allclose(field("EMFr"),-field("up")*field("Bt"),atol=1e-7)
        self.assertTrue(meta["optional_magnetic_diagnostics"]["induction_exported"])
        self.assertTrue({"T_nom0","C_nom0","N2","N2_nom0","grad_thetaT"} <= meta["fields"].keys())
        self.assertFalse({"Cnom0","Compnom0","Comp","N2_full"} & meta["fields"].keys())

    def test_full_sphere_has_one_regular_cartesian_centre(self):
        out,meta,_=self.run_converter(geometry="full")
        self.assertTrue(meta["full_sphere"]); self.assertEqual(meta["r_icb"],0)
        coords=json.loads((out/"coordinates.json").read_text())
        self.assertEqual(coords["r"][0],0);self.assertEqual(coords["r"].count(0),1)
        shape=(meta["nr"],meta["ntheta"],meta["nphi"])
        field=lambda n:np.fromfile(out/meta["fields"][n],dtype="<f4").reshape(shape)
        np.testing.assert_allclose(field("T")[0],1)
        np.testing.assert_allclose(field("Babs")[0],np.sqrt(1.2),atol=1e-7)
        np.testing.assert_allclose(field("Uabs")[0],0,atol=1e-7)
        np.testing.assert_allclose(field("Br")[0],field("Br")[1],atol=1e-7)

    def test_conducting_core_domain_and_core_only_preserve_outer_bytes(self):
        out,meta,_=self.run_converter("--incremental",geometry="core")
        self.assertTrue(meta["inner_core"]["available"])
        self.assertTrue(meta["has_conducting_inner_core"])
        self.assertEqual(meta["field_domains"]["C"]["r_min"],.35)
        before={p.name:p.read_bytes() for p in out.glob("*.f32")}
        _,_,log=self.run_converter("--inner-core-only",geometry="core")
        self.assertIn("No outer-core calculations",log)
        self.assertEqual(before,{p.name:p.read_bytes() for p in out.glob("*.f32")})

    def test_cutoff_downsampling_and_optional_fields(self):
        _,meta,_=self.run_converter("--spectral-lmax","2","--downsample-r","2",
                                   "--downsample-theta","2","--downsample-phi","2",
                                   "--no-m0-fields","--no-gradients")
        self.assertLess(meta["ntheta"],8);self.assertLess(meta["nphi"],12)
        self.assertEqual(meta["r_inner"],.35);self.assertEqual(meta["r_outer"],1)
        self.assertFalse(any("nom0" in n or "phiavg" in n or n.startswith("grad_") for n in meta["fields"]))

    def test_incremental_add_diagnostics_reuses_synthesis_and_preserves_view(self):
        out,meta,_=self.run_converter("--incremental")
        initial=(out/"Br_volume.f32").read_bytes()
        (out/"view.DTV2").write_text("saved user view")
        _,_,log=self.run_converter("--incremental")
        self.assertIn("skipped",log)
        _,meta,log=self.run_converter("--incremental","--emf","--induction")
        self.assertEqual(log.count("Reuse calculation: synthesize_spectra"),4)
        self.assertEqual((out/"Br_volume.f32").read_bytes(),initial)
        self.assertEqual((out/"view.DTV2").read_text(),"saved user view")
        self.assertIn("Ir",meta["fields"])

    def test_sequence_extension_and_failure_keep_existing_output(self):
        out,_,_=self.run_converter("--incremental","--sequence-first","0","--sequence-last","1",steps=(0,1,2))
        (out/"view.DTV2").write_text("root view")
        (out/"frames/state00001/view.DTV2").write_text("frame view")
        _,_,log=self.run_converter("--incremental","--sequence-first","0","--sequence-last","2")
        self.assertEqual(log.count("skipped"),2)
        self.assertEqual(len(json.loads((out/"sequence.json").read_text())["frames"]),3)
        self.assertEqual((out/"frames/state00001/view.DTV2").read_text(),"frame view")
        before=(out/"metadata.json").read_bytes()
        (self.root/"run/rst.2.fst").write_bytes(b"broken input")
        with self.assertRaises(ValueError):
            self.run_converter("--incremental","--sequence-first","0","--sequence-last","2")
        self.assertEqual((out/"metadata.json").read_bytes(),before)
        self.assertEqual((out/"view.DTV2").read_text(),"root view")

    def test_nonmagnetic_convection_is_usable(self):
        _,meta,_=self.run_converter("--emf","--induction",magnetic=False)
        self.assertIn("C",meta["fields"]);self.assertNotIn("Br",meta["fields"])
        self.assertFalse(meta["magnetic"]["has_magnetic_field"])

    def test_gzip_selective_read_and_truncation(self):
        make_run(self.root/"run")
        path=self.root/"run/rst.0.fst"
        compressed=path.with_suffix(".fst.gz")
        compressed.write_bytes(gzip.compress(path.read_bytes()))
        a=native.read_merged_ascii(path)
        b=native.read_merged_ascii(compressed,{"temperature"})
        np.testing.assert_array_equal(a["fields"]["temperature"],b["fields"]["temperature"])
        self.assertEqual(list(b["fields"]),["temperature"])
        path.write_bytes(path.read_bytes()[:-30])
        with self.assertRaisesRegex(ValueError,"Truncated"):
            native.read_merged_ascii(path)

    def test_wrong_control_grid_rejected_before_publication(self):
        make_run(self.root/"run")
        ctl=self.root/"run/control_MHD"
        ctl.write_text(ctl.read_text().replace("num_radial_domain_ctl 1","num_radial_domain_ctl 2"))
        with self.assertRaisesRegex(ValueError,"MPI count"):
            self.run_converter()
        self.assertFalse((self.root/"out/metadata.json").exists())

    def test_linked_controls_cycles_and_unknown_ordering(self):
        (self.root/"control_MHD").write_text("file spherical_shell_ctl control_MHD\n")
        with self.assertRaisesRegex(ValueError,"Cyclic"):
            native.read_controls(self.root/"control_MHD")
        make_run(self.root/"run")
        records,_=native.read_controls(self.root/"run/control_MHD")
        records.append(((),"rlm_order_distribution",["not-a-native-order"]))
        with self.assertRaisesRegex(ValueError,"distribution"):
            native.grid_from_controls(records)

    def test_folded_modes_cover_only_native_orders_once(self):
        modes=native.spectral_rank_modes(8,3,2,2)
        pairs=np.concatenate(modes)
        self.assertEqual(len(set(map(tuple,pairs))),len(pairs))
        self.assertTrue(np.all(pairs[:,1]%2==0))
        self.assertEqual(set(map(tuple,pairs)),{(l,m) for l in range(9) for m in range(-l,l+1) if m%2==0})

    def test_native_buoyancy_normalization_and_explicit_override(self):
        r=make_run(self.root/"run")
        records,_=native.read_controls(self.root/"run/control_MHD")
        args=converter.build_arg_parser().parse_args([])
        params,factors,_=converter.physical_parameters(records,args,r)
        self.assertIsNone(params["ra"])
        np.testing.assert_allclose(factors["T"],.2*r)
        np.testing.assert_allclose(factors["C"],.01*r)
        args.RaT=20
        _,factors,_=converter.physical_parameters(records,args,r)
        np.testing.assert_allclose(factors["T"],.001*r)

    def test_cutoff_removes_high_degree_without_rotating_retained_scalar(self):
        r=np.array([.4,.7,1.]);theta=np.arccos(np.polynomial.legendre.leggauss(8)[0][::-1])
        coefs=np.zeros((3,25,1));coefs[:,3,0]=r;coefs[:,24,0]=100
        actual=native.synthesize_spectra(coefs,r,theta,12,2)[0]
        expected=r[:,None,None]*np.sin(theta)[None,:,None]*np.cos(np.arange(12)*2*np.pi/12)[None,None,:]
        np.testing.assert_allclose(actual,expected,atol=1e-13)


SAMPLE=os.environ.get("CALYPSO_SAMPLE_DIR")


@unittest.skipUnless(SAMPLE,"set CALYPSO_SAMPLE_DIR for the supplied benchmark data")
class CalypsoSuppliedSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(SAMPLE)
        records,_=native.read_controls(cls.root/"control_MHD")
        cls.grid=native.grid_from_controls(records)
        cls.r=cls.grid["r"]
        cls.theta=np.arccos(np.polynomial.legendre.leggauss(96)[0][::-1])

    def test_initial_magnetic_benchmark_has_correct_amplitude_and_sign(self):
        spectra,_,_=native.read_restart(self.root/"rst_6/rst.0.fst",self.grid)
        br,bt,bp=native.synthesize_spectra(spectra["magnetic_field"],self.r,self.theta,192,63,True)
        r=self.r[:,None,None];t=self.theta[None,:,None];ri=self.r[0];ro=self.r[-1]
        expected=(5/8*(8*ro-6*r-2*ri**4/r**3)*np.cos(t),
                  5/8*(9*r-8*ro-ri**4/r**3)*np.sin(t),
                  5*np.sin(np.pi*(r-ri))*np.sin(2*t))
        for actual,wanted in zip((br,bt,bp),expected):
            np.testing.assert_allclose(actual,np.broadcast_to(wanted,actual.shape),atol=5e-12)

    def test_restart_matches_independent_cartesian_snapshot(self):
        spectra,_,_=native.read_restart(self.root/"rst_6/rst.1.fst",self.grid)
        physical=native.read_merged_ascii(self.root/"field/out.1.fld",{"velocity","temperature","magnetic_field"})
        radial=[np.arange(0,25),np.arange(25,49),np.arange(49,73)]
        polar=[np.arange(48),np.arange(48,96)]
        t=self.theta[None,:,None];p=np.arange(192)[None,None,:]*2*np.pi/192
        for name in ("temperature","velocity","magnetic_field"):
            a=native.synthesize_spectra(spectra[name],self.r,self.theta,192,63,name!="temperature")
            if len(a)==3:
                u,v,w=a
                a=(u*np.sin(t)*np.cos(p)+v*np.cos(t)*np.cos(p)-w*np.sin(p),
                   u*np.sin(t)*np.sin(p)+v*np.cos(t)*np.sin(p)+w*np.cos(p),
                   u*np.cos(t)-v*np.sin(t))
            offset=0
            for rank,count in enumerate(physical["counts"]):
                rr=radial[rank//2];tt=95-polar[rank%2]
                # Owned nodes precede halo nodes; longitude is fastest.
                n=len(rr)*48*192
                for component,values in enumerate(a):
                    wanted=values[rr[:,None,None],tt[None,:,None],np.arange(192)[None,None,:]].transpose(1,0,2).ravel()
                    actual=physical["fields"][name][offset:offset+n,component]
                    tolerance={"temperature":2e-12,"velocity":1e-8,"magnetic_field":8e-8}[name]
                    np.testing.assert_allclose(actual,wanted,rtol=0,atol=tolerance)
                offset+=int(count)


if __name__=="__main__":
    unittest.main()
