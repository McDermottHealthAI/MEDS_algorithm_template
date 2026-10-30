# Template test catalogue

These tests validate the generator and rendered repository structure. Shared runtime/contract tests have
[their own catalogue](https://github.com/McDermottHealthAI/meds-algorithm/blob/main/src/meds_algorithm/TESTING.md),
rendered from the installed package on the documentation site's Shared-package tests page.
Generated algorithm acceptance tests are documented separately in the next section of the site and in
`docs/TESTING.md` inside each generated repository. Keep these three scopes distinct.

## Running template tests

```bash
uv sync --group dev --group docs
uv run ruff check src tests scripts docs/hooks.py
uv run ruff format --check src tests scripts docs/hooks.py
uv run pytest -q
uv run pytest tests/test_profiles.py -q
uv run mkdocs build --strict
```

Tests use temporary renders, toy implementations and synthetic data. MEDS-DEV provisioning is mocked or
exercised through capability fixtures in this suite; passing it does not mean a real clinical dataset was
run. Parametrized functions produce several pytest cases. Helper fixtures are not separate acceptance tests.

## Test inventory

### test_generator.py

[Source](https://github.com/McDermottHealthAI/MEDS_algorithm_template/blob/main/tests/test_generator.py)

| Test | What it checks | Why it exists |
|---|---|---|
| `test_generator_binds_installed_version_and_forwards_answers` | Checks repository URL, installed-version tag, answers and Copier options passed by the launcher. | Generate from the version the user installed and preserve reproducible updates. |
| `test_bad_answers_fail_before_copy` | Parametrizes invalid answer-file contents and requires failure before generation. | Avoid partial projects from malformed user input. |
| `test_version_does_not_generate` | Runs the version option without invoking Copier. | Keep informational CLI commands free of generation side effects. |

### test_profiles.py

[Source](https://github.com/McDermottHealthAI/MEDS_algorithm_template/blob/main/tests/test_profiles.py)

| Test | What it checks | Why it exists |
|---|---|---|
| `test_algorithm_name_controls_module_classes_exports_and_command` | Renders a named algorithm and checks its module, classes, exports and console entry point. | Make concrete algorithms meaningfully importable and executable. |
| `test_invalid_or_colliding_algorithm_names_are_rejected` | Parametrizes invalid slugs/class names and collisions with reserved packages. | Reject generated projects that cannot import or would shadow their dependencies. |
| `test_all_profiles_coexist_and_selection_is_required` | Renders all profiles and checks explicit selection when a repository is ambiguous. | Support algorithm families without silently choosing a lifecycle. |
| `test_slurm_forwards_dataset_configuration_to_every_step` | Checks propagation of shared dataset/predicate/config arguments through the launcher. | Prevent one pipeline step from using a different data or configuration binding. |
| `test_descriptors_dispatch_only_their_profile_with_complete_arguments` | Checks each MEDS-DEV descriptor against its profile and required step arguments. | Keep generated external command wiring aligned with the core contract. |
| `test_registration_keeps_profile_descriptors_separate` | Registers several profiles independently into MEDS-DEV. | Avoid overwriting one profile with another in a family repository. |
| `test_generated_requests_reject_unknown_arguments` | Dispatches generated CLI requests with unknown arguments. | Fail configuration typos instead of silently ignoring them. |
| `test_slurm_selects_one_profile_and_isolates_default_outputs` | Checks profile selection and default artifact/run destinations. | Prevent cross-profile artifact collisions during cluster execution. |
| `test_generated_acceptance_tests_cover_every_profile` | Collects generated acceptance tests and checks their profile parametrization. | Ensure an implemented family cannot leave a declared profile untested. |
| `test_recorded_upstream_inputs_become_explicit_arguments` | Resolves recorded upstream inputs and rejects nonexistent artifact-input roles. | Make reused artifacts supply the correct explicit downstream inputs. |
| `test_rendered_spec_points_to_core_and_contract_is_not_copied` | Checks shared imports and absence of generated copies of the contract package. | Keep fixes and normative specifications owned by the shared package. |
| `test_rendered_report_gate_checks_completed_profile_with_other_stubs` | Completes one profile while others remain stubs and checks the report gate. | Require evidence for completed profiles even in partly implemented families. |

### test_render.py

[Source](https://github.com/McDermottHealthAI/MEDS_algorithm_template/blob/main/tests/test_render.py)

| Test | What it checks | Why it exists |
|---|---|---|
| `test_renders_six_algorithm_profiles` | Renders each profile, compiles Python and inspects its generated contract/operational files. | Catch generation failures across the full supported profile set. |
| `test_copier_answers_record_portable_update_metadata` | Checks the answers file retains update provenance. | Allow later Copier updates without reconstructing how the project was generated. |
| `test_mimic_task_prepends_pinned_meds_dev_venv_only_for_task` | Inspects environment arguments used for dataset and task preparation. | Use the intended task tool without globally changing unrelated command resolution. |
| `test_example_signal_dataset_has_no_length_or_position_leak` | Checks that labels match signal-code presence, with variable history lengths and both classes. | Sanity-check the example signal fixture; this is not a statistical proof that all shortcuts are absent. |
| `test_primary_behavior_is_a_required_failing_placeholder` | Checks the generated test requires real signal binding and a shuffled-label control. | Do not let an unimplemented scientific behavior test pass by default. |
| `test_predicates_are_external_not_a_rendered_semantic_format` | Renders without predicates and checks the descriptor and absence of a semantics file. | Avoid inventing an algorithm feature representation in the template. |
| `test_implementation_prompt_belongs_to_template_readme_not_rendered_repo` | Checks the copyable implementation prompt exists only in the template README. | Avoid shipping duplicate agent instructions into each generated project. |
| `test_spec_has_one_template_source_and_renders_to_root` | Checks the generated SPEC uses the single template source. | Prevent competing copies of generated specification guidance. |
| `test_prediction_keys_are_compared_directly` | Parametrizes reordered, missing, extra and duplicate prediction rows. | Judge cohort coverage by keys rather than row count or row order. |
| `test_meds_dev_predicates_capability_is_explicit` | Checks MEDS-DEV capability detection for predicate passthrough. | Fail unsupported integrations instead of silently dropping dataset semantics. |
| `test_only_zero_shot_meds_dev_runs_require_task_criteria` | Checks which profile adapters require task-criteria capability. | Require task support where needed without imposing it on other profiles. |
| `test_meds_dev_ref_is_checked_out_in_clone` | Inspects the configured revision used when provisioning MEDS-DEV. | Keep integration runs reproducible rather than following an implicit default branch. |
| `test_measurement_manifest_is_plausible` | Exercises measured publication and inspects recorded resources/provenance. | Catch missing or implausible run evidence at the integration boundary. |
| `test_only_zero_shot_profiles_receive_the_task` | Checks task arguments in generated zero-shot versus other profile wiring. | Keep task-independent preprocessing/inference independent of the evaluation task. |
| `test_zero_shot_stub_rejects_a_missing_task_before_work` | Invokes the generated CLI with missing/invalid task inputs. | Validate the boundary before reaching algorithm implementation. |
| `test_task_spec_ledger_and_label_blind_index` | Checks task/predicate digests, relaxation-ledger round trips, index projection and truth attachment. | Preserve task semantics and keep scoring inputs label-blind. |
| `test_predictions_and_cli_lists_follow_meds_dev` | Checks prediction layout and CLI list argument handling across profiles. | Keep generated commands consumable by MEDS-DEV. |
| `test_meds_dev_evaluates_every_parquet_under_predictions` | Checks handling of recursively stored prediction files. | Avoid omitting shards during evaluation. |
| `test_artifacts_are_siblings_and_slurm_lists_only_profile_commands` | Checks artifact layout and profile-specific launcher commands. | Avoid nested artifact overlap and accidental execution of unrelated steps. |
| `test_contract_helpers_for_conformance_checks` | Exercises shared conformance helpers through a rendered repository. | Ensure generated projects can use the installed core test utilities. |
| `test_predict_only_reads_context_labels_never_evaluated_ones` | Checks training-context access and forbids evaluated outcomes. | Protect predict-only/in-context scoring from target leakage. |
| `test_label_leakage_check_strips_what_the_profile_may_not_read` | Checks forbidden outcomes are removed according to each profile's permissions. | Make the adversarial rerun respect training/context permissions while withholding evaluation truth. |
| `test_submit_stages_reuse_shared_task_independent_artifacts` | Checks staged SLURM execution reuses preprocessing/pretraining as intended. | Avoid repeating shared work or confusing task-specific and independent artifacts. |
| `test_submit_overrides_resources_args_and_sbatch_flags_from_the_environment` | Supplies launcher environment overrides and checks the resulting command/resource flags. | Let documented run overrides take effect predictably. |

### test_typed_execution.py

[Source](https://github.com/McDermottHealthAI/MEDS_algorithm_template/blob/main/tests/test_typed_execution.py)

| Test | What it checks | Why it exists |
|---|---|---|
| `test_rendered_algorithm_runs_persisted_lifecycle_with_structured_config` | Implements a tiny rendered algorithm, runs its lifecycle and reloads fitted state with structured configuration. | Demonstrate the generated API works beyond empty stubs and records resolved settings. |

## Release checks outside pytest

`tests/wheel_smoke.py` installs/executes the generator against a local tagged template mirror. It checks
single-profile and all-profile generation, compilation, canonical source URL and recorded release tag.
It detects packaging and version/source mistakes without requiring a real release tag to exist yet.

`scripts/check_release.py` requires matching exact PyPI pins for runtime, conformance and development
uses of the shared package, then checks that the pinned version has downloadable files on PyPI. A Git
pin used to review unreleased core changes deliberately fails this release gate. Strict MkDocs checks
links/builds; Twine checks built distribution metadata. Neither proves scientific correctness.

Update a catalogue row whenever its test is added, renamed or changes purpose. A green template suite
is evidence about the template, not evidence that a generated algorithm has been implemented.
