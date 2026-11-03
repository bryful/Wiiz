"""ROM family recognition without exact-file SHA allowlisting."""
import hashlib
from pathlib import Path
import sys
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from rom_identity import inspect_wizardry,identity_profiles
from rom_profiles import profile_for
from dungeon_data import read_dungeons


class RomIdentityTests(unittest.TestCase):
    def test_original_and_parameter_roms(self):
        for n in (1,2,3):
            for suffix in ('','p'):
                path=ROOT/'.nes'/f'wiz{n}{suffix}.nes'
                with self.subTest(path=path):
                    result=inspect_wizardry(path.read_bytes())
                    self.assertEqual(result['scenario'],n)
                    self.assertTrue(result['known_layout'])
                    self.assertTrue(result['enhanced'])
                    self.assertTrue(result['verified_boot'])
                    self.assertEqual(result['enhanced_wiz1'],n==1)
                    self.assertEqual(profile_for(path.read_bytes())['id'],f'wiz{n}')

    def test_new_edits_are_not_hash_allowlisted(self):
        data=bytearray((ROOT/'.nes/wiz1.nes').read_bytes())
        original=hashlib.sha256(data).hexdigest()
        data[0x17320]^=77  # Another default-character value, not one of the supplied ROM hashes.
        data[0x23050]^=123 # CHR graphics.
        data[12:16]=b'TEST' # Reserved header bytes.
        self.assertNotEqual(hashlib.sha256(data).hexdigest(),original)
        self.assertTrue(inspect_wizardry(data)['enhanced_wiz1'])

    def test_partial_code_change_keeps_emulation_but_gates_extensions(self):
        data=bytearray((ROOT/'.nes/wiz1.nes').read_bytes())
        data[16+0x1c000]^=1
        result=inspect_wizardry(data)
        self.assertEqual(result['scenario'],1)
        self.assertFalse(result['known_layout'])
        self.assertFalse(result['enhanced_wiz1'])
        with self.assertRaises(ValueError):
            profile_for(data)

    def test_sound_patch_disables_only_enhancements(self):
        data=bytearray((ROOT/'.nes/wiz1.nes').read_bytes());data[16+0x8000]^=1
        result=inspect_wizardry(data)
        self.assertTrue(result['known_layout']);self.assertFalse(result['enhanced_wiz1'])

    def test_later_spell_patch_gates_hooks(self):
        for n in (2,3):
            data=bytearray((ROOT/'.nes'/f'wiz{n}.nes').read_bytes());data[16+0xc000]^=1
            result=inspect_wizardry(data)
            self.assertTrue(result['known_layout']);self.assertFalse(result['enhanced'])

    def test_changed_boot_code_disables_skip(self):
        for n in (2,3):
            data=bytearray((ROOT/'.nes'/f'wiz{n}.nes').read_bytes());data[16+0x8700]^=1
            result=inspect_wizardry(data)
            self.assertTrue(result['enhanced']);self.assertFalse(result['verified_boot'])

    def test_truncation_unrelated_rom_and_wrong_mapper_rejected(self):
        original=(ROOT/'.nes/wiz1.nes').read_bytes()
        for data in (original[:1000],b'garbage',original[:16]+bytes(len(original)-16)):
            with self.assertRaises(ValueError):inspect_wizardry(data)
        wrong=bytearray(original);wrong[6]=0x42
        with self.assertRaises(ValueError):inspect_wizardry(wrong)

    def test_generated_cpp_fingerprints_match_shared_data(self):
        subprocess.run([sys.executable,str(ROOT/'tools/generate_native_rom_identity.py'),'--check'],check=True)
        header=(ROOT/'app/rom_identity_data.hpp').read_text();config=identity_profiles()
        self.assertEqual(config['minimum_matches'],3)
        for p in config['profiles']:
            for value in p['signatures']+[p['fixed_sha256'],p['camp_sha256'],p['sound_sha256']]:
                self.assertIn('"'+value+'"',header)

    def test_parameter_rom_maps_match_original_maps(self):
        for n in (1,2,3):
            a=read_dungeons((ROOT/'.nes'/f'wiz{n}.nes').read_bytes())
            b=read_dungeons((ROOT/'.nes'/f'wiz{n}p.nes').read_bytes())
            for first,second in zip(a['floors'],b['floors']):
                self.assertEqual([(c['walls_raw'],c['flags_raw']) for c in first['cells']],
                                 [(c['walls_raw'],c['flags_raw']) for c in second['cells']])


if __name__=='__main__':unittest.main()
