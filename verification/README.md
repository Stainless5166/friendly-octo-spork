# Formal verification (CrossHair + TLA+)

Distinct from every other testing layer in this repo: `uv run pytest`,
Hypothesis (docs/DESIGN.md §16.1), and mutation testing
(`mutation/README.md`) all *sample* — thousands of generated examples,
or thousands of mutated implementations, but never a proof. CrossHair
performs symbolic execution: it explores every input satisfying a
function's precondition, looking for one that violates its
postcondition, and reports either a real counterexample or
`"Confirmed over all paths"` — a claim no amount of sampling can make.

This is not a replacement for the other layers. It's additive, and
deliberately narrow — see "Which functions, and why" below.

```bash
uv run crosshair check verification/contracts/<file>.py --per_condition_timeout 25
```

## What actually got verified (this baseline)

`verification/contracts/confidence_contract.py` wraps
`spork.core.llm.confidence.confidence_band()` — the smallest, purest
function in the mutation-tested set (docs/DESIGN.md §16.1) — with
three CrossHair contracts. Real, current results:

- **`confidence_band_is_autoact_iff_at_or_above_threshold`** —
  **confirmed over all paths.** For any `alert_threshold <=
  autoact_threshold`, `"autoact"` comes back exactly when `confidence
  >= autoact_threshold`. Not "no counterexample in N examples" —
  proven for every float satisfying the precondition.
- **`confidence_band_never_raises_for_a_valid_threshold_ordering`** —
  **confirmed over all paths.**
- **`confidence_band_is_alert_only_iff_below_alert_threshold`** —
  **counterexample found:** `confidence_band(float("nan"),
  alert_threshold=0.0, autoact_threshold=0.0)` returns `"alert_only"`,
  but `nan < 0.0` is `False` (every NaN comparison is `False` under
  IEEE 754), so the claimed `(band == "alert_only") == (confidence <
  alert_threshold)` iff is violated — both of `confidence_band()`'s
  `>=` checks fail silently on NaN and fall through to the
  `"alert_only"` default, rather than raising.

That third one is real, and it's exactly the kind of thing sampling
structurally can't find the way proof can: `test_confidence_fuzz.py`
(§16.1) explicitly sets `allow_nan=False` on its float strategy — a
reasonable choice for a property test, but it means Hypothesis was
never going to generate this input no matter how many examples ran.
CrossHair doesn't sample a distribution; it doesn't have one to avoid
the edge of.

**Is it exploitable?** No — verified, not assumed.
`confidence_band()`'s only real caller
(`spork.core.pipeline.tier2.modules.ConfidenceBandSelector.select()`)
passes `verdict.confidence`, and `Verdict.confidence` is a pydantic
field with `Field(ge=0.0, le=1.0)` — which, checked directly,
*rejects* NaN before a `Verdict` can even be constructed
(`ge`/`le` comparisons against NaN are `False`, so pydantic's own
range check fails closed). So this is a real gap in
`confidence_band()`'s own contract, currently defended in depth by its
one caller's input validation — the same "true in isolation, not
reachable end-to-end" shape `mutation/README.md`'s recorded-equivalent
mutants have, but found by proof instead of by a mutant surviving.
Not fixed here (an application-code change); recorded as a known,
narrow gap rather than silently left unverified.

## Which functions, and why — a purity catalog, not a mandate

"Pure" here means: no I/O, no mutation of arguments or module state,
deterministic given its inputs — the shape CrossHair (and, for that
matter, Hypothesis) actually works well against. Cataloged, not all
verified — running CrossHair against a function is its own deliberate
step per function, same "worth its own commit" reasoning
`mutation/README.md`/`static_analysis/README.md` already established
for scoping a new module in.

**Already pure, verification candidates (roughly ranked by how much a
silent wrong answer would matter):**

| Function | Why it's decision-critical |
|---|---|
| `llm.confidence.confidence_band()` | **verified above** — gates every Tier 2 verdict's autoact-vs-alert decision |
| `rules.engine._condition_matches()` / `evaluate()` | Tier 1's entire routing decision (already mutation-tested) |
| `dispatch.combine.PrimaryCombiner`/`HighestConfidenceCombiner` | multi-classifier reduction (already mutation-tested) |
| `classify.keyword.KeywordClassifier.classify()` | Tier 1's default local classifier's scoring (already mutation-tested) |
| `receipts.extract.resolve_company()` / `extract_date()` | the decline-rather-than-guess receipt resolution chain (already mutation-tested) |
| `receipts.registry.normalize_sender_domain()` | the key every learned-sender lookup is keyed by — a normalization bug silently splits one sender into two |
| `llm.clean._strip_html()` / `_collapse_quote_chain()` / `_truncate()` | already robustness-fuzz-tested (§16.3); correctness (not just survival) properties are a plausible next CrossHair target |
| `pipeline.tier2.escalate.parse_to_addresses()` | already property-tested (§16.1) — a small, cheap second CrossHair candidate |
| `llm.budget.has_budget_remaining()` | the daily-call-budget gate — small, easy, not yet looked at by any layer beyond examples |

**Could be made pure — decision logic currently entangled with a side
effect, worth a deliberate split before verification, not something to
force a contract onto as-is:**

- `actions.executor.ActionExecutor.execute()` — the *decision* half
  (which action types raise, which reach the applier) is already pure
  reasoning wrapped around one side-effecting call
  (`self._applier.apply(...)`). Splitting out a pure `_classify(action)
  -> Literal["reject", "apply", "noop"]` helper would make the
  decision itself directly CrossHair-checkable, independent of any
  `ActionApplier` implementation — the same "test the decision, not
  the effect" instinct docs/DESIGN.md §16.1 already applies to
  `evaluate()`. Not done here — an application-code change (a real
  refactor, not a tooling addition), left as a design decision for
  whoever picks it up next.

**Deliberately not catalogued as candidates:** anything whose job *is*
I/O (`StateDB`, every `Provider`, `LLMClient`, `Alerter`) or whose
correctness depends on a live collaborator's behavior
(`escalate_message_or_quarantine()`'s overall flow) — CrossHair (like
Hypothesis) needs a pure or mockably-pure boundary to search
symbolically against; forcing a contract onto a function that calls
`sqlite3`/`smtplib`/an LLM API wouldn't verify anything real, the same
"reach for it only when it earns its keep" discipline the rest of
docs/DESIGN.md §16 already applies.

## TLA+: verifying the design, not the code

CrossHair (above) proves properties about one function's *code*.
`verification/tla/` proves properties about a *design* — specifically
`_run_message_loop()`'s control-plane-event queue/drain protocol
(`spork.daemon.state.DaemonState.pending_control_plane_events`,
docs/DESIGN.md §6.2.2), the exact mechanism the code's own comments say
exists to avoid two independent `to_thread()` calls racing the same
`StateDB` connection. That comment is a claim about *interleavings* —
every possible order the asyncio scheduler could run the IPC handler
coroutines and the message loop coroutine in — which is a different
kind of question than "does this function's code have a bug." CrossHair
explores input *values*; TLA+ (via its model checker, TLC) explores
*interleavings* of a system's steps. Neither one is instrumentation —
see below.

**Is this instrumentation?** No. Instrumentation adds code that
observes a *running* system — a log line, a metric, a trace span —
and needs the real system executing to produce anything. A TLA+ spec
is a separate, standalone mathematical model, written in `verification/tla/`,
that never touches `src/spork` and never runs alongside `sporkd`. TLC
(the model checker) doesn't execute spork's Python at all — it
exhaustively explores every state the *model* can reach and checks
invariants/properties against that, offline, before any code runs.
It's closer to a proof than to a monitor: the output is "here is every
reachable state, and the property holds/fails in all of them," not
"here is what happened during this one run."

### What's modeled and what TLC found

`ControlPlaneDrain.tla` models exactly the protocol
`_run_message_loop()`'s own comments describe: an `IPC` process
(any number of `pause()`/`resume()` calls, each appending one event to
a shared `pending` list) and a `Loop` process (repeatedly: capture
`pending` into a local `draining` and reset `pending` to a fresh list
— one atomic step, no interleaving point in between, matching the real
code's two plain Python statements with no `await` between them — then
write each captured event one at a time, each write its own
interleaving point). Two properties, checked against
`EVENTS = {1, 2, 3}` (small enough for TLC to exhaust the whole state
space, large enough to force real interleaving):

```bash
java -cp tla2tools.jar pcal.trans ControlPlaneDrain.tla   # PlusCal -> TLA+
java -cp tla2tools.jar tlc2.TLC -config ControlPlaneDrain.cfg ControlPlaneDrain.tla
```

- **`NoDuplicateWrites`** (invariant, checked at every reachable
  state): no event is ever written to `StateDB` twice.
- **`AllEventsEventuallyWritten`** (temporal property, checked under
  the fairness TLC's `fair process` gives both processes): every
  enqueued event eventually gets written — no event is silently lost
  under *any* interleaving.

**Result: both hold.** TLC generated 414 states, found 239 of them
distinct, and reported no error on either property — the atomic
capture-and-reset design the code comments claim is safe is, per this
model, actually safe against every interleaving TLC could construct.

**Proving the model can actually fail** — the same discipline
`mutation/README.md` applies to a surviving mutant: a check that can't
distinguish correct from broken isn't verifying anything.
`ControlPlaneDrainNonAtomic.tla` regresses the one thing that matters —
splits the capture-and-reset into two separate steps, with an
interleaving point in between, modeling what a careless future refactor
could introduce (an accidental `await`, or reverting to `.clear()`).
TLC finds a real counterexample:

1. IPC enqueues events 2 and 3; `pending = <<2,3>>`.
2. Loop's capture step runs: `draining := pending` → `draining = <<2,3>>`.
   `pending` is *not yet* reset (the now-separate `Reset` step hasn't
   run) — the gap that doesn't exist in the real, atomic design.
3. IPC interleaves here and enqueues event 1: `pending = <<2,3,1>>`.
4. Loop's `Reset` step runs: `pending := <<>>` — discarding event 1,
   which was never captured into `draining` either. It's gone.
5. `DrainWrite` writes `draining`'s contents (`2`, `3`); the loop
   repeats forever with nothing left to enqueue. Event `1` never
   appears in `written_log` — `AllEventsEventuallyWritten` is violated.

That's the real, verified cost of the anti-pattern the code comments
warn about, not an assumed one — the atomicity isn't decoration, it's
the one thing standing between this design and a silently-dropped
control-plane audit event.

### Getting `tla2tools.jar`

Not vendored in this repo (a ~2MB Java archive, and `.gitignore`
already excludes `verification/tla/states/`/`*.old`, TLC's/pcal.trans's
own regenerated artifacts). Fetch it fresh:

```bash
curl -sSL -o tla2tools.jar \
  https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar
```

Requires a JVM (any recent OpenJDK) — nothing else. `pcal.trans`
regenerates the plain-TLA+ translation (and its own `.cfg` template,
which the checked-in `.cfg` files already extend with the actual
`EVENTS`/`INVARIANT`/`PROPERTY` lines) from the `.tla` file's PlusCal
block; re-run it after editing the `(* --algorithm ... end algorithm; *)`
block, same as `mutmut`/`crosshair` need re-running after a source
change.

## Why a `contracts/` file, not a decorator in `src/spork`

CrossHair's docstring-based `pre:`/`post:` syntax could live directly
on the real function's own docstring — some CrossHair users do exactly
that. Deliberately not done here: it would mean writing a
machine-readable micro-language into `src/spork`'s prose docstrings
(which this codebase otherwise reserves for *why*, never a contract
DSL — see CLAUDE.md "Conventions"), and it would tie a function's
signature to whichever contracts happen to be checkable today.
`verification/contracts/*.py` imports and wraps the real function
instead — CrossHair verifies a claim about the actual `src/spork` code
either way, but the application code stays untouched, and a contract
file can state several independent properties (as
`confidence_contract.py` does) without crowding the function it's
about.
