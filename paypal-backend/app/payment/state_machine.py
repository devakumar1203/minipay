from typing import Dict, Set

VALID_TRANSITIONS: Dict[str, Set[str]] = {
    "PENDING": {"COMPLETED", "FAILED", "UNDER_REVIEW"},
    "UNDER_REVIEW": {"PENDING", "FAILED"},  # Admin approve -> PENDING (resumes flow), reject -> FAILED
    "COMPLETED": {"REVERSED"},
    "FAILED": set(),
    "REVERSED": set(),
}


def validate_transition(current: str, target: str) -> bool:
    """Validates state transitions according to the payment state machine."""
    return target in VALID_TRANSITIONS.get(current, set())

