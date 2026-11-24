//! Deterministic RNG compatibility layer for the frozen C++ simulator.

const N: usize = 312;
const M: usize = 156;
const MATRIX_A: u64 = 0xB5026F5AA96619E9;
const UPPER_MASK: u64 = 0xFFFFFFFF80000000;
const LOWER_MASK: u64 = 0x7FFFFFFF;
const INIT_MULT: u64 = 6364136223846793005;

/// Bit-compatible port of `std::mt19937_64` as seeded by libstdc++.
pub struct Mt19937_64 {
    state: [u64; N],
    index: usize,
}

impl Mt19937_64 {
    pub fn new(seed: u64) -> Self {
        let mut s = Self {
            state: [0; N],
            index: N,
        };
        s.seed(seed);
        s
    }

    fn seed(&mut self, seed: u64) {
        self.state[0] = seed;
        for i in 1..N {
            let prev = self.state[i - 1];
            self.state[i] = INIT_MULT
                .wrapping_mul(prev ^ (prev >> 62))
                .wrapping_add(i as u64);
        }
        self.index = N;
    }

    fn twist(&mut self) {
        for i in 0..(N - M) {
            let x = (self.state[i] & UPPER_MASK) | (self.state[i + 1] & LOWER_MASK);
            self.state[i] = self.state[i + M] ^ (x >> 1) ^ if x & 1 != 0 { MATRIX_A } else { 0 };
        }
        for i in (N - M)..(N - 1) {
            let x = (self.state[i] & UPPER_MASK) | (self.state[i + 1] & LOWER_MASK);
            self.state[i] =
                self.state[i + M - N] ^ (x >> 1) ^ if x & 1 != 0 { MATRIX_A } else { 0 };
        }
        let x = (self.state[N - 1] & UPPER_MASK) | (self.state[0] & LOWER_MASK);
        self.state[N - 1] = self.state[M - 1] ^ (x >> 1) ^ if x & 1 != 0 { MATRIX_A } else { 0 };
        self.index = 0;
    }

    pub fn next_u64(&mut self) -> u64 {
        if self.index >= N {
            self.twist();
        }
        let mut y = self.state[self.index];
        self.index += 1;
        y ^= (y >> 29) & 0x5555555555555555;
        y ^= (y << 17) & 0x71D67FFFEDA60000;
        y ^= (y << 37) & 0xFFF7EEE000000000;
        y ^= y >> 43;
        y
    }
}

/// Frozen simulator RNG: `u()` uses the top 53 bits, `n(k)` uses direct modulo.
pub struct Rng {
    pub g: Mt19937_64,
}

impl Rng {
    pub fn new(seed: u64) -> Self {
        Self {
            g: Mt19937_64::new(seed),
        }
    }

    #[inline]
    pub fn u(&mut self) -> f64 {
        (self.g.next_u64() >> 11) as f64 * (1.0 / 9007199254740992.0)
    }

    #[inline]
    pub fn n(&mut self, k: u32) -> u32 {
        (self.g.next_u64() % k as u64) as u32
    }

    /// libstdc++ `uniform_int_distribution` downscaling for a 64-bit URBG.
    /// This is Lemire's nearly divisionless sampler used by GCC 16's shuffle.
    fn uniform_nd(&mut self, range: u64) -> u64 {
        debug_assert!(range > 0);
        let threshold = range.wrapping_neg() % range;
        loop {
            let product = (self.g.next_u64() as u128) * (range as u128);
            let low = product as u64;
            if low >= threshold {
                return (product >> 64) as u64;
            }
        }
    }

    /// Bit-compatible port of libstdc++ `std::shuffle` fast path for small ranges.
    pub fn shuffle<T>(&mut self, items: &mut [T]) {
        let n = items.len();
        if n < 2 {
            return;
        }
        let mut i = 1usize;
        if n % 2 == 0 {
            let j = self.uniform_nd(2) as usize;
            items.swap(i, j);
            i += 1;
        }
        while i < n {
            let swap_range = (i + 1) as u64;
            let x = self.uniform_nd(swap_range.wrapping_mul(swap_range + 1));
            let p0 = (x / (swap_range + 1)) as usize;
            let p1 = (x % (swap_range + 1)) as usize;
            items.swap(i, p0);
            items.swap(i + 1, p1);
            i += 2;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mt_reference_vectors() {
        let mut r = Rng::new(5489);
        assert_eq!(r.g.next_u64(), 14514284786278117030);
        assert_eq!(r.g.next_u64(), 4620546740167642908);
        assert_eq!(r.g.next_u64(), 13109570281517897720);
    }

    #[test]
    fn seed_zero_reference() {
        let mut r = Rng::new(0);
        assert_eq!(r.g.next_u64(), 2947667278772165694);
    }
}
