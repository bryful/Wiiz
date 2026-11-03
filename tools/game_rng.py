"""ROM-independent RNG state step and the two observed scaling algorithms."""


def next_byte(counter, accumulator):
    if not 0 <= counter <= 255 or not 0 <= accumulator <= 255:
        raise ValueError('RNG state must contain two bytes')
    following = (counter + 1) & 255
    value = (accumulator + counter + int(following == 0)) & 255
    return dict(counter=following, accumulator=value, value=value)


def scaled_roll(game, counter, accumulator, limit):
    if game not in ('wiz1', 'wiz2', 'wiz3') or not 1 <= limit <= 255:
        raise ValueError('Unsupported game or roll limit')
    state = next_byte(counter, accumulator)
    if game == 'wiz1':
        # Preserve the original byte-wise carry behavior. Replacing this with
        # a wide multiply changes some results (e.g. limit 255).
        upper, lower, value = state['accumulator'], state['counter'], 0
        for _ in range(16):
            carry, value = value >> 7, (value << 1) & 255
            carry, lower = lower >> 7, ((lower << 1) | carry) & 255
            carry, upper = upper >> 7, ((upper << 1) | carry) & 255
            if carry:
                total = value + limit
                value = total & 255
                if total > 255:
                    lower = (lower + 1) & 255
        value = upper
    else:
        value = (state['value'] * limit) >> 8
    return dict(state, value=value)
