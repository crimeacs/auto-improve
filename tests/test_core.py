import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import improve


# ── apply_diff: the crash-proof apply ladder ─────────────────────────────────

def test_apply_exact_replaces_once():
    content = "alpha beta gamma beta"
    new, how = improve.apply_diff(content, "alpha beta", "ALPHA BETA")
    assert how == "exact"
    assert new == "ALPHA BETA gamma beta"  # only the first occurrence


def test_apply_variance_climbs_ladder():
    # curly quotes + collapsed whitespace in the FIND should still land via
    # the canon or fuzzy rung, not fail.
    content = 'the user said "hello   world" today'
    new, how = improve.apply_diff(content, '“hello world”', "GOODBYE")
    assert how in ("canon", "fuzzy")
    assert new is not None
    assert "GOODBYE" in new


def test_apply_absent_find_is_not_found():
    new, how = improve.apply_diff("just some text", "nowhere to be seen", "X")
    assert new is None
    assert how == "not-found"


def test_apply_empty_find_rejected():
    new, how = improve.apply_diff("any content", "", "X")
    assert new is None
    assert how == "empty-find"


def test_apply_delimiter_in_replace_rejected():
    # a replacement that smuggles in a parser delimiter not already present
    new, how = improve.apply_diff("plain content here", "plain", "x ---REPLACE--- y")
    assert new is None
    assert how == "delimiter-in-replace"


# ── _parse_candidates: the parser guard ──────────────────────────────────────

def test_parse_one_clean_candidate():
    text = "\n".join([
        "===CANDIDATE 1===",
        "---FIND---",
        "old line of text",
        "---REPLACE---",
        "new line of text",
        "---DESCRIPTION---",
        "clarity: tighten the phrasing",
    ])
    cands = improve._parse_candidates(text)
    assert len(cands) == 1
    find, replace, desc = cands[0]
    assert find == "old line of text"
    assert replace == "new line of text"
    assert desc == "clarity: tighten the phrasing"


def test_parse_drops_block_with_stray_delimiter():
    # REPLACE body contains a stray ---REPLACE--- token -> ambiguous, dropped.
    text = "\n".join([
        "===CANDIDATE 1===",
        "---FIND---",
        "original text",
        "---REPLACE---",
        "rewritten ---REPLACE--- text",
        "---DESCRIPTION---",
        "voice: stronger opener",
    ])
    cands = improve._parse_candidates(text)
    assert cands == []


def test_parse_two_candidates():
    text = "\n".join([
        "===CANDIDATE 1===",
        "---FIND---",
        "first find",
        "---REPLACE---",
        "first replace",
        "---DESCRIPTION---",
        "dim one",
        "===CANDIDATE 2===",
        "---FIND---",
        "second find",
        "---REPLACE---",
        "second replace",
        "---DESCRIPTION---",
        "dim two",
    ])
    cands = improve._parse_candidates(text)
    assert len(cands) == 2
    assert cands[0][0] == "first find"
    assert cands[1][0] == "second find"
