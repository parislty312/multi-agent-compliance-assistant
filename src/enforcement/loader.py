import json
from pathlib import Path

from src.models import EnforcementRuleset

DEFAULT_RULESET_PATH = (
    Path(__file__).parents[2] / "rules" / "enforcement_rules.json"
)


def load_enforcement_ruleset(
    path: Path = DEFAULT_RULESET_PATH,
) -> EnforcementRuleset:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EnforcementRuleset.model_validate(payload)

