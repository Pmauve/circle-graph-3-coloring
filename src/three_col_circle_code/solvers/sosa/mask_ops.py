from collections.abc import Iterator


def iter_mask_indices(mask: int) -> Iterator[int]:
    """Yield the set-bit indices of a non-negative integer mask in ascending order."""
    current_mask = mask
    while current_mask:
        least_significant_bit = current_mask & -current_mask
        yield least_significant_bit.bit_length() - 1
        current_mask ^= least_significant_bit


def mask_is_singleton(mask: int) -> bool:
    """Return whether the mask contains exactly one set bit."""
    return mask != 0 and (mask & (mask - 1)) == 0
