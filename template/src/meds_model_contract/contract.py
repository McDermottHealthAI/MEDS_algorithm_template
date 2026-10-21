"""Compatibility imports; the versioned core owns these definitions."""

from meds_model_core.contracts.commands import (
    MODEL_PROFILES,
    ZERO_SHOT_TASK_COMMANDS,
    STEP_SPECS,
    ArtifactInput,
    ArtifactType,
    Command,
    CommandName,
    ModelRepository,
    StepSpec,
)

__all__ = [
    "MODEL_PROFILES",
    "ZERO_SHOT_TASK_COMMANDS",
    "STEP_SPECS",
    "ArtifactInput",
    "ArtifactType",
    "Command",
    "CommandName",
    "ModelRepository",
    "StepSpec",
]
