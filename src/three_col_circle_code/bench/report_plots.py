import colorsys
import hashlib


def solver_target_color(solver_target: str) -> str:
    """Map each solver variant label to one stable report color."""
    digest = hashlib.blake2b(solver_target.encode("utf-8"), digest_size=2).digest()
    hue = int.from_bytes(digest, "big") / 65535.0
    red, green, blue = colorsys.hls_to_rgb(hue, 0.46, 0.62)
    return f"#{int(red * 255):02x}{int(green * 255):02x}{int(blue * 255):02x}"
