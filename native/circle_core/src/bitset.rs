#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BitSet {
    len: usize,
    words: Vec<u64>,
}

impl BitSet {
    pub fn full(len: usize) -> Self {
        let mut words = vec![u64::MAX; len.div_ceil(64)];
        clear_trailing_bits(len, &mut words);
        Self { len, words }
    }

    pub fn empty(len: usize) -> Self {
        Self {
            len,
            words: vec![0; len.div_ceil(64)],
        }
    }

    pub fn len(&self) -> usize {
        self.len
    }

    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    pub fn get(&self, index: usize) -> bool {
        assert!(index < self.len);
        (self.words[index / 64] & (1u64 << (index % 64))) != 0
    }

    pub fn set(&mut self, index: usize, value: bool) {
        assert!(index < self.len);
        let mask = 1u64 << (index % 64);
        if value {
            self.words[index / 64] |= mask;
        } else {
            self.words[index / 64] &= !mask;
        }
    }

    pub fn clear(&mut self, index: usize) {
        self.set(index, false);
    }

    pub fn count_ones(&self) -> usize {
        self.words
            .iter()
            .map(|word| word.count_ones() as usize)
            .sum()
    }

    pub fn iter_ones(&self) -> BitSetIter<'_> {
        BitSetIter {
            bitset: self,
            word_index: 0,
            current: self.words.first().copied().unwrap_or(0),
        }
    }
}

pub struct BitSetIter<'a> {
    bitset: &'a BitSet,
    word_index: usize,
    current: u64,
}

impl Iterator for BitSetIter<'_> {
    type Item = usize;

    fn next(&mut self) -> Option<Self::Item> {
        loop {
            if self.current != 0 {
                let bit = self.current.trailing_zeros() as usize;
                self.current &= self.current - 1;
                let index = self.word_index * 64 + bit;
                if index < self.bitset.len {
                    return Some(index);
                }
            }
            self.word_index += 1;
            if self.word_index >= self.bitset.words.len() {
                return None;
            }
            self.current = self.bitset.words[self.word_index];
        }
    }
}

fn clear_trailing_bits(len: usize, words: &mut [u64]) {
    if len == 0 {
        return;
    }
    let used_bits = len % 64;
    if used_bits == 0 {
        return;
    }
    if let Some(last) = words.last_mut() {
        *last &= (1u64 << used_bits) - 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn creates_empty_and_full_sets() {
        let empty = BitSet::empty(70);
        assert_eq!(empty.count_ones(), 0);

        let full = BitSet::full(70);
        assert_eq!(full.count_ones(), 70);
        assert!(full.get(69));
    }

    #[test]
    fn sets_and_clears_bits() {
        let mut bits = BitSet::empty(10);
        bits.set(3, true);
        bits.set(7, true);
        bits.clear(3);

        assert!(!bits.get(3));
        assert!(bits.get(7));
        assert_eq!(bits.count_ones(), 1);
    }

    #[test]
    fn iterates_set_bits_in_order() {
        let mut bits = BitSet::empty(130);
        bits.set(129, true);
        bits.set(0, true);
        bits.set(64, true);

        assert_eq!(bits.iter_ones().collect::<Vec<_>>(), vec![0, 64, 129]);
    }

    #[test]
    fn masks_trailing_bits_for_full_set() {
        let full = BitSet::full(65);

        assert_eq!(full.count_ones(), 65);
        assert_eq!(full.iter_ones().last(), Some(64));
    }
}
