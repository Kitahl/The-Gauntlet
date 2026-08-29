from __future__ import annotations

import json
from pathlib import Path

from egrt_challenge_types import ChallengeKind, ChallengeOrigin, ChallengeRequest
from egrt_types import digest


def init_root(root: Path, mode: str = "shadow") -> None:
    (root / ".gauntlet.json").write_text(
        json.dumps({
            "state_dir": ".egrt/state",
            "runtime": {"enabled": True, "schema": "egrt.runtime.v1"},
            "challenge": {
                "mode": mode,
                "max_total_per_obligation": 4,
                "max_load_bearing_per_obligation": 2,
                "max_selected_discriminators": 2,
                "allow_foil_proposals": True,
                "require_claim_native_receipt": True,
                "block_on_unavailable_load_bearing": True,
                "persist_raw_text": False,
            },
        }),
        encoding="utf-8",
    )


def request(
    *,
    challenge_id: str = "challenge-1",
    task_id: str = "task-1",
    obligation_id: str = "obl-1",
    kind: ChallengeKind = ChallengeKind.COUNTEREXAMPLE,
    load_bearing: bool = True,
) -> ChallengeRequest:
    return ChallengeRequest(
        challenge_id=challenge_id,
        task_id=task_id,
        obligation_id=obligation_id,
        target_module="mind",
        origin=ChallengeOrigin.MODULE_NATIVE,
        kind=kind,
        hypothesis="candidate may fail",
        alternative="negated candidate",
        refuter="exact check",
        consequence_if_true="candidate is invalid",
        load_bearing=load_bearing,
        required_capability="FINITE_ENUMERATION",
        candidate_hash=digest({"candidate": 1}),
        scope_hash=digest({"scope": 1}),
        obligation_set_hash=digest({"obligations": 1}),
        proposer="mind:native",
        information_rank=3,
        risk_rank=3,
        cost_rank=1,
    )
