import importlib.util
from pathlib import Path

from asseta.modules.intelligence.ml_models import MODEL_TRANSITIONS, ModelStatus
from asseta.modules.intelligence.ml_training import clean_json
from asseta.tools.ml_cli import build_parser

MIGRATION = Path(__file__).parents[2] / "migrations/versions/20261022_g6sec0000002_ml_governance_security.py"


def test_db_guard_and_code_share_one_transition_graph() -> None:
    spec = importlib.util.spec_from_file_location("ml_sec", MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    code = {(a.value, b.value) for a, targets in MODEL_TRANSITIONS.items() for b in targets}
    assert code == set(mod.TRANSITIONS)
    assert MODEL_TRANSITIONS[ModelStatus.DISABLED] == frozenset() == MODEL_TRANSITIONS[ModelStatus.REJECTED]


def test_clean_json_drops_non_finite_numbers() -> None:
    assert clean_json({"a": float("nan"), "b": [1.5, float("inf")], "c": (2,)}) == {
        "a": None,
        "b": [1.5, None],
        "c": [2],
    }


def test_cli_parses_subcommands() -> None:
    p = build_parser()
    args = p.parse_args(["snapshot", "--tenant", "all", "--from", "2026-01-01", "--to", "2026-02-01"])
    assert (args.tenant, args.date_from, args.date_to) == ("all", "2026-01-01", "2026-02-01")
    assert p.parse_args(["train", "--tenant", "00000000-0000-0000-0000-000000000001", "--seed", "3"]).seed == 3
    assert p.parse_args(["status"]).command == "status"
