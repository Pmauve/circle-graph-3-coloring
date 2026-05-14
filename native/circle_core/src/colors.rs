pub type ColorMask = u8;

pub const RED: ColorMask = 0b001;
pub const GREEN: ColorMask = 0b010;
pub const BLUE: ColorMask = 0b100;
pub const ALL_COLORS: ColorMask = RED | GREEN | BLUE;

pub fn color_count(mask: ColorMask) -> u32 {
    (mask & ALL_COLORS).count_ones()
}

pub fn singleton_color(mask: ColorMask) -> Option<u8> {
    match mask & ALL_COLORS {
        RED => Some(1),
        GREEN => Some(2),
        BLUE => Some(3),
        _ => None,
    }
}

pub fn color_bit(color: u8) -> ColorMask {
    match color {
        1 => RED,
        2 => GREEN,
        3 => BLUE,
        _ => 0,
    }
}

pub fn iter_colors(mask: ColorMask) -> impl Iterator<Item = u8> {
    (1..=3).filter(move |&color| mask & color_bit(color) != 0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detects_singletons() {
        assert_eq!(singleton_color(RED), Some(1));
        assert_eq!(singleton_color(GREEN), Some(2));
        assert_eq!(singleton_color(BLUE), Some(3));
        assert_eq!(singleton_color(RED | BLUE), None);
    }

    #[test]
    fn iterates_colors_in_order() {
        assert_eq!(iter_colors(RED | BLUE).collect::<Vec<_>>(), vec![1, 3]);
    }
}
