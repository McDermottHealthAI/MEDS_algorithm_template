"""Model-owned profile execution and fitted-feature inspection adapters."""
from collections.abc import Mapping
from pathlib import Path
from meds_model_core.conformance.types import E2EResult, MEDSDevRun

def run_e2e(tmp_path, *, profile: str, **inputs):
    """Run every selected step into tmp_path, honoring all external inputs and split overrides.

    Use create_repository().run(...) (the same typed runner as the CLI) for every step.
    Use a fresh algorithm instance/process; reopen fitted artifacts instead of keeping hidden state.
    Return E2EResult with seed, external_meds_dir and all task inputs recorded in inputs. Apply the seed
    to every RNG/framework/subprocess and use deterministic fixture settings. Conformance compares
    keyed scores across reruns (rtol=1e-6, atol=1e-8); stochastic production runs remain model-owned.
    Conformance reruns
    this hook with evaluated outcomes removed. Reuse supplied histories, not an old prepared artifact;
    emit fresh artifacts below tmp_path. Training/context splits retain their permitted labels.
    """
    raise NotImplementedError(
        "Prepare a small MEDS input/task, execute the selected model profile's real commands, and return "
        "E2EResult(artifacts, labels_dir, evaluated splits, external inputs used, "
        "canaries from meds_model_core.conformance.signal.add_split_canaries applied to the fixture)."
    )


def fitted_codes(artifacts: Mapping[str, Path]) -> set[str]:
    """Return every code the model fitted a population statistic for: its vocabulary, frequency tables,
    selected features, or bins.

    The transductive-fitting check requires the split canaries to be absent from this set (SPEC section
    2.1). Read it from the model's own artifacts; the payload formats are model-owned.
    """
    raise NotImplementedError("Report the codes the model fitted, read from its artifacts")


def prepare_meds_dev_run(meds_dev, tmp_path, *, profile: str):
    """Return ``MEDSDevRun(args, predictions_dir, labels_dir, splits)`` for this implementation."""
    raise NotImplementedError("Configure the selected model profile's real MEDS-DEV run")
