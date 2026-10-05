from cpubench.specs import load_pack, load_profile


def test_bundled_memory_pack_loads() -> None:
    pack, families = load_pack("packs/memory-access/pack.yaml")
    assert pack.pack_id == "memory-access"
    assert {family.family_id for family in families} == {
        "memory.dependent_load_latency",
        "memory.memory_level_parallelism",
    }
    assert all(family.semantic_id for family in families)


def test_bundled_profile_loads() -> None:
    profile = load_profile("profiles/smoke.yaml")
    assert profile.profile_id == "smoke"
    assert profile.attempts_per_point == 1
