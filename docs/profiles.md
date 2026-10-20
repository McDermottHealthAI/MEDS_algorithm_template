# Choosing a model profile

A **model profile** is a fixed sequence of commands. Every repository selects exactly one when it is
rendered (`copier copy … --data profile=…`). A profile describes the model's *lifecycle* — what it needs to
be trained and how it predicts — not its architecture or backend. Commands outside the selected profile are
unsupported, not silent no-ops.

| Profile | Commands, in dependency order |
|---|---|
| `supervised` | `preprocess_data` → `supervised_train` → `predict` |
| `finetune` | `preprocess_data` → `pretrain` → `supervised_train` → `predict` |
| `probe` | `preprocess_data` → `pretrain` → `infer` → `supervised_train` → `predict` |
| `zero_shot_direct` | `preprocess_data` → `pretrain` → `predict` |
| `zero_shot_materialized` | `preprocess_data` → `pretrain` → `infer` → `predict` |
| `packaged` | `preprocess_data` → `predict` |

## Which profile fits my model?

```mermaid
flowchart TD
    q1{Does the model learn<br/>from this task's labels?}
    q1 -- No --> q4{Was it pretrained on the<br/>target dataset by this repo?}
    q4 -- "No: it ships ready-made<br/>(weights, rules, a service)" --> packaged[packaged]
    q4 -- Yes --> q5{How does it answer a task?}
    q5 -- "Answers a task-derived query directly<br/>(hazard, P(code in window), score)" --> zsd[zero_shot_direct]
    q5 -- "Generates possible futures,<br/>then the task is evaluated on them" --> zsm[zero_shot_materialized]
    q1 -- Yes --> q2{Is there a task-independent<br/>pretraining stage?}
    q2 -- No --> supervised[supervised]
    q2 -- Yes --> q3{How are labels used?}
    q3 -- "Update the pretrained model's weights" --> finetune[finetune]
    q3 -- "Freeze it, extract representations,<br/>train a small head on them" --> probe[probe]
```

Pick the profile that matches the source model's **actual** training and prediction lifecycle, and record
why in `IMPLEMENTATION_REPORT.md`. Do not pick a shorter profile to avoid implementing a stage.

## Commands at a glance

| Command | Publishes | Receives labels? | Receives the task? |
|---|---|---|---|
| `preprocess_data` | `patients` | no | no |
| `pretrain` | `pretrained_model` (task-independent) | no | no |
| `infer` | `inference` (task-independent, at requested timepoints) | no (keys only) | no |
| `supervised_train` | `supervised_model` | yes | no (learned from labels) |
| `predict` | `predictions` | no (keys only; see [the one rule](concepts.md#reading-labels-the-one-rule)) | zero-shot only |

## The profiles one by one

=== "supervised"

    A model trained from scratch on the task's labels: logistic regression on tabular features, XGBoost,
    a recurrent network trained end to end.

    ```mermaid
    flowchart LR
        d[(MEDS)] --> pp[preprocess_data] --> st[supervised_train] --> pr[predict]
        l[(index + labels)] --> st
        l -. keys .-> pr
    ```

=== "finetune"

    A foundation model pretrained on the dataset without labels, then fine-tuned end to end on the task
    (MOTOR fine-tuned, CLMBR fine-tuned).

    ```mermaid
    flowchart LR
        d[(MEDS)] --> pp[preprocess_data] --> pt[pretrain] --> st[supervised_train] --> pr[predict]
        l[(index + labels)] --> st
        l -. keys .-> pr
    ```

=== "probe"

    A frozen foundation model whose representations at the prediction times are extracted once
    (`infer`), then a light head is trained on them (linear probing, MOTOR-LP).

    ```mermaid
    flowchart LR
        d[(MEDS)] --> pp[preprocess_data] --> pt[pretrain] --> inf[infer] --> st[supervised_train] --> pr[predict]
        l[(index + labels)] -. keys .-> inf
        l --> st
        l -. keys .-> pr
    ```

=== "zero_shot_direct"

    A pretrained model that **answers a query derived from the task directly**, without any labels:
    MOTOR+ (time-to-event hazards via aces-to-motor) and EveryQuery (probability that a code occurs in a
    window). `predict` translates the task into the model's queries, runs the model, and decodes
    probabilities.

    ```mermaid
    flowchart LR
        d[(MEDS)] --> pp[preprocess_data] --> pt[pretrain] --> pr[predict]
        t[ACES task] --> pr
        l[(index)] -. keys .-> pr
    ```

=== "zero_shot_materialized"

    A pretrained **generative** model that samples possible futures (an autoregressive EHR generator such
    as MEDS-EIC-AR). `infer` generates futures at the index's prediction times *without knowing the task*,
    so one `infer` run serves every task over the same index. `predict` evaluates the ACES task on the
    real history plus each generated future and reports the fraction of futures in which the label is
    true.

    ```mermaid
    flowchart LR
        d[(MEDS)] --> pp[preprocess_data] --> pt[pretrain] --> inf["infer<br/>(task-independent)"] --> pr[predict]
        l[(index)] -. keys .-> inf
        t[ACES task] --> pr
        d -- real history --> pr
        l -. keys .-> pr
    ```

=== "packaged"

    A model that arrives ready-made and is not trained here: published weights, a rule-based score, or an
    external service. Only data preparation and prediction run in the repository.

    ```mermaid
    flowchart LR
        d[(MEDS)] --> pp[preprocess_data] --> pr[predict]
        l[(index)] -. keys .-> pr
    ```

## Direct vs materialized: the distinction that matters

The two zero-shot profiles are not two ways of organizing the same code; they are two kinds of model.

| | `zero_shot_direct` | `zero_shot_materialized` |
|---|---|---|
| The model | answers a query: a hazard, a probability, a score | generates (*materializes*) possible futures |
| Examples | MOTOR+, EveryQuery | MEDS-EIC-AR |
| `infer` | none | task-independent: N futures per index row, reusable across tasks |
| `predict` | translate the task → run the model → decode probabilities | run ACES on history + each future; probability = fraction of futures with the label |
| What gets approximated | the *task*: it is reduced to the query language, so the ledger usually lists several steps | the *estimate*: the task is evaluated as written, so it is usually exact up to sampling |
| Tasks whose windows reach before the prediction time | must be re-anchored on the prediction time or rejected | fine: past criteria are checked on the real history |

If your model needs the task to decide what to compute, it is direct. If it can do its expensive work
without knowing the task and only needs the task to *score* what it produced, it is materialized.
