"""Paired continual-RSI study for auto-improve with and without Self-Improvement Memory.

Per pair k: a source run builds a memory on the source email; two target runs improve the
target email from the same start with matched iterations and candidates, one without memory
and one inheriting the source memory. The endpoint is an independent final comparison of the
two target results: the pairwise judge in both orders (votes counted, ties kept), plus absolute
scores (3 evaluation runs each). A known-bad probe checks the judge first.
"""
import concurrent.futures as cf, json, os, shutil, subprocess, sys

AI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AI)
import improve  # noqa: E402

CRIT = os.path.join(AI, "criteria", "cold-email-quality.md")
SRC = os.path.join(AI, "examples", "cold-email.txt")
TGT = os.path.join(D, "target-email.txt")
ITERS, CANDS, EVAL_RUNS, PAIRS = int(os.environ.get("ITERS", 5)), 3, 1, int(os.environ.get("PAIRS", 3))


def repo_with(name, src):
    r = os.path.join(D, "runs", name)
    shutil.rmtree(r, ignore_errors=True)
    os.makedirs(r)
    shutil.copy(src, os.path.join(r, "artifact.txt"))
    for c in (["init", "-q"], ["add", "-A"], ["-c", "user.name=s", "-c", "user.email=s@x", "commit", "-q", "-m", "seed"]):
        subprocess.run(["git", "-C", r] + c, check=True, capture_output=True)
    return r


def improve_run(name, src, sim=None):
    r = repo_with(name, src)
    cmd = [sys.executable, os.path.join(AI, "improve.py"), "--artifact", os.path.join(r, "artifact.txt"),
           "--criteria", CRIT, "--tag", name, "--max-iterations", str(ITERS), "--candidates", str(CANDS),
           "--eval-runs", str(EVAL_RUNS), "--threshold", "99"] + (["--sim", sim] if sim else [])
    env = {**os.environ, "RESULTS_DIR": os.path.join(D, "results"), "GIT_AUTHOR_NAME": "s", "GIT_AUTHOR_EMAIL": "s@x",
           "GIT_COMMITTER_NAME": "s", "GIT_COMMITTER_EMAIL": "s@x"}
    p = subprocess.run(["timeout", "-k", "30", "2400"] + cmd, capture_output=True, text=True, env=env)
    open(os.path.join(D, "runs", f"{name}.log"), "w").write(p.stdout + p.stderr)
    return open(os.path.join(r, "artifact.txt")).read()


def votes(a, b, crit):
    """Pairwise in both orders. Returns (votes for a, votes for b)."""
    p1 = improve._pairwise_text_one(a, b, crit)
    p2 = improve._pairwise_text_one(b, a, crit)
    return int(p1["winner"] == "A") + int(p2["winner"] == "B"), int(p1["winner"] == "B") + int(p2["winner"] == "A")


def pair(k):
    crit = open(CRIT).read()
    sim = os.path.join(D, "results", f"src{k}.sim.json")
    if os.path.exists(sim):
        os.remove(sim)
    improve_run(f"src{k}", SRC, sim)
    tsim = os.path.join(D, "results", f"tgt{k}-sim.sim.json")
    shutil.copy(sim, tsim)
    with cf.ThreadPoolExecutor(2) as ex:
        fa = ex.submit(improve_run, f"tgt{k}-nosim", TGT)
        fb = ex.submit(improve_run, f"tgt{k}-sim", TGT, tsim)
        a, b = fa.result(), fb.result()
    va, vb = votes(a, b, crit)
    sa, _ = improve.evaluate(a, crit, runs=3)
    sb, _ = improve.evaluate(b, crit, runs=3)
    mem = json.load(open(sim))
    return {"pair": k, "votes_nosim": va, "votes_sim": vb, "score_nosim": sa, "score_sim": sb,
            "source_memory_attempts": sum(len(p["attempts"]) for p in mem["problems"].values()),
            "source_memory_problems": len(mem["problems"])}


if __name__ == "__main__":
    os.makedirs(os.path.join(D, "results"), exist_ok=True)
    crit = open(CRIT).read()
    tgt = open(TGT).read()
    base, _ = improve.evaluate(tgt, crit, runs=3)
    bad = "hi\n\nbuy our thing. it is good. call me. asdf asdf asdf\n"
    bad_score, _ = improve.evaluate(bad, crit, runs=3)
    print(json.dumps({"target_baseline": base, "known_bad_probe": bad_score}), flush=True)
    if bad_score > 50:
        sys.exit("judge failed the known-bad probe (>50); stopping")
    with cf.ThreadPoolExecutor(PAIRS) as ex:
        rows = list(ex.map(pair, range(1, PAIRS + 1)))
    out = {"design": {"iterations": ITERS, "candidates": CANDS, "eval_runs": EVAL_RUNS, "pairs": PAIRS,
                      "mutator": improve.MUTATOR_MODEL, "evaluator": improve.EVALUATOR_MODEL},
           "target_baseline": base, "known_bad_probe": bad_score, "pairs": rows}
    json.dump(out, open(os.path.join(D, "study.json"), "w"), indent=1)
    for r in rows:
        print(json.dumps(r), flush=True)
