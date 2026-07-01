from rag.query_expand import expand_query


def test_expand_marssoniosis():
    out = expand_query("Что известно о марссониозе яблони?").lower()
    assert "marssonina" in out
    assert "марссон" in out


def test_expand_no_change_without_match():
    q = "Как поливать грушу?"
    assert expand_query(q) == q


def test_expand_rootstock_synonyms():
    out = expand_query("Подвои серии СК-4").lower()
    assert "ск 4" in out or "ск4" in out
