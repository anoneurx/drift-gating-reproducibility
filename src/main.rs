//! Deterministic Rust core port of the frozen Black Wall drift-gating study.
//!
//! This crate intentionally avoids external dependencies and emits only
//! deterministic values; the C++ timings are not reproduced.

mod controller;
mod policies;
mod rng;
mod trace;

use controller::{Da, Params};
use policies::{make_candidate, Policy};
use std::env;
use std::fs::File;
use std::io::{BufWriter, Write};
use std::process::ExitCode;
use trace::{build_traces, Trace};

const RESULTS_HEADER: &str = "scenario,seed,method,miss_ratio,switches,shadow_evals";
const DETECTION_HEADER: &str =
    "scenario,seed,method,n_bounds,detected,delays,spurious,confirms,false_after_100k";

#[derive(Clone)]
struct Row {
    scenario: String,
    seed: u64,
    method: &'static str,
    miss: f64,
    switches: usize,
    evals: usize,
}

impl Row {
    fn write(&self, out: &mut impl Write) -> std::io::Result<()> {
        writeln!(
            out,
            "{},{},{},{:.5},{},{}",
            self.scenario, self.seed, self.method, self.miss, self.switches, self.evals
        )
    }
}

fn run_policy<P: Policy + ?Sized>(policy: &mut P, t: &Trace, warm: usize) -> f64 {
    let mut misses = 0usize;
    for (i, &page) in t.refs.iter().enumerate() {
        let hit = policy.access(page);
        if i >= warm && !hit {
            misses += 1;
        }
    }
    misses as f64 / (t.refs.len() - warm) as f64
}

fn write_detection(out: &mut impl Write, t: &Trace, da: &Da) -> std::io::Result<()> {
    let mut spurious = 0usize;
    let mut false_after_100k = 0usize;
    for &c in &da.confirms {
        let in_window = t
            .bounds
            .iter()
            .any(|&b| c >= b as u64 && c <= b as u64 + 30_000);
        if !in_window {
            spurious += 1;
        }
        if t.scenario == "stable" && c > 100_000 {
            false_after_100k += 1;
        }
    }

    let mut detected = 0usize;
    let mut delays = String::new();
    for &b in &t.bounds {
        let start = b as u64;
        let end = start + 30_000;
        if let Some(&c) = da.confirms.iter().find(|&&c| c >= start && c <= end) {
            detected += 1;
            delays.push_str(&(c - start).to_string());
            delays.push(';');
        }
    }

    writeln!(
        out,
        "{},{},DA,{},{},{},{},{},{}",
        t.scenario,
        t.seed,
        t.bounds.len(),
        detected,
        delays,
        spurious,
        da.confirms.len(),
        false_after_100k
    )
}

fn mean(values: impl IntoIterator<Item = f64>) -> f64 {
    let mut sum = 0.0;
    let mut n = 0usize;
    for v in values {
        sum += v;
        n += 1;
    }
    sum / n as f64
}

fn check_rows(rows: &[Row]) -> bool {
    let non_stable = rows
        .iter()
        .filter(|r| r.scenario != "stable")
        .collect::<Vec<_>>();
    let expected: Vec<(&str, &str, f64, f64)> = vec![
        ("DA", "miss", 0.45288775, 2e-6),
        ("DA", "switches", 2.3625, 1e-9),
        ("DA", "evals", 6.475, 1e-9),
        ("ContShadow", "miss", 0.42283225, 2e-6),
        ("ContShadow", "switches", 3.15, 1e-9),
        ("ContShadow", "evals", 27.3875, 1e-9),
        ("S3-FIFO", "miss", 0.468310625, 2e-6),
        ("LRU", "miss", 0.56997525, 2e-6),
    ];
    let mut ok = true;
    let ntraces = non_stable.iter().filter(|r| r.method == "DA").count();
    println!("Frozen seed-5001 non-stable aggregate check ({ntraces} traces):");
    for (method, field, want, tol) in expected {
        let selected: Vec<&&Row> = non_stable.iter().filter(|r| r.method == method).collect();
        let got = mean(selected.iter().map(|r| match field {
            "miss" => r.miss,
            "switches" => r.switches as f64,
            _ => r.evals as f64,
        }));
        let pass = (got - want).abs() <= tol;
        ok &= pass;
        println!(
            "  {:<11} {:<8} got {:.9} expected {:.9} {}",
            method,
            field,
            got,
            want,
            if pass { "PASS" } else { "FAIL" }
        );
    }
    ok
}

fn next_arg(args: &[String], i: &mut usize) -> Result<String, String> {
    *i += 1;
    args.get(*i)
        .cloned()
        .ok_or_else(|| "missing argument value".to_string())
}

fn parse_arg<T: std::str::FromStr>(
    args: &[String],
    i: &mut usize,
    label: &str,
) -> Result<T, String> {
    let value = next_arg(args, i)?;
    value.parse().map_err(|_| format!("invalid {label}"))
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    let mut seed = 5001u64;
    let mut params = Params::default();
    let mut results_path = "results.csv".to_string();
    let mut detection_path = "detection.csv".to_string();
    let mut warm = 20_000usize;
    let mut nstable = 6usize;
    let mut nper = 20usize;
    let mut check = false;
    let mut ablations = false;

    let mut i = 1usize;
    while i < args.len() {
        let arg = args[i].as_str();
        let parsed = match arg {
            "--check" => {
                check = true;
                Ok(())
            }
            "--ablations" => {
                ablations = true;
                Ok(())
            }
            "--seed" => parse_arg(&args, &mut i, "--seed").map(|v| seed = v),
            "--out" => next_arg(&args, &mut i).map(|v| results_path = v),
            "--det" => next_arg(&args, &mut i).map(|v| detection_path = v),
            "--warm" => parse_arg(&args, &mut i, "--warm").map(|v| warm = v),
            "--C" => parse_arg(&args, &mut i, "--C").map(|v| params.c = v),
            "--W" => parse_arg(&args, &mut i, "--W").map(|v| params.w = v),
            "--h" => parse_arg(&args, &mut i, "--h").map(|v| params.h = v),
            "--alpha" => parse_arg(&args, &mut i, "--alpha").map(|v| params.alpha = v),
            "--p" => parse_arg(&args, &mut i, "--p").map(|v| params.p = v),
            "--kfrac" => parse_arg(&args, &mut i, "--kfrac").map(|v| params.kfrac = v),
            "--ncand" => parse_arg(&args, &mut i, "--ncand").map(|v| params.ncand = v),
            "--z" => parse_arg(&args, &mut i, "--z").map(|v| params.z = v),
            "--H" => parse_arg(&args, &mut i, "--H").map(|v| params.horizon = v),
            "--edelay" => parse_arg(&args, &mut i, "--edelay").map(|v| params.eval_delay = v),
            "--per-scenario" => parse_arg(&args, &mut i, "--per-scenario").map(|v| nper = v),
            "--stable-per-prim" => {
                parse_arg(&args, &mut i, "--stable-per-prim").map(|v| nstable = v)
            }
            "--s3frac" => parse_arg::<f64>(&args, &mut i, "--s3frac").map(|_| ()),
            _ => Err(format!("unknown argument {arg}")),
        };
        if let Err(e) = parsed {
            eprintln!("error: {e}");
            return ExitCode::from(2);
        }
        i += 1;
    }

    if ablations {
        eprintln!("note: ablation variants are not part of this core Rust port");
    }

    let traces = build_traces(seed, nstable, nper);
    let mut rows = Vec::with_capacity(traces.len() * 4);

    let results_file = match File::create(&results_path) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("error: cannot create {results_path}: {e}");
            return ExitCode::from(1);
        }
    };
    let detection_file = match File::create(&detection_path) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("error: cannot create {detection_path}: {e}");
            return ExitCode::from(1);
        }
    };
    let mut results_out = BufWriter::new(results_file);
    let mut detection_out = BufWriter::new(detection_file);
    writeln!(results_out, "{RESULTS_HEADER}").unwrap();
    writeln!(detection_out, "{DETECTION_HEADER}").unwrap();

    for t in &traces {
        let mut lru = make_candidate(0, params.c, 4 * params.c as u64);
        let mut s3 = make_candidate(4, params.c, 4 * params.c as u64);
        let lru_miss = run_policy(lru.as_mut(), t, warm);
        let s3_miss = run_policy(s3.as_mut(), t, warm);

        let mut da = Da::new(params.clone());
        let da_miss = run_policy(&mut da, t, warm);
        let da_switches = da.switches;
        let da_evals = da.shadow_evals;
        write_detection(&mut detection_out, t, &da).unwrap();

        let mut cont = params.clone();
        cont.gated = false;
        let mut cont_shadow = Da::new(cont);
        let cont_miss = run_policy(&mut cont_shadow, t, warm);
        let cont_switches = cont_shadow.switches;
        let cont_evals = cont_shadow.shadow_evals;

        let trace_rows = [
            Row {
                scenario: t.scenario.clone(),
                seed: t.seed,
                method: "LRU",
                miss: lru_miss,
                switches: 0,
                evals: 0,
            },
            Row {
                scenario: t.scenario.clone(),
                seed: t.seed,
                method: "S3-FIFO",
                miss: s3_miss,
                switches: 0,
                evals: 0,
            },
            Row {
                scenario: t.scenario.clone(),
                seed: t.seed,
                method: "DA",
                miss: da_miss,
                switches: da_switches,
                evals: da_evals,
            },
            Row {
                scenario: t.scenario.clone(),
                seed: t.seed,
                method: "ContShadow",
                miss: cont_miss,
                switches: cont_switches,
                evals: cont_evals,
            },
        ];
        for row in &trace_rows {
            row.write(&mut results_out).unwrap();
            rows.push(row.clone());
        }
        eprint!(".");
    }
    eprintln!();
    results_out.flush().unwrap();
    detection_out.flush().unwrap();

    if check {
        if check_rows(&rows) {
            ExitCode::SUCCESS
        } else {
            ExitCode::from(1)
        }
    } else {
        ExitCode::SUCCESS
    }
}
