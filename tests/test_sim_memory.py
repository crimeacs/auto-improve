import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import improve, sim_memory


REPLY = """===CANDIDATE 1===
---FIND---
old line
---REPLACE---
new line
---DESCRIPTION---
sharper hook
---PROBLEM---
Hook Strength
---PREDICT---
hook score +2
===CANDIDATE 2===
---FIND---
b
---REPLACE---
c
---DESCRIPTION---
no meta here
"""


def test_sim_sections_parse_and_old_replies_still_work():
    full = improve._parse_candidates_full(REPLY)
    assert full[0][:3] == ("old line", "new line", "sharper hook")
    assert full[0][3] == {"problem": "Hook Strength", "predicted": "hook score +2"}
    assert full[1][3] == {"problem": "", "predicted": ""}
    assert improve._parse_candidates(REPLY) == [c[:3] for c in full]   # unchanged 3-tuples


def test_a_delimiter_in_the_edit_still_drops_the_candidate():
    bad = REPLY.replace("new line", "new ---PROBLEM--- line")
    assert [c[0] for c in improve._parse_candidates_full(bad)] == ["b"]


def test_record_measures_the_targeted_dimension_and_keeps_discards():
    mem = sim_memory.load(None)
    before = json.dumps({"dimensions": {"Hook Strength": {"score": 5, "max": 10}}})
    after = json.dumps({"dimensions": {"Hook Strength": {"score": 8, "max": 10}}})
    ctx = sim_memory.context("email.txt", "t", 1, "m", "e")
    k = sim_memory.record(mem, problem="Hook Strength", what="sharper hook", predicted="+2",
                          before_breakdown=before, after_breakdown=after, overall_before=50, overall_after=54,
                          pairwise="keep_challenger", kept=True, context=ctx)
    sim_memory.record(mem, problem="hook strength", what="question opener", predicted="+1",
                      before_breakdown=after, after_breakdown=after, overall_before=54, overall_after=53,
                      pairwise="keep_champion", kept=False, context=ctx)
    atts = mem["problems"][k]["attempts"]
    assert k == "hook-strength" and len(atts) == 2          # same problem, both attempts kept
    assert atts[0]["observed"]["dimension_delta"] == 3
    assert atts[1]["kept"] is False
    text = sim_memory.render(mem)
    assert "KEPT" in text and "discarded" in text and "predicted: +2" in text and "dimension +3" in text


def test_memory_round_trips_and_rejects_foreign_files():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.json")
        mem = sim_memory.load(p)
        mem["problems"]["x"] = {"name": "x", "opened": None, "attempts": []}
        sim_memory.save(mem, p)
        assert sim_memory.load(p)["problems"]["x"]["name"] == "x"
        open(p, "w").write('{"version": "other"}')
        try:
            sim_memory.load(p)
            assert False, "foreign file accepted"
        except ValueError:
            pass


def test_the_mutator_prompt_carries_the_whole_memory(monkeypatch):
    seen = {}
    monkeypatch.setattr(improve, "llm_call", lambda prompt, temperature=0.7: seen.setdefault("p", prompt) and REPLY)
    out = improve.mutate_candidates("old line\nb", "rubric", "{}", "history row", n=2, memory_text="MEMORY-BODY")
    assert "MEMORY-BODY" in seen["p"] and "---PREDICT---" in seen["p"]
    assert "history row" not in seen["p"]
    assert len(out[0]) == 4
    seen.clear()
    out = improve.mutate_candidates("old line\nb", "rubric", "{}", "history row", n=2)
    assert "history row" in seen["p"] and "---PREDICT---" not in seen["p"]
    assert len(out[0]) == 3
