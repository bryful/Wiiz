"""Item replacement and supported SP transitions, independent of CPU execution.

Inputs are a confirmed activation and a supplied RNG byte, not a probability.
UI, context selection, complete stat rebuilding and unknown SP bodies are outside
this module's scope. The returned character commits the selected inventory slot.
"""
from game_rules import special_power_core


def replacement(game, item, flags, roll, mode='spell'):
    if game not in ('wiz1', 'wiz2', 'wiz3') or mode not in ('spell', 'sp'):
        raise ValueError('Unsupported game or use mode')
    if not 0 <= flags <= 255:
        raise ValueError('Expected inventory flag byte')
    threshold = item['stats']['break_raw']
    inclusive = mode == 'sp' and game != 'wiz1'
    consumes_rng = inclusive or threshold != 255
    if consumes_rng and (not isinstance(roll, int) or not 0 <= roll <= 255):
        raise ValueError('An RNG byte is required')
    changes = roll <= threshold if inclusive else (threshold == 255 or roll < threshold)
    new_flags = flags
    if changes:
        if inclusive:
            new_flags = ((flags & 0x40) | 0x20) if game == 'wiz2' else flags & 0x60
        else:
            new_flags = flags | 0x20
    return dict(replaced=changes, item_id=item['stats']['replacement_item_id'] if changes else item['id'],
                flags=new_flags, rng_consumed=consumes_rng)


def sp_eligibility(game, item, class_id):
    if game not in ('wiz1', 'wiz2', 'wiz3') or not 0 <= class_id < 8:
        raise ValueError('Unsupported game/class')
    power = item.get('special_power')
    sp_id = item['stats']['special_power_raw']
    has_sp = power is not None and sp_id != 0 and (game != 'wiz1' or sp_id < 128)
    class_allowed = bool(item['stats']['equip_mask'] & (1 << class_id))
    return dict(has_sp=has_sp, class_allowed=class_allowed, eligible=has_sp and class_allowed)


def resolve_sp(game, character, item, slot=0, roll=None):
    """Confirmed SP activation for a supported body; returns a new state.

    The old item's body runs even when that item becomes its replacement first.
    Inventory count, prompts and derived combat stats are left to the caller.
    """
    if len(character) < 0x60 or not 0 <= slot < 8:
        raise ValueError('Invalid character record or inventory slot')
    class_id = character[0x0b] if game == 'wiz1' else (character[0x0a] >> 2) & 7
    eligibility = sp_eligibility(game, item, class_id)
    flag_offset, id_offset = ((0x4c + slot, 0x54 + slot) if game == 'wiz1' else (0x43 + slot, 0x4b + slot))
    if character[id_offset] != item['id']:
        raise ValueError('Selected inventory item differs from supplied item')
    if not eligibility['eligible']:
        return dict(activated=False, character=bytes(character), inventory=dict(item_id=item['id'], flags=character[flag_offset], replaced=False, rng_consumed=False), carry_into_body=None)
    definition = item['special_power']
    if not definition['executable_core']:
        raise ValueError('SP body is not implemented; no state change has been applied')
    inventory = replacement(game, item, character[flag_offset], roll, 'sp')
    # W2's CMP carry survives the activation helper. W3's inline dispatcher
    # performs further arithmetic and enters these handlers with carry clear.
    carry = int(roll >= item['stats']['break_raw']) if game == 'wiz2' else 0
    result = bytearray(special_power_core(character, definition, carry_in=carry))
    result[flag_offset], result[id_offset] = inventory['flags'], inventory['item_id']
    return dict(activated=True, character=bytes(result), inventory=inventory, carry_into_body=carry)


def metadata(game, item):
    threshold = item['stats']['break_raw']
    ordinary = '必ず変化（乱数なし）' if threshold == 255 else f'r < {threshold}'
    sp = f'r ≤ {threshold}' if game != 'wiz1' else ordinary
    return dict(normal=dict(condition=ordinary, threshold=threshold, comparison='lt_or_ff',
                            flag_rule='flags | 0x20'),
                sp=dict(condition=sp, threshold=threshold, comparison='le' if game != 'wiz1' else 'lt_or_ff',
                        flag_rule={'wiz1': 'flags | 0x20', 'wiz2': '(flags & 0x40) | 0x20', 'wiz3': 'flags & 0x60'}[game]),
                replacement_item_id=item['stats']['replacement_item_id'],
                source_cpu_addresses=dict(normal={'wiz1': 0xbf9d, 'wiz2': 0xb348, 'wiz3': 0xb19a}[game],
                                          sp_class_gate={'wiz1': 0xb675, 'wiz2': 0xb1ab, 'wiz3': 0xafff}[game]),
                scope='通常使用は呪文効果の実行が選ばれた後、SPは発動確認後の処理。rは0〜255の乱数バイト。')
