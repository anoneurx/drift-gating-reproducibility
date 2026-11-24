//! Drift-aware controller: CUSUM trigger, KS confirmation, sampled shadows.

use crate::policies::{make_candidate, Policy};
use crate::rng::Rng;
use crate::trace::PAGE_SPACE;

#[derive(Clone)]
pub struct Params {
    pub c: usize,
    pub w: usize,
    pub b: usize,
    pub min_ks: usize,
    pub eval_delay: i32,
    pub cooldown: i32,
    pub dwell: i32,
    pub hyst: i32,
    pub age_epochs: usize,
    pub cont_every: i32,
    pub delta: f64,
    pub h: f64,
    pub alpha: f64,
    pub p: f64,
    pub warm: f64,
    pub z: f64,
    pub horizon: f64,
    pub kfrac: f64,
    pub purge: u64,
    pub ncand: usize,
    pub use_ks: bool,
    pub use_shadow: bool,
    pub use_purge: bool,
    pub use_cost: bool,
    pub gated: bool,
}

impl Default for Params {
    fn default() -> Self {
        Self {
            c: 1000,
            w: 2000,
            b: 8,
            min_ks: 100,
            eval_delay: 10,
            cooldown: 4,
            dwell: 10,
            hyst: 30,
            age_epochs: 50,
            cont_every: 10,
            delta: 0.5,
            h: 5.0,
            alpha: 1e-3,
            p: 0.2,
            warm: 0.4,
            z: 1.28,
            horizon: 50_000.0,
            kfrac: 0.0,
            purge: 20_000,
            ncand: 5,
            use_ks: true,
            use_shadow: true,
            use_purge: true,
            use_cost: true,
            gated: true,
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum State {
    Base,
    Mon,
    Wait,
    Cool,
}

#[derive(Clone, Copy)]
struct SRef {
    page: u32,
    ep: i32,
}

struct Eval {
    ok: bool,
    blk: Vec<[f64; 6]>,
    tot: Vec<f64>,
    braw: f64,
}

impl Eval {
    fn failed() -> Self {
        Self {
            ok: false,
            blk: Vec::new(),
            tot: Vec::new(),
            braw: 0.0,
        }
    }
}

fn ks_p(mut a: Vec<f64>, mut b: Vec<f64>) -> f64 {
    a.sort_by(|x, y| x.partial_cmp(y).unwrap());
    b.sort_by(|x, y| x.partial_cmp(y).unwrap());
    let mut i = 0usize;
    let mut j = 0usize;
    let mut d = 0.0f64;
    while i < a.len() && j < b.len() {
        let x = a[i].min(b[j]);
        while i < a.len() && a[i] <= x {
            i += 1;
        }
        while j < b.len() && b[j] <= x {
            j += 1;
        }
        d = d.max((i as f64 / a.len() as f64 - j as f64 / b.len() as f64).abs());
    }
    let ne = a.len() as f64 * b.len() as f64 / (a.len() + b.len()) as f64;
    let root = ne.sqrt();
    let lambda = (root + 0.12 + 0.11 / root) * d;
    let mut p = 0.0f64;
    for k in 1..=100 {
        let sign = if k & 1 != 0 { 1.0 } else { -1.0 };
        let term = 2.0 * sign * (-2.0 * k as f64 * k as f64 * lambda * lambda).exp();
        p += term;
        if term.abs() < 1e-10 {
            break;
        }
    }
    p.clamp(0.0, 1.0)
}

pub struct Da {
    p: Params,
    act: Box<dyn Policy>,
    act_id: usize,
    prev_id: i32,
    t: u64,
    age_refs: u64,
    ep: i32,
    epoch_refs: usize,
    epoch_miss: usize,
    state: State,
    first_base: bool,
    bm: Vec<f64>,
    mu: f64,
    sg: f64,
    sp: f64,
    sn: f64,
    last: Vec<u32>,
    cnt: Vec<u16>,
    last_s: Vec<u64>,
    si: u64,
    thr: u64,
    ep_ru: Vec<Vec<f64>>,
    cur_ru: Vec<f64>,
    win: Vec<SRef>,
    base_ru: Vec<f64>,
    conf_ep: i32,
    eval_at: i32,
    cool_until: i32,
    last_switch_ep: i32,
    rr: Rng,
    pub confirms: Vec<u64>,
    pub switches: usize,
    pub shadow_evals: usize,
    pub alarms: usize,
}

impl Da {
    pub fn new(p: Params) -> Self {
        let c = p.c;
        let age_refs = p.age_epochs as u64 * p.w as u64;
        let thr = (p.p * u64::MAX as f64) as u64;
        Self {
            act: make_candidate(0, c, 4 * c as u64),
            p,
            act_id: 0,
            prev_id: -1,
            t: 0,
            age_refs,
            ep: 0,
            epoch_refs: 0,
            epoch_miss: 0,
            state: State::Base,
            first_base: true,
            bm: Vec::new(),
            mu: 0.0,
            sg: 0.02,
            sp: 0.0,
            sn: 0.0,
            last: vec![0; PAGE_SPACE],
            cnt: vec![0; PAGE_SPACE],
            last_s: vec![0; PAGE_SPACE],
            si: 0,
            thr,
            ep_ru: Vec::new(),
            cur_ru: Vec::new(),
            win: Vec::new(),
            base_ru: Vec::new(),
            conf_ep: 0,
            eval_at: 0,
            cool_until: 0,
            last_switch_ep: -1000,
            rr: Rng::new(99),
            confirms: Vec::new(),
            switches: 0,
            shadow_evals: 0,
            alarms: 0,
        }
    }

    #[inline]
    fn hash(x: u32) -> u64 {
        let mut z = (x as u64).wrapping_add(0x9E3779B97F4A7C15);
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
        z ^ (z >> 31)
    }

    pub fn access(&mut self, page: u32) -> bool {
        self.t += 1;
        let idx = page as usize;
        self.last[idx] = self.t as u32;
        if self.cnt[idx] < u16::MAX {
            self.cnt[idx] += 1;
        }
        if self.age_refs != 0 && self.t % self.age_refs == 0 {
            for c in &mut self.cnt {
                *c >>= 1;
            }
        }

        let hit = self.act.access(page);
        if !hit {
            self.epoch_miss += 1;
        }

        if Self::hash(page) < self.thr {
            self.si += 1;
            let reuse = if self.last_s[idx] != 0 {
                (self.si - self.last_s[idx]) as f64
            } else {
                1e9
            };
            self.last_s[idx] = self.si;
            self.cur_ru.push(reuse);
            self.win.push(SRef { page, ep: self.ep });
        }

        self.epoch_refs += 1;
        if self.epoch_refs == self.p.w {
            self.epoch_refs = 0;
            self.end_epoch();
        }
        hit
    }

    fn recent_ru(&self, n: usize) -> Vec<f64> {
        let start = self.ep_ru.len().saturating_sub(n);
        let mut out = Vec::new();
        for bucket in &self.ep_ru[start..] {
            out.extend_from_slice(bucket);
        }
        out
    }

    fn evaluate(&mut self, start_ep: i32) -> Eval {
        let w: Vec<u32> = self
            .win
            .iter()
            .filter(|s| s.ep >= start_ep)
            .map(|s| s.page)
            .collect();
        if w.len() < 100 {
            return Eval::failed();
        }

        let cs = std::cmp::max(8, (self.p.p * self.p.c as f64).round() as usize);
        let wm = (w.len() as f64 * self.p.warm) as usize;
        let rest = w.len() - wm;
        let mut blk = vec![[0.0f64; 6]; self.p.ncand];
        let mut tot = vec![0.0f64; self.p.ncand];

        for c in 0..self.p.ncand {
            let mut pol = make_candidate(c, cs, 4 * cs as u64);
            for (i, &page) in w.iter().enumerate() {
                let hit = pol.access(page);
                if i >= wm && !hit {
                    let b = std::cmp::min(3, (i - wm) * 4 / std::cmp::max(1, rest));
                    blk[c][b] += 1.0;
                    tot[c] += 1.0;
                }
            }
        }

        let braw = (self.ep - start_ep) as f64 * self.p.w as f64 * (1.0 - self.p.warm) / 4.0;
        self.shadow_evals += 1;
        Eval {
            ok: true,
            blk,
            tot,
            braw,
        }
    }

    fn decide(&self, e: &Eval, initial: bool) -> usize {
        if !e.ok {
            return self.act_id;
        }
        if initial {
            let mut best = 0usize;
            for c in 1..self.p.ncand {
                if e.tot[c] < e.tot[best] {
                    best = c;
                }
            }
            return best;
        }

        let k = if self.p.use_cost {
            self.p.kfrac * self.p.c as f64
        } else {
            0.0
        };
        let mut best = 0.0f64;
        let mut pick = self.act_id;
        for c in 0..self.p.ncand {
            if c == self.act_id {
                continue;
            }
            let mut d = [0.0f64; 4];
            let mut mean = 0.0f64;
            for b in 0..4 {
                d[b] = e.blk[self.act_id][b] - e.blk[c][b];
                mean += d[b];
            }
            mean /= 4.0;
            let mut variance = 0.0f64;
            for b in 0..4 {
                variance += (d[b] - mean) * (d[b] - mean);
            }
            let sd = (variance / 3.0).sqrt();
            let lcb = mean - self.p.z * sd / 2.0;
            let mut score = (lcb / self.p.p / e.braw) * self.p.horizon - k;
            if c as i32 == self.prev_id && self.ep - self.last_switch_ep < self.p.hyst {
                score -= k;
            }
            if score > best {
                best = score;
                pick = c;
            }
        }
        pick
    }

    fn switch_to(&mut self, id: usize) {
        if id == self.act_id {
            return;
        }
        let mut pages = self.act.resident();
        let last = &self.last;
        pages.sort_by(|a, b| last[*a as usize].cmp(&last[*b as usize]));
        if self.p.use_purge {
            let t = self.t;
            let purge = self.p.purge;
            pages.retain(|q| t - self.last[*q as usize] as u64 <= purge);
        }
        let counts: Vec<u16> = pages.iter().map(|q| self.cnt[*q as usize]).collect();
        if std::env::var_os("DA_DEBUG").is_some() {
            eprintln!(
                "t={} ep={} {}->{} kept={}",
                self.t,
                self.ep,
                self.act_id,
                id,
                pages.len()
            );
        }
        let mut next = make_candidate(id, self.p.c, 4 * self.p.c as u64);
        next.load(&pages, &counts);
        self.act = next;
        self.prev_id = self.act_id as i32;
        self.act_id = id;
        self.last_switch_ep = self.ep;
        self.switches += 1;
    }

    fn end_epoch(&mut self) {
        let m = self.epoch_miss as f64 / self.p.w as f64;
        self.epoch_miss = 0;
        self.ep += 1;
        self.ep_ru.push(std::mem::take(&mut self.cur_ru));
        if self.ep_ru.len() > 60 {
            self.ep_ru.remove(0);
        }
        while !self.win.is_empty() && self.win[0].ep < self.ep - 45 {
            let n = std::cmp::min(20_000, self.win.len());
            self.win.drain(0..n);
        }

        if self.state == State::Base {
            self.bm.push(m);
            if self.bm.len() == self.p.b {
                let mean = self.bm.iter().sum::<f64>() / self.bm.len() as f64;
                self.mu = mean;
                let variance = self.bm.iter().map(|x| (x - mean) * (x - mean)).sum::<f64>();
                self.sg = (variance / self.bm.len() as f64).sqrt().max(0.02);
                self.sp = 0.0;
                self.sn = 0.0;
                self.base_ru = self.recent_ru(self.p.b);
                if self.first_base {
                    self.first_base = false;
                    if self.p.use_shadow {
                        let pick = {
                            let e = self.evaluate(self.ep - self.p.b as i32);
                            self.decide(&e, true)
                        };
                        self.switch_to(pick);
                    }
                }
                self.state = State::Mon;
            }
            return;
        }

        if !self.p.gated {
            if self.ep % self.p.cont_every == 0 && self.p.use_shadow {
                let pick = {
                    let e = self.evaluate(self.ep - self.p.cont_every);
                    self.decide(&e, false)
                };
                self.switch_to(pick);
            }
            return;
        }

        if self.state == State::Mon {
            let z = (m - self.mu) / self.sg;
            self.sp = (self.sp + z - self.p.delta).max(0.0);
            self.sn = (self.sn - z - self.p.delta).max(0.0);
            if self.sp > self.p.h || self.sn > self.p.h {
                self.alarms += 1;
                let mut ok = true;
                if self.p.use_ks {
                    let recent = self.recent_ru(3);
                    ok = recent.len() >= self.p.min_ks
                        && self.base_ru.len() >= self.p.min_ks
                        && ks_p(self.base_ru.clone(), recent) < self.p.alpha;
                }
                if ok {
                    self.confirms.push(self.t);
                    self.conf_ep = self.ep;
                    self.eval_at = self.ep + self.p.eval_delay;
                    self.state = State::Wait;
                } else {
                    self.sp = 0.0;
                    self.sn = 0.0;
                }
            }
            return;
        }

        if self.state == State::Wait {
            if self.ep >= self.eval_at {
                let pick = if !self.p.use_shadow {
                    loop {
                        let p = self.rr.n(4) as usize;
                        if p != self.act_id {
                            break p;
                        }
                    }
                } else {
                    let e = self.evaluate(self.conf_ep);
                    self.decide(&e, false)
                };
                if self.ep - self.last_switch_ep >= self.p.dwell {
                    self.switch_to(pick);
                }
                self.state = State::Cool;
                self.cool_until = self.ep + self.p.cooldown;
            }
            return;
        }

        if self.state == State::Cool && self.ep >= self.cool_until {
            self.state = State::Base;
            self.bm.clear();
        }
    }
}

impl Policy for Da {
    fn access(&mut self, page: u32) -> bool {
        Da::access(self, page)
    }
}
