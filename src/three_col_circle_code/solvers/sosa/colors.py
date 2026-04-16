from enum import IntEnum


class Color(IntEnum):
    """Semantic color identifiers for SOSA list-coloring."""

    RED = 0
    GREEN = 1
    BLUE = 2


RED_MASK = 1 << Color.RED
GREEN_MASK = 1 << Color.GREEN
BLUE_MASK = 1 << Color.BLUE
ALL_COLOR_MASK = RED_MASK | GREEN_MASK | BLUE_MASK

COLOR_ORDER = (Color.RED, Color.GREEN, Color.BLUE)
COLOR_MASK_ORDER = (RED_MASK, GREEN_MASK, BLUE_MASK)
COLOR_NAMES = {
    Color.RED: "red",
    Color.GREEN: "green",
    Color.BLUE: "blue",
}
COLOR_TO_MASK = {
    Color.RED: RED_MASK,
    Color.GREEN: GREEN_MASK,
    Color.BLUE: BLUE_MASK,
}


def color_to_mask(color: Color) -> int:
    """Return the bitmask representation for one color."""
    return COLOR_TO_MASK[color]


def mask_to_colors(mask: int) -> tuple[Color, ...]:
    """Return the colors present in a mask in canonical SOSA order."""
    return tuple(color for color in COLOR_ORDER if mask & color_to_mask(color))


def mask_to_names(mask: int) -> tuple[str, ...]:
    """Return the human-readable names present in a mask."""
    return tuple(COLOR_NAMES[color] for color in mask_to_colors(mask))
