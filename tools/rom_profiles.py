"""Offsets verified for the user's three ROM revisions only."""
import hashlib
from rom_identity import inspect_wizardry

PROFILES = {
    '38da945c819fab8255a1b3b8ad7c7ea162b51e8f09584501626d0aaa14a92e9a':
        dict(id='wiz1', title='Wizardry FC I', count=101, mapper=1),
    '6b1d9ca5bbe9be4f7d12c2de2dd8115f99c1cc2de3944787d2d5c2959cc116c0':
        dict(id='wiz2', title='Wizardry FC II', count=78, mapper=4,
             code_bank=4, code_base=0x8000, routine=0x9f00,
             unknown_table=0x9f9b, pointer_table_file=0xc010, record_base=0xc110,
             pointer_bias=28, chr_bias=32, attributes=32,
             id_address=0x28e, origin=[0x5c, 0x53], prg_banks=[4, 6],
             names_file=0x14010),
    'b5f7dff95724e1a9f5c486b15f53aae4124266c18abb1218a48a73a539149212':
        dict(id='wiz3', title='Wizardry FC III', count=90, mapper=4,
             code_bank=11, code_base=0xa000, routine=0xaaf2,
             unknown_table=0xab7c, pointer_table_file=0x16be6, record_base=0x14010,
             pointer_bias=0, chr_bias=48, attributes=0,
             id_address=0x2ae, origin=[4, 0x43], prg_banks=[10, 11],
             names_file=0xc010),
}


def profile_for(rom):
    sha = hashlib.sha256(rom).hexdigest()
    if sha in PROFILES:
        return PROFILES[sha]
    identity=inspect_wizardry(rom)
    if not identity['known_layout']:
        raise ValueError('Wizardry program recognized, but fixed analysis offsets are unverified')
    return next(p for p in PROFILES.values() if p['id']==f"wiz{identity['scenario']}")
