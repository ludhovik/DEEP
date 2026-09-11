"""Numerical equivalence, grid lifetime, progress and interrupted conversion."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import convert_leeds_to_viewer as tracer
from tools import convert_calypso_to_viewer as calypso
from tools import field_line_progress
from tools.viewer_bundle import validate_bundle, write_field_lines
from test_calypso_converter import make_run


class ReferenceSampler:
    """Call the unchanged scalar interpolation separately for each component."""
    def __init__(self, br, bt, bp, r, theta, phi):
        self.fields=(br,bt,bp);self.grid=(r,theta,phi)

    def sample(self,r,theta,phi):
        return tuple(tracer.interp_spherical_field(a,*self.grid,r,theta,phi) for a in self.fields)


def fields(exterior=False, dtype=np.float64):
    radius=np.geomspace(1,8,32) if exterior else np.array([.3,.35,.48,.62,.85,1.])
    theta=np.linspace(.03,np.pi-.03,28)
    phi=np.arange(20)*2*np.pi/20
    r,t,p=np.meshgrid(radius,theta,phi,indexing="ij")
    # Tilted dipole plus interior toroidal field; includes non-axisymmetric B.
    axis=.2*np.sin(t)*np.cos(p)-.1*np.sin(t)*np.sin(p)+np.cos(t)
    br=2*axis/r**3
    bt=(-.2*np.cos(t)*np.cos(p)+.1*np.cos(t)*np.sin(p)+np.sin(t))/r**3
    bp=(.2*np.sin(p)+.1*np.cos(p))/r**3
    if not exterior: bp+=.3*r*np.sin(t)
    return tuple(a.astype(dtype) for a in (br,bt,bp)),radius,theta,phi


class FieldLinePerformanceTests(unittest.TestCase):
    def test_line_json_matches_streaming_output_and_rejects_invalid_numbers(self):
        records=[{"line_id":"test", "strength":[1.,None,.3],
                  "points":[[.12345678901234567,-2.3,1e-11]]*10000}]
        reference=io.StringIO();json.dump(records,reference,allow_nan=False)
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            path=Path(directory)/"B_lines.json"
            write_field_lines(path,records)
            self.assertEqual(path.read_text(),reference.getvalue())
            self.assertEqual(json.loads(path.read_text()),records)
            with self.assertRaises(ValueError): write_field_lines(path,[{"points":[float("nan")]}])
            self.assertEqual(path.read_text(),reference.getvalue())

    def test_prepared_interpolation_equals_reference_at_seams_poles_and_boundaries(self):
        rng=np.random.default_rng(20260909)
        for dtype in (np.float32,np.float64):
            b,r,t,p=fields(dtype=dtype)
            for phi in (p,(p+.31)%(2*np.pi),np.zeros_like(p),np.array([])):
                fast=tracer._FieldLineSampler(*b,r,t,phi)
                reference=ReferenceSampler(*b,r,t,phi)
                points=[(.3,0,0),(1,np.pi,2*np.pi),(.7,.9,-1e-14),
                        (np.nextafter(.3,0),.7,1),(np.nextafter(1,2),1.3,2),
                        (.3-1e-8,.6,0),(1+1e-8,.6,0)]
                points.extend(zip(rng.uniform(.3,1,100),rng.uniform(0,np.pi,100),rng.uniform(-8,8,100)))
                for point in points:
                    np.testing.assert_array_equal(fast.sample(*point),reference.sample(*point))

    def test_sampler_does_not_reuse_another_or_modified_longitude_grid(self):
        b,r,t,p=fields()
        first=tracer._FieldLineSampler(*b,r,t,p)
        expected=first.sample(.6,.9,.2)
        shifted=p+.3
        second=tracer._FieldLineSampler(*b,r,t,shifted)
        self.assertNotEqual(expected,second.sample(.6,.9,.2))
        p[:]+=.1
        reopened=tracer._FieldLineSampler(*b,r,t,p)
        np.testing.assert_array_equal(reopened.sample(.6,.9,.2),ReferenceSampler(*b,r,t,p).sample(.6,.9,.2))

    def test_longitude_preparation_occurs_once_per_branch(self):
        b,r,t,p=fields()
        with mock.patch.object(np,"unwrap",wraps=np.unwrap) as unwrap:
            points=tracer.trace_one_line(tracer.sph_to_cart(.95,.7,.2),-1,*b,r,t,p,.01,100)
        self.assertGreater(len(points),10)
        self.assertEqual(unwrap.call_count,1)

    def test_internal_branches_and_strengths_are_bit_identical_to_reference(self):
        b,r,t,p=fields()
        reference=ReferenceSampler(*b,r,t,p)
        for theta in (.5,1.2,2.3):
            for direction in (-1,1):
                seed=tracer.sph_to_cart(.98,theta,.63)
                expected=tracer.trace_one_line(seed,direction,*b,r,t,p,.01,500,sampler=reference)
                actual=tracer.trace_one_line(seed,direction,*b,r,t,p,.01,500)
                np.testing.assert_array_equal(actual,expected)
                np.testing.assert_array_equal(tracer.sample_line_strengths(actual,*b,r,t,p),
                    tracer.sample_line_strengths(expected,*b,r,t,p,sampler=reference))

    def test_exterior_statuses_endpoints_and_refinements_equal_reference(self):
        b,r,t,p=fields(exterior=True)
        reference=ReferenceSampler(*b,r,t,p)
        for theta in (.3,.8,1.55,2.3):
            seed=tracer.sph_to_cart(1,theta,.2)
            br=reference.sample(1,theta,.2)[0]
            args=(seed,1 if br>0 else -1,*b,r,t,p,.012,600,8)
            expected=tracer.trace_exterior_cmb_to_cmb_arc(*args,adaptive_step=True,sampler=reference)
            actual=tracer.trace_exterior_cmb_to_cmb_arc(*args,adaptive_step=True)
            np.testing.assert_array_equal(actual[0],expected[0])
            self.assertEqual(actual[1:],expected[1:])

    def test_invalid_samples_and_null_strengths_keep_existing_behavior(self):
        b,r,t,p=fields()
        b[1][...]=np.nan
        sampler=tracer._FieldLineSampler(*b,r,t,p)
        x=tracer.sph_to_cart(.5,.5,.5)
        self.assertIsNone(tracer.interpolate_B_cartesian(x,*b,r,t,p,sampler))
        self.assertEqual(tracer.sample_line_strengths([x],*b,r,t,p),[None])

    def test_progress_is_flushed_rate_limited_and_reports_the_active_step(self):
        class Output(io.StringIO):
            flushes=0
            def flush(self): self.flushes+=1
        output=Output()
        with mock.patch.object(field_line_progress.time,"monotonic",side_effect=[0,.1,1,5.1,5.2,6]), redirect_stdout(output):
            progress=field_line_progress.TraceProgress("Tracing internal field lines",3,4000)
            progress.begin(0)
            progress.tick("forward, step 1/4000")
            progress.tick("forward, step 641/4000")
            progress.begin(1)
            progress.finish(2)
        lines=output.getvalue().splitlines()
        self.assertEqual(len(lines),3)
        self.assertIn("0/3 seeds completed",lines[1])
        self.assertIn("step 641/4000",lines[1])
        self.assertIn("3/3 seeds completed; retained 2 lines",lines[-1])
        self.assertEqual(output.flushes,3)

    def test_cached_return_connections_match_fresh_combined_and_separate_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/"input";make_run(source)
            out=root/"out"
            args=["--folder",str(source),"--out",str(out),"--incremental",
                  "--cache-dir",str(root/"cache"),"--field-line-mode","both",
                  "--line-seeds","4","--line-max-steps","600",
                  "--external-nr","48","--external-rmax","10"]
            with redirect_stdout(io.StringIO()): calypso.main(args)
            filenames=("B_lines.json","B_lines_shell.json","B_lines_exterior_poloidal.json")
            original={name:(out/name).read_bytes() for name in filenames}
            combined=json.loads(original["B_lines.json"])
            exterior=json.loads(original["B_lines_exterior_poloidal.json"])
            self.assertTrue(exterior)
            self.assertTrue(any(line.get("return_connection_status")=="connected" for line in exterior))
            for line in exterior: self.assertIn(line,combined)
            # An additional diagnostic rebuilds the bundle but reuses all tracing.
            with redirect_stdout(io.StringIO()) as reused: calypso.main([*args,"--emf"])
            self.assertIn("Reuse calculation: connect_exterior_return_footpoints",reused.getvalue())
            self.assertEqual(original,{name:(out/name).read_bytes() for name in filenames})
            validate_bundle(out)

    def test_interrupt_preserves_previous_bundle_and_reuses_completed_transforms(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/"input";make_run(source)
            out=root/"out"
            args=["--folder",str(source),"--out",str(out),"--incremental",
                  "--cache-dir",str(root/"cache"),"--line-seeds","4","--line-max-steps","600"]
            with redirect_stdout(io.StringIO()):
                calypso.main([*args,"--skip-field-lines"])
            (out/"view.DTV2").write_text("preserved view")
            before={p.name:p.read_bytes() for p in out.iterdir() if p.is_file()}
            with redirect_stdout(io.StringIO()) as interrupted, \
                 mock.patch.object(tracer,"boundary_limited_rk4_step",side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt): calypso.main(args)
            self.assertEqual(before,{p.name:p.read_bytes() for p in out.iterdir() if p.is_file()})
            self.assertNotIn("seeds completed; retained",interrupted.getvalue())
            with redirect_stdout(io.StringIO()) as resumed: calypso.main(args)
            self.assertIn("Reuse calculation: read_restart",resumed.getvalue())
            self.assertEqual(resumed.getvalue().count("Reuse calculation: synthesize_spectra"),4)
            self.assertIn("Tracing internal field lines: 0/",resumed.getvalue())
            self.assertIn("seeds completed; retained",resumed.getvalue())
            self.assertEqual((out/"view.DTV2").read_text(),"preserved view")
            validate_bundle(out)
            with redirect_stdout(io.StringIO()) as unchanged: calypso.main(args)
            self.assertIn("skipped",unchanged.getvalue())


if __name__=="__main__": unittest.main()
