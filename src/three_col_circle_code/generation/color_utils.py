from typing import Iterable, Mapping


def validate_num_colors(num_colors: int) -> None:
    """Validate a positive palette size."""
    if num_colors < 1:
        raise ValueError("num_colors must be at least 1")


def color_bit(color: int) -> int:
    """Return the bit mask for one-based color identifiers."""
    if color < 1:
        raise ValueError("color must be at least 1")
    return 1 << (color - 1)


def full_color_mask(num_colors: int) -> int:
    """Return the mask containing all colors in the palette 1..num_colors."""
    validate_num_colors(num_colors)
    return (1 << num_colors) - 1


def available_color_mask(
    colors: Mapping[int, int],
    neighbors: Iterable[int],
    num_colors: int,
) -> int:
    """Return the mask of colors unused by the given neighbors."""
    mask = full_color_mask(num_colors)
    for neighbor in neighbors:
        color = colors[neighbor]
        if not 1 <= color <= num_colors:
            raise ValueError(
                f"neighbor {neighbor!r} has color {color!r} outside palette 1..{num_colors}"
            )
        mask &= ~color_bit(color)
    return mask


def colors_from_mask(mask: int, num_colors: int) -> tuple[int, ...]:
    """Convert a bit mask to ascending one-based color identifiers."""
    validate_num_colors(num_colors)
    return tuple(color for color in range(1, num_colors + 1) if mask & color_bit(color))


def available_colors(
    colors: Mapping[int, int],
    neighbors: Iterable[int],
    num_colors: int,
) -> tuple[int, ...]:
    """Return ascending colors unused by the given neighbors."""
    return colors_from_mask(
        available_color_mask(colors, neighbors, num_colors),
        num_colors,
    )
