//! Synthetic workload generation for the frozen seed-5001 study.

use crate::rng::Rng;

const NP: usize = 1 << 18;

#[derive(Clone)]
pub struct Trace {
    pub scenario: String,
    pub seed: u64,
    pub refs: Vec<u32>,
    pub bounds: Vec<usize>,
}

impl Trace {
    fn new(scenario: &str, seed: u64) -> Self {
        Self {
            scenario: scenario.to_string(),
            seed,
            refs: Vec::new(),
            bounds: Vec::new(),
        }
    }
}

struct ZipfSampler {
    cdf: Vec<f64>,
    perm: Vec<u32>,
}

impl ZipfSampler {
    fn new(n: usize, s: f64, rng: &mut Rng, permute: bool) -> Self {
        let mut cdf = vec![0.0f64; n];
        let mut sum = 0.0f64;
        for i in 0..n {
            sum += 1.0 / ((i + 1) as f64).powf(s);
            cdf[i] = sum;
        }
        for c in &mut cdf {
            *c /= sum;
        }
        let mut perm: Vec<u32> = (0..n as u32).collect();
        if permute {
            rng.shuffle(&mut perm);
        }
        Self { cdf, perm }
    }

    fn draw(&self, rng: &mut Rng) -> u32 {
        let x = rng.u();
        let mut k = 0usize;
        while k < self.cdf.len() && self.cdf[k] < x {
            k += 1;
        }
        if k >= self.perm.len() {
            k = self.perm.len() - 1;
        }
        self.perm[k]
    }
}

enum Gen {
    Loop {
        base: u32,
        pos: u32,
    },
    Zipf {
        base: u32,
        sampler: ZipfSampler,
    },
    HotScan {
        base: u32,
        pos: u32,
    },
    Window {
        base: u32,
        t: u64,
    },
    Uniform {
        base: u32,
    },
    Matrix {
        base: u32,
        i: u32,
    },
    HashJoin {
        base: u32,
        pos: u32,
    },
    BTree {
        base: u32,
        step: i32,
        sampler: ZipfSampler,
    },
    Sort {
        base: u32,
        k: u32,
        ptr: [u32; 16],
    },
    Kv {
        base: u32,
        pos: u32,
        burst: i32,
        sampler: ZipfSampler,
    },
}

impl Gen {
    fn next(&mut self, rng: &mut Rng) -> u32 {
        match self {
            Gen::Loop { base, pos } => {
                let v = *base + (*pos % 1200);
                *pos = pos.wrapping_add(1);
                v
            }
            Gen::Zipf { base, sampler } => *base + sampler.draw(rng),
            Gen::HotScan { base, pos } => {
                if rng.u() < 0.7 {
                    *base + rng.n(600)
                } else {
                    let v = *base + 600 + (*pos % 20000);
                    *pos = pos.wrapping_add(1);
                    v
                }
            }
            Gen::Window { base, t } => {
                let s = ((*t / 40) % 20000) as u32;
                *t += 1;
                *base + (s + rng.n(700)) % 20000
            }
            Gen::Uniform { base } => *base + rng.n(4000),
            Gen::Matrix { base, i } => {
                let row = *i % 40;
                let col = (*i / 40) % 40;
                *i += 1;
                *base + row * 40 + col
            }
            Gen::HashJoin { base, pos } => {
                if rng.u() < 0.5 {
                    let v = *base + (*pos % 20000);
                    *pos = pos.wrapping_add(1);
                    v
                } else {
                    *base + 20000 + rng.n(1500)
                }
            }
            Gen::BTree {
                base,
                step,
                sampler,
            } => {
                let s = *step % 3;
                *step += 1;
                match s {
                    0 => *base,
                    1 => *base + 1 + rng.n(40),
                    _ => *base + 41 + sampler.draw(rng),
                }
            }
            Gen::Sort { base, k, ptr } => {
                let run = *k % 16;
                *k += 1;
                let p = ptr[run as usize];
                ptr[run as usize] = p.wrapping_add(1);
                *base + run * 2500 + (p % 2500)
            }
            Gen::Kv {
                base,
                pos,
                burst,
                sampler,
            } => {
                if *burst > 0 {
                    *burst -= 1;
                    let v = *base + 6000 + (*pos % 20000);
                    *pos = pos.wrapping_add(1);
                    v
                } else {
                    if rng.u() < 0.0005 {
                        *burst = 300;
                    }
                    *base + sampler.draw(rng)
                }
            }
        }
    }
}

fn mk_prim(t: usize, rng: &mut Rng) -> Gen {
    match t {
        0 => Gen::Loop { base: 0, pos: 0 },
        1 => Gen::Zipf {
            base: 2000,
            sampler: ZipfSampler::new(8000, 0.9, rng, true),
        },
        2 => Gen::HotScan {
            base: 10000,
            pos: 0,
        },
        3 => Gen::Window { base: 32000, t: 0 },
        _ => Gen::Uniform { base: 54000 },
    }
}

fn mk_kern(t: usize, rng: &mut Rng) -> Gen {
    match t {
        0 => Gen::Matrix { base: 70000, i: 0 },
        1 => Gen::HashJoin {
            base: 72000,
            pos: 0,
        },
        2 => Gen::BTree {
            base: 95000,
            step: 0,
            sampler: ZipfSampler::new(3000, 0.8, rng, true),
        },
        3 => Gen::Sort {
            base: 100000,
            k: 0,
            ptr: [0; 16],
        },
        _ => Gen::Kv {
            base: 60000,
            pos: 0,
            burst: 0,
            sampler: ZipfSampler::new(6000, 0.99, rng, true),
        },
    }
}

pub fn gen_stable(prim: usize, seed: u64) -> Trace {
    let mut rng = Rng::new(seed);
    let mut g = mk_prim(prim, &mut rng);
    let mut t = Trace::new("stable", seed);
    for _ in 0..300_000 {
        t.refs.push(g.next(&mut rng));
    }
    t
}

pub fn gen_phased(kind: &str, seed: u64) -> Trace {
    let mut rng = Rng::new(seed);
    let mut t = Trace::new(kind, seed);
    let mut gens: Vec<Gen> = Vec::new();
    let mut seq: Vec<usize>;
    let length: usize;
    let mut ramp: usize = 0;

    if kind == "composite" {
        for k in 0..5 {
            gens.push(mk_kern(k, &mut rng));
        }
        seq = vec![0, 1, 2, 3, 4];
        rng.shuffle(&mut seq);
        length = 100_000;
    } else {
        for k in 0..5 {
            gens.push(mk_prim(k, &mut rng));
        }
        if kind == "recurring" {
            let a = rng.n(5) as usize;
            let b2 = ((a + 1 + rng.n(4) as usize) % 5) as usize;
            seq = vec![a, b2, a, b2, a, b2];
            length = 80_000;
        } else {
            let mut prev: i32 = -1;
            seq = Vec::with_capacity(6);
            for _ in 0..6 {
                let c = loop {
                    let c = rng.n(5) as i32;
                    if c != prev {
                        break c;
                    }
                };
                seq.push(c as usize);
                prev = c;
            }
            length = 100_000;
            if kind == "gradual" {
                ramp = 40_000;
            }
        }
    }

    for i in 0..seq.len() {
        if i > 0 {
            t.bounds.push(i * length);
        }
        for j in 0..length {
            let mut g = seq[i];
            if ramp != 0 {
                if i + 1 < seq.len() && j >= length - ramp / 2 {
                    if rng.u() < (j - (length - ramp / 2)) as f64 / ramp as f64 {
                        g = seq[i + 1];
                    }
                } else if i > 0 && j < ramp / 2 {
                    if rng.u() >= 0.5 + j as f64 / ramp as f64 {
                        g = seq[i - 1];
                    }
                }
            }
            t.refs.push(gens[g].next(&mut rng));
        }
    }
    t
}

pub fn build_traces(seed: u64, nstable: usize, nper: usize) -> Vec<Trace> {
    let mut traces = Vec::with_capacity(nstable * 5 + nper * 4);
    for prim in 0..5 {
        for k in 0..nstable {
            traces.push(gen_stable(prim, seed + prim as u64 * 100 + k as u64));
        }
    }
    let scenarios = ["abrupt", "gradual", "recurring", "composite"];
    for (s, kind) in scenarios.iter().enumerate() {
        for k in 0..nper {
            traces.push(gen_phased(kind, seed + 1000 * (s as u64 + 1) + k as u64));
        }
    }
    traces
}

pub const PAGE_SPACE: usize = NP;
