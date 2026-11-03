"""Wiz1 JP normal-attack arithmetic, before target selection or RNG."""


def signed(value):
    value &= 255
    return value - 256 if value >= 128 else value


def base_stats(class_id, level, strength):
    level = min(level, 255)
    hit = level // 3 + 2 if class_id in (0, 2, 5, 6, 7) else level // 5
    bonus = strength - 15 if strength >= 16 else strength - 6 if strength < 6 else 0
    attacks = min(10, level // 5 + (2 if class_id == 7 else 1)) if class_id in (0, 5, 6, 7) else 1
    return dict(hit=signed(hit + bonus), attacks=attacks, damage_bonus=max(0, strength - 15))


def player_threshold(hit, ac, group=1):
    value = signed(19 + group - ac - hit)
    return min(19, max(0, value)) + 1


def enemy_threshold(level, attacker_ac, referenced_ac, parry=False):
    a = (19 + (2 if parry else 0) - referenced_ac - level) & 255
    b = (a - attacker_ac) & 255
    if b >= 128:
        value = 0 if b >= 220 or a >= 128 else 19
    else:
        value = min(b, 19)
    return value + 1


def player_priority(agility, roll):
    a = min(18, max(0, agility))
    bonus = 14-a if a >= 15 else 0 if a >= 8 else 1 if a >= 6 else 2 if a >= 4 else 3
    return max(0, min(9, roll+bonus)) + 1


def enemy_priority(roll):
    return (roll & 7) + 2
