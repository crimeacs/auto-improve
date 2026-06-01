// auto-improve · live climb plot
//
// Reads a results/<tag>.tsv (written by improve.py) and animates the score climbing:
// green = a kept win, red = a discarded (reset) candidate, gold = a crash/retry. It
// re-reads the file as the loop runs, so you can watch it climb live in real time.
//
//   cargo run --release -- ../results/email.tsv     # a specific run
//   cargo run --release -- ../results               # latest *.tsv in a dir
//   cargo run --release                             # latest *.tsv in ./results
//   cargo run --release -- --dump ../results/email.tsv   # headless: print + exit

use macroquad::prelude::*;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

const BG: Color = Color { r: 0.027, g: 0.031, b: 0.047, a: 1.0 };
const ACCENT: Color = Color { r: 0.40, g: 0.76, b: 0.99, a: 1.0 };
const GOLD: Color = Color { r: 0.99, g: 0.74, b: 0.39, a: 1.0 };
const RED: Color = Color { r: 0.98, g: 0.45, b: 0.52, a: 1.0 };
const GREEN: Color = Color { r: 0.46, g: 0.85, b: 0.60, a: 1.0 };
const DIM: Color = Color { r: 0.52, g: 0.58, b: 0.70, a: 1.0 };
const INK: Color = Color { r: 0.88, g: 0.91, b: 0.97, a: 1.0 };

struct Row { iter: f64, score: f64, status: String, desc: String }
struct Climb { tag: String, rows: Vec<Row>, ymin: f64, ymax: f64, sig: u128 }

fn mtime(p: &Path) -> u128 {
    fs::metadata(p).and_then(|m| m.modified()).ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_nanos()).unwrap_or(0)
}

/// Resolve the target TSV: a .tsv path as given, else the latest *.tsv in a dir.
fn resolve(arg: Option<&str>) -> Option<PathBuf> {
    let p = arg.map(PathBuf::from).unwrap_or_else(|| PathBuf::from("results"));
    if p.extension().map(|e| e == "tsv").unwrap_or(false) {
        return p.exists().then_some(p);
    }
    let mut best: Option<(PathBuf, u128)> = None;
    for e in fs::read_dir(&p).ok()?.flatten() {
        let f = e.path();
        if f.extension().map(|x| x == "tsv").unwrap_or(false) {
            let t = mtime(&f);
            if best.as_ref().map(|(_, b)| t >= *b).unwrap_or(true) { best = Some((f, t)); }
        }
    }
    best.map(|(f, _)| f)
}

fn load(path: &Path) -> Climb {
    let content = fs::read_to_string(path).unwrap_or_default();
    let mut lines = content.lines();
    let header: Vec<&str> = lines.next().unwrap_or("").split('\t').collect();
    let col = |n: &str| header.iter().position(|h| *h == n);
    let (ci, cs, cst, cd) = (
        col("iteration").unwrap_or(0),
        col("score").unwrap_or(2),
        col("status").unwrap_or(4),
        col("description").unwrap_or(5),
    );
    let mut rows = Vec::new();
    let mut cur = 0.0; // shown score climbs on baseline/keep, holds on discard/crash
    for line in lines {
        if line.trim().is_empty() { continue; }
        let f: Vec<&str> = line.split('\t').collect();
        let g = |i: usize| f.get(i).copied().unwrap_or("");
        let it: f64 = g(ci).parse().unwrap_or(0.0);
        let sc: f64 = g(cs).trim_start_matches('+').parse().unwrap_or(0.0);
        let st = g(cst).trim().to_string();
        if st == "baseline" || st == "keep" { cur = sc; }
        rows.push(Row { iter: it, score: cur, status: st, desc: g(cd).trim().to_string() });
    }
    // show only the last run if a file accumulated several
    if let Some(lb) = rows.iter().rposition(|r| r.status == "baseline") {
        if lb > 0 { rows.drain(0..lb); }
    }
    let ys: Vec<f64> = rows.iter().map(|r| r.score).filter(|s| *s > 0.0).collect();
    let (mut ymin, mut ymax) = (0.0, 100.0);
    if !ys.is_empty() {
        let mn = ys.iter().cloned().fold(f64::MAX, f64::min);
        let mx = ys.iter().cloned().fold(f64::MIN, f64::max);
        ymin = (mn - 6.0).max(0.0);
        ymax = (mx + 6.0).min(100.0);
    }
    let tag = path.file_stem().and_then(|s| s.to_str()).unwrap_or("run").to_string();
    Climb { tag, rows, ymin, ymax, sig: mtime(path) }
}

fn conf() -> Conf {
    Conf { window_title: "auto-improve · climb".to_string(),
           window_width: 900, window_height: 560, high_dpi: true, ..Default::default() }
}

#[macroquad::main(conf)]
async fn main() {
    let args: Vec<String> = std::env::args().collect();
    let dump = args.iter().any(|a| a == "--dump");
    let path_arg = args.iter().skip(1).find(|a| !a.starts_with("--")).map(|s| s.as_str());

    let Some(path) = resolve(path_arg) else {
        eprintln!("no .tsv found — pass a results/<tag>.tsv or a directory to scan");
        return;
    };
    let mut climb = load(&path);

    if dump {
        let base = climb.rows.first().map(|r| r.score as i64).unwrap_or(0);
        let cur = climb.rows.last().map(|r| r.score as i64).unwrap_or(0);
        println!("tag={} rows={} climb {}->{}", climb.tag, climb.rows.len(), base, cur);
        for r in &climb.rows { println!("  it{:>2} {:>3} {}", r.iter as i64, r.score as i64, r.status); }
        return;
    }

    let mut last_scan = get_time();
    loop {
        if is_key_pressed(KeyCode::Escape) || is_key_pressed(KeyCode::Q) { break; }
        if get_time() - last_scan > 0.5 {
            last_scan = get_time();
            if mtime(&path) != climb.sig { climb = load(&path); }
        }
        clear_background(BG);
        draw_climb(&climb, get_time() as f32 * 3.0);
        next_frame().await;
    }
}

/// Truncate `s` to fit within `max_w` px at font size `fs`, adding an ellipsis if cut.
fn fit_text(s: &str, fs: u16, max_w: f32) -> String {
    if measure_text(s, None, fs, 1.0).width <= max_w {
        return s.to_string();
    }
    let mut out = String::new();
    for ch in s.chars() {
        if measure_text(&format!("{out}{ch}…"), None, fs, 1.0).width > max_w {
            break;
        }
        out.push(ch);
    }
    out.push('…');
    out
}

fn draw_climb(c: &Climb, t: f32) {
    let (sw, sh) = (screen_width(), screen_height());
    draw_text("auto-improve", 36.0, 46.0, 30.0, INK);
    draw_text(&format!("{} · score vs iteration · live", c.tag), 36.0, 70.0, 16.0, DIM);
    if c.rows.is_empty() {
        draw_text("waiting for the loop to write results…", 36.0, 112.0, 18.0, DIM);
        return;
    }
    let base = c.rows.first().map(|r| r.score as i64).unwrap_or(0);
    let cur = c.rows.last().map(|r| r.score as i64).unwrap_or(0);
    draw_text(&format!("{base} -> {cur}"), sw - 188.0, 58.0, 34.0, GREEN);

    let (x0, y0) = (84.0, 100.0);
    let (cw, chh) = (sw - 130.0, sh - 190.0);
    let maxx = (c.rows.len().saturating_sub(1)).max(1) as f64;
    let px = |it: f64, s: f64| -> Vec2 {
        vec2(x0 + (it / maxx) as f32 * cw,
             y0 + chh - ((s - c.ymin) / (c.ymax - c.ymin).max(1.0)) as f32 * chh)
    };

    let ax = Color::new(0.28, 0.32, 0.40, 1.0);
    draw_line(x0, y0, x0, y0 + chh, 1.0, ax);
    draw_line(x0, y0 + chh, x0 + cw, y0 + chh, 1.0, ax);
    draw_text(&format!("{}", c.ymax as i64), 40.0, y0 + 6.0, 14.0, DIM);
    draw_text(&format!("{}", c.ymin as i64), 40.0, y0 + chh, 14.0, DIM);

    for w in c.rows.windows(2) {
        let a = px(w[0].iter, w[0].score);
        let b = px(w[1].iter, w[1].score);
        draw_line(a.x, a.y, b.x, b.y, 2.4, ACCENT);
    }
    let n = c.rows.len();
    for (i, r) in c.rows.iter().enumerate() {
        let p = px(r.iter, r.score);
        let col = match r.status.as_str() {
            "keep" | "baseline" => GREEN, "discard" => RED, "crash" => GOLD, _ => ACCENT,
        };
        let rad = if i == n - 1 { 7.0 } else { 4.5 };
        draw_circle(p.x, p.y, rad * 1.8, Color::new(col.r, col.g, col.b, 0.12));
        draw_circle(p.x, p.y, rad, col);
        if i == n - 1 {
            let pulse = (t.sin() * 0.5 + 0.5) * 6.0;
            draw_circle_lines(p.x, p.y, rad + 3.0 + pulse, 1.6, Color::new(col.r, col.g, col.b, 0.5));
        }
    }

    let last = c.rows.last().unwrap();
    let (badge, bc) = match last.status.as_str() {
        "keep" => ("KEPT", GREEN), "discard" => ("RESET", RED), "crash" => ("RETRY", GOLD),
        "baseline" => ("START", ACCENT), _ => ("DONE", GREEN),
    };
    draw_text(badge, x0, sh - 38.0, 18.0, bc);
    let dx = x0 + 66.0;
    let desc = fit_text(&last.desc, 16, sw - 24.0 - dx);   // measure + ellipsis, never overflow
    draw_text(&desc, dx, sh - 38.0, 16.0, INK);
    draw_text("green keep · red reset · gold retry        Esc quit", x0, sh - 14.0, 13.0, DIM);
}
