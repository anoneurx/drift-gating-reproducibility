//! Cache replacement policies needed by the frozen drift-gating study.

use crate::trace::PAGE_SPACE;
use std::collections::BTreeSet;

const NONE: u32 = u32::MAX;

/// Doubly-linked lists with O(1) arbitrary-page removal, matching C++ `std::list`
/// plus a per-page iterator/location array.
struct Ls {
    head: Vec<u32>,
    tail: Vec<u32>,
    next: Vec<u32>,
    prev: Vec<u32>,
    loc: Vec<i16>,
    len: Vec<usize>,
}

impl Ls {
    fn new(lists: usize) -> Self {
        Self {
            head: vec![NONE; lists],
            tail: vec![NONE; lists],
            next: vec![NONE; PAGE_SPACE],
            prev: vec![NONE; PAGE_SPACE],
            loc: vec![-1; PAGE_SPACE],
            len: vec![0; lists],
        }
    }

    #[inline]
    fn loc(&self, page: u32) -> i16 {
        self.loc[page as usize]
    }

    #[inline]
    fn len(&self, list: usize) -> usize {
        self.len[list]
    }

    fn push_front(&mut self, list: usize, page: u32) {
        let old = self.head[list];
        self.next[page as usize] = old;
        self.prev[page as usize] = NONE;
        if old == NONE {
            self.tail[list] = page;
        } else {
            self.prev[old as usize] = page;
        }
        self.head[list] = page;
        self.loc[page as usize] = list as i16;
        self.len[list] += 1;
    }

    #[allow(dead_code)]
    fn push_back(&mut self, list: usize, page: u32) {
        let old = self.tail[list];
        self.prev[page as usize] = old;
        self.next[page as usize] = NONE;
        if old == NONE {
            self.head[list] = page;
        } else {
            self.next[old as usize] = page;
        }
        self.tail[list] = page;
        self.loc[page as usize] = list as i16;
        self.len[list] += 1;
    }

    fn remove(&mut self, page: u32) {
        let list = self.loc[page as usize] as usize;
        let p = self.prev[page as usize];
        let n = self.next[page as usize];
        if p == NONE {
            self.head[list] = n;
        } else {
            self.next[p as usize] = n;
        }
        if n == NONE {
            self.tail[list] = p;
        } else {
            self.prev[n as usize] = p;
        }
        self.loc[page as usize] = -1;
        self.len[list] -= 1;
    }

    #[inline]
    fn back(&self, list: usize) -> u32 {
        self.tail[list]
    }

    #[inline]
    fn front(&self, list: usize) -> u32 {
        self.head[list]
    }

    /// Oldest to newest (C++ iterates the list in reverse).
    fn ordered(&self, list: usize) -> Vec<u32> {
        let mut out = Vec::with_capacity(self.len[list]);
        let mut p = self.tail[list];
        while p != NONE {
            out.push(p);
            p = self.prev[p as usize];
        }
        out
    }
}

pub trait Policy {
    fn access(&mut self, page: u32) -> bool;
    fn resident(&mut self) -> Vec<u32> {
        Vec::new()
    }
    fn load(&mut self, _pages: &[u32], _counts: &[u16]) {}
}

pub fn make_candidate(id: usize, capacity: usize, age_refs: u64) -> Box<dyn Policy> {
    match id {
        0 => Box::new(Lru::new(capacity, false)),
        1 => Box::new(LfuA::new(capacity, age_refs)),
        2 => Box::new(TwoQ::new(capacity)),
        3 => Box::new(Lru::new(capacity, true)),
        4 => Box::new(S3Fifo::new(capacity)),
        _ => Box::new(Arc::new(capacity)),
    }
}

struct Lru {
    s: Ls,
    capacity: usize,
    mru: bool,
}

impl Lru {
    fn new(capacity: usize, mru: bool) -> Self {
        Self {
            s: Ls::new(1),
            capacity,
            mru,
        }
    }
}

impl Policy for Lru {
    fn access(&mut self, page: u32) -> bool {
        if self.s.loc(page) >= 0 {
            self.s.remove(page);
            self.s.push_front(0, page);
            return true;
        }
        if self.s.len(0) >= self.capacity {
            let victim = if self.mru {
                self.s.front(0)
            } else {
                self.s.back(0)
            };
            self.s.remove(victim);
        }
        self.s.push_front(0, page);
        false
    }

    fn resident(&mut self) -> Vec<u32> {
        self.s.ordered(0)
    }

    fn load(&mut self, pages: &[u32], _counts: &[u16]) {
        let start = pages.len().saturating_sub(self.capacity);
        for &page in &pages[start..] {
            self.s.push_front(0, page);
        }
    }
}

struct LfuA {
    set: BTreeSet<(u32, u64, u32)>,
    cnt: Vec<u32>,
    last: Vec<u64>,
    resident: Vec<u8>,
    t: u64,
    age: u64,
    n: usize,
    capacity: usize,
}

impl LfuA {
    fn new(capacity: usize, age: u64) -> Self {
        Self {
            set: BTreeSet::new(),
            cnt: vec![0; PAGE_SPACE],
            last: vec![0; PAGE_SPACE],
            resident: vec![0; PAGE_SPACE],
            t: 0,
            age,
            n: 0,
            capacity,
        }
    }
}

impl Policy for LfuA {
    fn access(&mut self, page: u32) -> bool {
        self.t += 1;
        let p = page as usize;
        if self.age != 0 && self.t % self.age == 0 {
            let pages: Vec<u32> = self.set.iter().map(|e| e.2).collect();
            self.set.clear();
            for q in pages {
                let q = q as usize;
                self.cnt[q] = std::cmp::max(1, self.cnt[q] / 2);
                self.set.insert((self.cnt[q], self.last[q], q as u32));
            }
        }
        if self.resident[p] != 0 {
            self.set.remove(&(self.cnt[p], self.last[p], page));
            self.cnt[p] += 1;
            self.last[p] = self.t;
            self.set.insert((self.cnt[p], self.last[p], page));
            return true;
        }
        if self.n >= self.capacity {
            let victim = *self.set.iter().next().unwrap();
            self.set.remove(&victim);
            self.resident[victim.2 as usize] = 0;
            self.n -= 1;
        }
        self.cnt[p] = 1;
        self.last[p] = self.t;
        self.resident[p] = 1;
        self.n += 1;
        self.set.insert((1, self.t, page));
        false
    }

    fn resident(&mut self) -> Vec<u32> {
        let mut v = Vec::with_capacity(self.set.len());
        for e in &self.set {
            v.push((e.1, e.2));
        }
        v.sort_unstable();
        v.into_iter().map(|x| x.1).collect()
    }

    fn load(&mut self, pages: &[u32], counts: &[u16]) {
        let start = pages.len().saturating_sub(self.capacity);
        for i in start..pages.len() {
            let q = pages[i] as usize;
            self.cnt[q] = std::cmp::max(1, counts[i] as u32);
            self.last[q] = {
                self.t += 1;
                self.t
            };
            self.resident[q] = 1;
            self.n += 1;
            self.set.insert((self.cnt[q], self.last[q], pages[i]));
        }
    }
}

struct TwoQ {
    s: Ls,
    capacity: usize,
    kin: usize,
    kout: usize,
}

impl TwoQ {
    fn new(capacity: usize) -> Self {
        Self {
            s: Ls::new(3),
            capacity,
            kin: std::cmp::max(1, capacity / 4),
            kout: std::cmp::max(1, capacity / 2),
        }
    }

    fn reclaim(&mut self) {
        if self.s.len(0) + self.s.len(1) < self.capacity {
            return;
        }
        if self.s.len(0) > self.kin || self.s.len(1) == 0 {
            let victim = self.s.back(0);
            self.s.remove(victim);
            self.s.push_front(2, victim);
            if self.s.len(2) > self.kout {
                let victim = self.s.back(2);
                self.s.remove(victim);
            }
        } else {
            let victim = self.s.back(1);
            self.s.remove(victim);
        }
    }
}

impl Policy for TwoQ {
    fn access(&mut self, page: u32) -> bool {
        let list = self.s.loc(page);
        if list == 1 {
            self.s.remove(page);
            self.s.push_front(1, page);
            return true;
        }
        if list == 0 {
            return true;
        }
        if list == 2 {
            self.s.remove(page);
            self.reclaim();
            self.s.push_front(1, page);
            return false;
        }
        self.reclaim();
        self.s.push_front(0, page);
        false
    }

    fn resident(&mut self) -> Vec<u32> {
        let mut out = self.s.ordered(0);
        out.extend(self.s.ordered(1));
        out
    }

    fn load(&mut self, pages: &[u32], counts: &[u16]) {
        let start = pages.len().saturating_sub(self.capacity);
        for i in start..pages.len() {
            let list = if counts[i] >= 2 { 1 } else { 0 };
            self.s.push_front(list, pages[i]);
        }
    }
}

struct S3Fifo {
    s: Ls,
    capacity: usize,
    small: usize,
    main: usize,
    freq: Vec<u8>,
}

impl S3Fifo {
    fn new(capacity: usize) -> Self {
        let small = std::cmp::max(1, (0.10 * capacity as f64).round() as usize);
        Self {
            s: Ls::new(3),
            capacity,
            small,
            main: capacity - small,
            freq: vec![0; PAGE_SPACE],
        }
    }

    fn evict_main(&mut self) {
        loop {
            let page = self.s.back(1);
            self.s.remove(page);
            let f = self.freq[page as usize];
            if f > 0 {
                self.freq[page as usize] = f - 1;
                self.s.push_front(1, page);
            } else {
                return;
            }
        }
    }

    fn evict(&mut self) {
        if self.s.len(0) + self.s.len(1) < self.capacity {
            return;
        }
        if self.s.len(0) >= self.small || self.s.len(1) == 0 {
            let page = self.s.back(0);
            self.s.remove(page);
            let f = self.freq[page as usize];
            if f > 1 {
                self.freq[page as usize] = 0;
                if self.s.len(1) >= self.main {
                    self.evict_main();
                }
                self.s.push_front(1, page);
            } else {
                self.s.push_front(2, page);
                if self.s.len(2) > self.main {
                    let victim = self.s.back(2);
                    self.s.remove(victim);
                }
            }
        } else {
            self.evict_main();
        }
    }
}

impl Policy for S3Fifo {
    fn access(&mut self, page: u32) -> bool {
        let list = self.s.loc(page);
        if list == 0 || list == 1 {
            self.freq[page as usize] = std::cmp::min(3, self.freq[page as usize] + 1);
            return true;
        }
        let from_ghost = list == 2;
        if from_ghost {
            self.s.remove(page);
        }
        self.evict();
        self.freq[page as usize] = 0;
        self.s.push_front(if from_ghost { 1 } else { 0 }, page);
        false
    }
}

struct Arc {
    s: Ls,
    capacity: usize,
    p: f64,
}

impl Arc {
    fn new(capacity: usize) -> Self {
        Self {
            s: Ls::new(4),
            capacity,
            p: 0.0,
        }
    }

    fn replace(&mut self, page: u32) {
        let in_b2 = self.s.loc(page) == 3;
        if self.s.len(0) > 0
            && (self.s.len(0) as f64 > self.p || (in_b2 && self.s.len(0) as f64 == self.p))
        {
            let victim = self.s.back(0);
            self.s.remove(victim);
            self.s.push_front(2, victim);
        } else if self.s.len(1) > 0 {
            let victim = self.s.back(1);
            self.s.remove(victim);
            self.s.push_front(3, victim);
        }
    }
}

impl Policy for Arc {
    fn access(&mut self, page: u32) -> bool {
        let list = self.s.loc(page);
        if list == 0 || list == 1 {
            self.s.remove(page);
            self.s.push_front(1, page);
            return true;
        }
        if list == 2 {
            let cap = self.capacity as f64;
            let delta = (self.s.len(3) as f64 / self.s.len(2) as f64).max(1.0);
            self.p = (self.p + delta).min(cap);
            self.replace(page);
            self.s.remove(page);
            self.s.push_front(1, page);
            return false;
        }
        if list == 3 {
            let delta = (self.s.len(2) as f64 / self.s.len(3) as f64).max(1.0);
            self.p = (self.p - delta).max(0.0);
            self.replace(page);
            self.s.remove(page);
            self.s.push_front(1, page);
            return false;
        }
        let l1 = self.s.len(0) + self.s.len(2);
        if l1 >= self.capacity {
            if self.s.len(0) < self.capacity {
                let victim = self.s.back(2);
                self.s.remove(victim);
                self.replace(page);
            } else {
                let victim = self.s.back(0);
                self.s.remove(victim);
            }
        } else {
            let total = l1 + self.s.len(1) + self.s.len(3);
            if total >= self.capacity {
                if total >= 2 * self.capacity && self.s.len(3) > 0 {
                    let victim = self.s.back(3);
                    self.s.remove(victim);
                }
                self.replace(page);
            }
        }
        self.s.push_front(0, page);
        false
    }
}
