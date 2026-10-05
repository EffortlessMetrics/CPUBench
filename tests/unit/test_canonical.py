from cpubench.canonical import canonical_json_text, semantic_id


def test_canonical_json_orders_keys() -> None:
    assert canonical_json_text({"b": 2, "a": 1}) == '{"a":1,"b":2}'


def test_semantic_id_is_deterministic() -> None:
    left = semantic_id("example", 1, {"b": 2, "a": 1})
    right = semantic_id("example", 1, {"a": 1, "b": 2})
    assert left == right
    assert left.startswith("sha256:")
