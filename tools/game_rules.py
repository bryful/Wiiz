"""Small ROM-independent rule kernels, checked against original 6502 code.

These kernels apply already-selected effects. Inventory validation, class/level
base stats, UI, random selection and battle turn processing are outside scope.
"""
from monster_data import signed


def equipment_contribution(game, state, item, alignment_matches=True):
    """Apply ONE equipped item's combat contribution, not a full stat rebuild."""
    result = dict(state, damage=dict(state['damage']))
    stats = item['stats']
    strength = (state['strength'] + stats['strength']) & 255
    if game == 'wiz1':
        if alignment_matches:
            result['ac'] = signed((state['ac'] + stats['ac_modifier']) & 255)
            result['strength'] = signed(strength)
            result['critical_raw'] |= stats['critical_raw']
        else:
            result['ac'] = signed((state['ac'] + 1) & 255)
            result['strength'] = signed((state['strength'] - 1) & 255)
            result['critical_raw'] = 0
    else:
        # W3 guards the sign bit after the 8-bit addition; W2 doesn't.
        result['strength'] = 0 if game == 'wiz3' and strength >= 128 else signed(strength)
        result['critical_raw'] |= stats['critical_raw']
        # AC is computed elsewhere in II/III, not inside this kernel.
    if stats['kind'] == 0:
        result['damage'] = dict(count=stats['damage']['count'], sides=stats['damage']['sides'],
                                bonus=(state['damage']['bonus'] + stats['damage']['bonus']) & 255)
        if game == 'wiz1':
            result['attacks'] = max(state['attacks'], stats['minimum_attacks'])
        else:
            attacks = (state['attacks'] + stats['minimum_attacks']) & 255
            result['attacks'] = 1 if attacks == 0 or attacks >= 128 else min(attacks, 10)
    return result


def modify_ac(current, delta):
    """Battle spell AC adjustment for the observed deltas -4..+3."""
    if not -99 <= current <= 99 or not -4 <= delta <= 3:
        raise ValueError('Outside verified AC input range')
    return max(-99, min(99, current + delta))


def heal_hp(current, maximum, status_code, rolled_amount):
    """Apply a pre-rolled basic healing amount, before messages/turn handling."""
    if not 0 <= current <= maximum <= 32767 or not 0 <= rolled_amount <= 255:
        raise ValueError('Outside verified HP range')
    return current if status_code >= 5 else min(maximum, current + rolled_amount)


def special_power_core(character, definition, carry_in=None):
    """Deterministic single-character SP body after eligibility/activation.

    No item replacement/consumption, prompts, random outcomes or party effects.
    Character uses raw layout bytes so uncertain units aren't invented.
    """
    if not definition.get('executable_core'):
        raise ValueError('SP body is not implemented')
    result = bytearray(character)
    kind = definition['kind']
    if kind == 'attribute_increase':
        offset, cap = definition['character_offset'], definition['cap']
        if cap is None:
            race = result[0x0a] >> 5
            if race >= len(definition['race_caps']):
                raise ValueError('Invalid race code')
            cap = definition['race_caps'][race]
        if result[offset] < cap:
            result[offset] += 1
    elif kind == 'attribute_decrease':
        offset = definition['character_offset']
        result[offset] = max(0, result[offset] - 1)
    elif kind == 'class_ninja':
        if definition['game'] == 'wiz1':
            result[0x0b] = 7
        else:
            result[0x0a] |= 0x1c
    elif kind == 'class_lord':
        result[0x0a] = (result[0x0a] & 0xe3) | 0x18
    elif kind == 'status_code':
        result[0x23] = definition['value']
    elif kind == 'age_raw_decrease':
        if result[0x24] >= 20:
            result[0x24] -= 1
    elif kind == 'max_hp_increase':
        offset = definition['max_hp_offset']
        if carry_in not in (0, 1):
            raise ValueError('Carry must be 0 or 1')
        hp = min(32767, int.from_bytes(result[offset:offset + 2], 'little') + 1 + carry_in)
        result[offset:offset + 2] = hp.to_bytes(2, 'little')
    else:
        raise ValueError('Unsupported SP core')
    return bytes(result)
