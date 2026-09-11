"""Native binary layout, half-Chebyshev geometry and full-sphere exports."""
from contextlib import redirect_stdout
import gzip
import io
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import calypso_data as native
from tools import convert_calypso_to_viewer as converter
from tools.viewer_bundle import validate_bundle
from test_calypso_converter import make_run


def binary_fixture(fields, counts, step=400, endian="<", compressed=False, bad_offset=False):
    """Independent native MPI writer: each rank stores complete Fortran columns."""
    integer = lambda values: struct.pack(endian + "q" * len(values), *values)
    counts = list(map(int, counts))
    columns = np.concatenate(list(fields.values()), axis=1)
    ranks, offset = [], 0
    for count in counts:
        ranks.append(columns[offset:offset+count].astype(endian+"f8").tobytes(order="F"))
        offset += count
    assert offset == len(columns)
    header = [b"XINU" if endian == "<" else b"UNIX", integer([len(counts)]),
              integer([step]), struct.pack(endian+"d", .4), struct.pack(endian+"d", .001),
              integer(np.cumsum(counts)), integer([len(fields)]),
              integer([a.shape[1] for a in fields.values()]),
              b"".join(name.encode().ljust(255,b" ") for name in fields)]
    if not compressed:
        return b"".join(header+ranks)
    packed = [gzip.compress(rank,mtime=0) for rank in ranks]
    offsets = np.cumsum([len(rank) for rank in packed])
    if bad_offset: offsets[0] += 1
    return b"".join(gzip.compress(block,mtime=0) for block in header+[integer(offsets)]) + b"".join(packed)


def half_sphere_fixture(root, index=7):
    radius = np.sin(np.arange(1,9)*np.pi/16)
    make_run(root,"full",radius=radius)
    source = native.read_merged_ascii(root/"rst.0.fst")
    (root/"rst.0.fst").unlink()
    (root/f"rst.{index}.fsb.gz").write_bytes(binary_fixture(source["fields"],source["counts"],compressed=True))
    control = root/"control_MHD"
    control.write_text(re.sub(r"radial_grid_type_ctl explicit.*?end array r_layer",
        "radial_grid_type_ctl half_Chebyshev\nnum_fluid_grid_ctl 8\n"
        "fluid_core_size_ctl 1\nICB_to_CMB_ratio_ctl 0",control.read_text(),flags=re.S))
    return radius


class CalypsoBinaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_rank_local_fortran_columns_and_byte_order(self):
        fields={"velocity":np.arange(15,dtype=float).reshape(5,3)+.25,
                "temperature":np.arange(5,dtype=float)[:,None]-2,
                "unused":np.arange(10,dtype=float).reshape(5,2)*11}
        for endian in ("<",">"):
            for compressed in (False,True):
                path=self.root/("rst.7.fsb.gz" if compressed else "rst.7.fsb")
                path.write_bytes(binary_fixture(fields,[2,0,3],endian=endian,compressed=compressed))
                result=native.read_merged_binary(path,selected=("velocity","temperature"))
                self.assertEqual(result["step"],400)
                self.assertEqual(result["field_names"],list(fields))
                self.assertEqual(set(result["fields"]),{"velocity","temperature"})
                np.testing.assert_array_equal(result["counts"],[2,0,3])
                for name in result["fields"]:
                    np.testing.assert_array_equal(result["fields"][name],fields[name])

    def test_corrupt_offsets_checksums_truncation_and_trailing_data_rejected(self):
        fields={"temperature":np.arange(4,dtype=float)[:,None]}
        good=binary_fixture(fields,[1,3],compressed=True)
        corrupt=bytearray(good);corrupt[-8]^=1
        for content in (good[:-5],bytes(corrupt),good+b"extra",
                        binary_fixture(fields,[1,3],compressed=True,bad_offset=True)):
            path=self.root/"rst.7.fsb.gz";path.write_bytes(content)
            with self.assertRaises(ValueError): native.read_merged_binary(path)
        plain=binary_fixture(fields,[1,3])
        for content in (b"FAIL"+plain[4:],plain[:-1],plain+b"extra"):
            path=self.root/"rst.7.fsb";path.write_bytes(content)
            with self.assertRaises(ValueError): native.read_merged_binary(path)
        fields["temperature"][0,0]=np.nan
        path.write_bytes(binary_fixture(fields,[1,3]))
        with self.assertRaisesRegex(ValueError,"Nonfinite"): native.read_merged_binary(path)

    def test_half_chebyshev_grid_has_no_spectral_zero_and_detects_full_sphere(self):
        expected=half_sphere_fixture(self.root)
        records,_=native.read_controls(self.root/"control_MHD")
        grid=native.grid_from_controls(records)
        np.testing.assert_allclose(grid["r"],expected,rtol=0,atol=2e-16)
        self.assertEqual((grid["icb"],grid["cmb"]),(0,7))
        self.assertTrue(grid["center"] and grid["full_sphere"])
        with self.assertRaisesRegex(ValueError,"conflicts"):
            native.grid_from_controls(records,"shell")
        # The grid type determines geometry even without a velocity BC entry.
        self.assertTrue(native.grid_from_controls([r for r in records if r[1]!="bc_velocity"])["full_sphere"])
        for key,value in (("max_radius_ctl","2"),("increment_cheby_ctl","2")):
            with self.assertRaisesRegex(ValueError,"explicit native"):
                native.grid_from_controls([*records,((),key,[value])])
        changed=[(scope,key,[".35"] if key=="icb_to_cmb_ratio_ctl" else value)
                 for scope,key,value in records]
        with self.assertRaisesRegex(ValueError,"zero ICB"):
            native.grid_from_controls(changed)

    def test_binary_full_sphere_conversion_centre_diagnostics_and_cache(self):
        source=self.root/"run";radius=half_sphere_fixture(source)
        out=self.root/"out"
        args=["--folder",str(source),"--out",str(out),"--cache-dir",str(self.root/"cache"),
              "--incremental","--skip-field-lines"]
        with redirect_stdout(io.StringIO()): converter.main(args)
        meta=json.loads((out/"metadata.json").read_text())
        coords=json.loads((out/"coordinates.json").read_text())
        self.assertEqual(meta["state_number"],7)
        self.assertEqual(meta["calypso"]["simulation_step"],400)
        self.assertEqual(meta["r_icb"],0)
        np.testing.assert_allclose(coords["r"],np.r_[0,radius])
        shape=(meta["nr"],meta["ntheta"],meta["nphi"])
        field=lambda name:np.fromfile(out/meta["fields"][name],dtype="<f4").reshape(shape)
        r=np.asarray(coords["r"])[:,None,None]
        th=np.asarray(coords["theta"])[None,:,None]
        ph=np.asarray(coords["phi"])[None,None,:]
        expected=1-r*r+.1*r*np.sin(th)*np.cos(ph)
        np.testing.assert_allclose(field("T"),expected,rtol=1e-6,atol=1e-7)
        np.testing.assert_allclose(field("Babs"),np.sqrt(1.2),rtol=1e-6)
        np.testing.assert_allclose(field("Uabs")[0],0,atol=1e-7)
        before=(out/"Br_volume.f32").read_bytes()
        (out/"view.DTV2").write_text("retained view")
        with redirect_stdout(io.StringIO()) as log: converter.main([*args,"--emf","--induction"])
        self.assertIn("Reuse calculation: read_restart",log.getvalue())
        self.assertEqual(before,(out/"Br_volume.f32").read_bytes())
        self.assertEqual((out/"view.DTV2").read_text(),"retained view")
        validate_bundle(out)
        with redirect_stdout(io.StringIO()) as log: converter.main([*args,"--emf","--induction"])
        self.assertIn("skipped",log.getvalue())

    def test_explicit_native_zero_icb_is_the_separate_centre(self):
        make_run(self.root,"full")
        records,_=native.read_controls(self.root/"control_MHD")
        changed=[]
        for scope,key,args in records:
            if key=="bc_velocity": continue
            if key=="boundaries_ctl" and args[0]=="ICB": args=["ICB","0"]
            changed.append((scope,key,args))
        grid=native.grid_from_controls(changed)
        self.assertTrue(grid["full_sphere"])
        self.assertEqual(grid["icb"],0)
        self.assertGreater(grid["r"][0],0)
        with self.assertRaisesRegex(ValueError,"with_center"):
            native.grid_from_controls([r for r in changed if r[1]!="sph_coef_type_ctl"])

    def test_duplicate_formats_require_explicit_selection_and_sequence_uses_indices(self):
        source=self.root/"run";half_sphere_fixture(source)
        original=source/"rst.7.fsb.gz"
        (source/"rst.8.fsb.gz").write_bytes(original.read_bytes())
        args=converter.build_arg_parser().parse_args(["--folder",str(source),
               "--sequence-first","7","--sequence-last","8"])
        records,_=native.read_controls(source/"control_MHD")
        self.assertEqual([converter.restart_step(p) for p in converter.discover_states(args,source/"control_MHD",records)],[7,8])
        (source/"rst.7.fst").write_text("duplicate")
        with self.assertRaisesRegex(ValueError,"Two Calypso restarts"):
            converter.discover_states(args,source/"control_MHD",records)


FULL_SAMPLE=os.environ.get("CALYPSO_FULL_SPHERE_SAMPLE_DIR")


@unittest.skipUnless(FULL_SAMPLE,"set CALYPSO_FULL_SPHERE_SAMPLE_DIR for the supplied full-sphere restart")
class SuppliedFullSphereTests(unittest.TestCase):
    def test_real_48_rank_grid_header_and_independent_centre_offset(self):
        root=Path(FULL_SAMPLE)
        records,_=native.read_controls(root/"control_MHD")
        grid=native.grid_from_controls(records)
        path=root/"rst_48/rst.99.fsb.gz"
        spectra,centres,header=native.read_restart(path,grid)
        self.assertEqual(header["step"],990000)
        self.assertAlmostEqual(header["time"],2.475,places=9)
        self.assertEqual(spectra["velocity"].shape,(192,1024,3))
        self.assertTrue(grid["full_sphere"])
        # Independently address T at the sole extra centre node in raw bytes.
        data=gzip.decompress(path.read_bytes())
        stack=struct.unpack_from("<48q",data,36)
        counts=np.diff([0,*stack])
        self.assertEqual(stack[-1],192*1024+1)
        owner=np.flatnonzero(counts%192)[0]
        self.assertEqual(counts[owner]%192,1)
        start=36+48*8+8+7*8+7*255+48*8
        offset=start+int(sum(counts[:owner]))*15*8
        offset+=(int(counts[owner])*3+int(counts[owner])-1)*8
        stored_temperature=struct.unpack_from("<d",data,offset)[0]
        self.assertEqual(float(centres["temperature"][0]),stored_temperature)
        self.assertAlmostEqual(stored_temperature,.40226777,places=7)


if __name__=="__main__": unittest.main()
