# Design Spec

**Project:** friendly-octo-spork ("Spork")
**Status:** Draft v0.1 — pre-implementation
**Author:** william@barrulemedical.im (with Claude)
**Last updated:** 2026-08-11

> **Naming note:** the repo name is the GitHub-generated placeholder. This
> spec adopts a working product name, **Spork**, purely so the two
> executables and package can have concrete names (`sporkd`, `spork`).
> Rename freely before the first release — nothing below depends on the
> name itself.

## 1. Overview

Spork is a personal email-triage tool for a Fastmail (JMAP) mailbox. It
listens for new mail, runs each message through a tiered classification
pipeline — cheap/deterministic first, LLM only when warranted — and takes
mailbox actions (file, tag, draft a reply) or raises an alert for the human
to handle. It is built to run continuously as a per-user background service,
with a companion CLI for status, configuration, and rule management.

This document specifies the architecture, components, data formats, and
key design decisions. See `ROADMAP.md` for phasing.

## 2. Goals

- Near-real-time triage of a single Fastmail account via JMAP push.
- A tiered pipeline that spends LLM tokens only on ambiguous/important mail.
- Deterministic, auditable rules for anything that runs unattended.
- Safe defaults: nothing is auto-sent or irreversibly destroyed without
  either high confidence or human confirmation.
- A daemon that survives logout/login cycles via systemd user services,
  plus a CLI that a human actually wants to run.
- Secrets declared, not scattered across `.env` files.

## 3. Non-goals (v1)

- Multi-account / multi-tenant support. One JMAP account, one user.
- A web UI. CLI + local notifications only.
- Fleet/admin JMAP APIs — irrelevant for a single personal mailbox.
- Full natural-language rule authoring in v1 (see roadmap — planned, not
  blocking).
- Auto-send of LLM-drafted replies. Draft-and-hold only, indefinitely,
  unless a future explicit opt-in is added per-rule.

## 4. Terminology

| Term | Meaning |
|---|---|
| **Tier 0** | Sieve rules running server-side on Fastmail; no Spork process involved. |
| **Tier 1** | Cheap local classification (rules/heuristics, no LLM call). |
| **Tier 2** | LLM escalation (Claude API call) for ambiguous/important mail. |
| **Tier 3** | Human review — surfaced via alert, no automatic action taken. |
| **Rule** | A user-authored condition → action mapping, evaluated at Tier 1. |
| **Action** | A mailbox mutation: move, tag (add/remove mailbox), draft, notify, no-op. |
| **Verdict** | The structured output of a Tier 1 or Tier 2 classification pass. |
| **Trigger** | Decides *when* to fetch — a push connection, a timer, an immediate no-op for tests. |
| **ContentFetcher** | Decides *what* to fetch, given a trigger fired — knows nothing about timing. |
| **Source** | A Trigger + ContentFetcher pair (sometimes fused, sometimes composed) that yields `NormalizedMessage` batches. |
| **Dispatch target** | A named `TextClassifier` backend a message can be fanned out to. |
| **Combiner** | Reduces N dispatch targets' results to the single `ClassificationResult` a decision acts on. |
| **Provider** | The daemon's whole relationship to one remote mail backend (JMAP, IMAP, ...): both read (`build_source`) and write (`build_action_applier`); loaded dynamically by spec string, never hardcoded. |
| **ActionApplier** | A provider's write side — applies one rule/verdict `Action` to a message on the remote backend. |

## 5. Architecture

```mermaid
flowchart TD
    fastmail[Fastmail<br/>JMAP over HTTPS]
    fastmail -->|EventSource push<br/>state changes| session

    subgraph sporkd["sporkd (daemon process)"]
        direction TB
        session["JMAP session manager<br/>(jmapc client + push)"]
        fetch["Fetch (Email/query + Email/get)"]
        tier1{"Tier 1: rule engine<br/>(heuristics, no LLM)"}
        tier2["Tier 2: Claude API classify"]
        exec_["Action executor<br/>(JMAP Email/set, drafts)"]
        alert["Alerting (desktop/push)"]
        state[("State store (SQLite)<br/>cursor, audit log, rule stats")]
        socket[["Local control socket<br/>(Unix domain)"]]

        session --> fetch --> tier1
        tier1 -->|confident verdict| exec_
        tier1 -->|"ambiguous / escalate rule"| tier2
        tier2 --> exec_
        exec_ --> alert
        fetch -.->|cursor| state
        exec_ -.->|audit| state
        tier1 -.->|audit| state
    end

    socket === cli["spork (CLI)<br/>status / rules / config / logs / pause"]
```

Two OS processes, one shared library:

- **`sporkd`** — long-running daemon, owns the JMAP connection, the state
  DB, and the rule engine. Started by a systemd user unit at login.
- **`spork`** — short-lived CLI, talks to `sporkd` over a local control
  channel (Unix domain socket) for anything live (status, pause/resume,
  "classify this message now"), and reads/writes config + rules files
  directly for anything that's just editing state on disk.
- **`spork.core`** — shared library: JMAP client wrapper, rule schema,
  Tier 1 evaluator, Claude client wrapper, action executor, state DB
  models. Both executables import it; there is no logic duplicated
  between them.

## 6. Components

### 6.1 Core library (`spork.core`)

Solid boxes are built and tested today; dashed boxes are planned
layout for a milestone that hasn't landed yet (M3's `llm/prompts.py`
— the not-yet-built step that assembles a `VerdictRequest` from a
message —, M4's `alerts/`, M5's `ipc/` + most of `cli/commands/`, and
`config.py`, still needed by anything that reads `config.toml`). This
is layout orientation only — see §6.4 for what each built module's
classes actually look like.

```mermaid
flowchart TD
    src["src/spork/"] --> core & daemon_pkg & cli_pkg

    subgraph core["core/ (shared library)"]
        config["config.py<br/>load/validate config.toml"]:::planned
        secrets_mod["secrets.py<br/>secretspec integration"]
        models_mod["models.py<br/>NormalizedMessage"]

        subgraph pipeline["pipeline/"]
            pipeline_core["core.py<br/>Payload/Filter/Selector/Pipeline"]
            pipeline_meta["meta.py<br/>MessageMeta"]
            pipeline_modules["modules.py<br/>7 concrete Filters/Selectors"]
            pipeline_default["default.py<br/>build_default_pipeline() +<br/>process_message()"]
        end

        subgraph providers["providers/"]
            providers_base["base.py<br/>Provider + ActionApplier"]
            providers_loader["loader.py<br/>load_provider()"]
            subgraph jmap["jmap/"]
                jmap_provider["provider.py<br/>JmapProvider"]
                jmap_client["client.py<br/>JmapClient"]
                jmap_push["push.py<br/>JmapPushTrigger"]
                jmap_backoff["backoff.py<br/>next_delay()"]
                jmap_mailboxes["mailboxes.py<br/>MailboxResolver"]
            end
            subgraph file_["file/"]
                file_provider["provider.py<br/>FileProvider"]
                file_messages["messages.py<br/>load_messages()"]
            end
        end

        subgraph sources["sources/"]
            sources_base["base.py<br/>Trigger/ContentFetcher/Source"]
            sources_triggered["triggered.py<br/>TriggeredSource"]
            sources_replay["replay.py<br/>ImmediateTrigger +<br/>SequenceContentFetcher"]
            sources_timer["timer.py<br/>IntervalTimer"]
            sources_fallback["fallback.py<br/>FallbackSource"]
        end

        subgraph rules["rules/"]
            rules_schema["schema.py<br/>Condition/Action/Rule"]
            rules_engine["engine.py<br/>Tier 1 evaluate()"]
            rules_loader["loader.py<br/>rules.toml parsing"]
        end

        subgraph classify["classify/"]
            classify_base["base.py<br/>TextClassifier +<br/>ClassificationResult"]
            classify_registry["registry.py<br/>name -> factory lookup"]
            classify_keyword["keyword.py<br/>default heuristic backend"]:::planned
        end

        subgraph dispatch["dispatch/"]
            dispatch_dispatcher["dispatcher.py<br/>Dispatcher"]
            dispatch_combine["combine.py<br/>Combiner +<br/>DispatchingClassifier"]
        end

        subgraph llm["llm/ (M3)"]
            llm_clean["clean.py<br/>clean_body()"]
            llm_prompts["prompts.py<br/>VerdictRequest builder"]:::planned
            llm_base["base.py<br/>LLMClient +<br/>VerdictRequest/Verdict"]
            llm_loader["loader.py<br/>load_llm_client()"]
            subgraph llm_clients["clients/"]
                llm_anthropic["anthropic.py<br/>AnthropicLLMClient"]
            end
        end

        subgraph actions["actions/"]
            actions_executor["executor.py<br/>ActionExecutor"]
            actions_drafts["drafts.py (M3)"]:::planned
        end

        subgraph alerts["alerts/ (M4)"]
            alerts_base["base.py"]:::planned
            alerts_desktop["desktop.py"]:::planned
            alerts_push["push.py"]:::planned
        end

        subgraph state["state/"]
            state_db["db.py<br/>StateDB + AuditEntry"]
        end

        subgraph ipc["ipc/ (M5)"]
            ipc_protocol["protocol.py"]:::planned
            ipc_server["server.py"]:::planned
        end
    end

    subgraph daemon_pkg["daemon/"]
        daemon_main["main.py<br/>sporkd entrypoint (stub loop)"]
    end

    subgraph cli_pkg["cli/"]
        cli_main["main.py<br/>spork entrypoint"]
        subgraph cli_commands["commands/"]
            cli_rules["rules.py<br/>spork rules test"]
            cli_doctor["doctor.py<br/>spork doctor (stub)"]
            cli_status["status.py / config.py / logs.py (M5)"]:::planned
        end
    end

    classDef planned stroke-dasharray: 4 3,opacity:0.65
```

### 6.2 Daemon (`sporkd`)

Single-process, asyncio event loop:

1. Load config + secrets at startup; fail fast with a clear error if
   required secrets are missing (`secretspec check` semantics).
2. Open a JMAP session, resolve mailbox IDs/roles once, cache them.
3. Start the EventSource push listener. On reconnect/backoff, fall back
   to a periodic `Email/query` poll (interval configurable) so the tool
   degrades gracefully instead of going silent.
4. On a push notification (or poll tick): fetch new `Email` objects in
   one batched JMAP call (`Email/query` + `Email/get` via result
   references), skipping IDs already in the state DB.
5. Run each message through the Tier 1 rule engine.
6. If a rule matches with an action, or explicitly resolves to "no
   action", apply it and stop.
7. If a rule marks the message for escalation, or no rule matches and the
   default policy is "escalate unknowns", send it to Tier 2 (Claude).
8. Apply the resulting Verdict via the action executor; anything at or
   above the configured alert threshold also fires an alert.
9. Record an audit entry (message ID, tier reached, verdict, action
   taken, latency, token cost if Tier 2) in the state DB.
10. Serve the local control socket concurrently for CLI requests
    (status, pause, "reclassify message X", "reload rules").

### 6.3 CLI (`spork`)

Talks to the daemon over the Unix socket when the daemon is up; falls
back to "daemon not running" messaging (with the systemd unit name to
start it) rather than silently doing nothing. Config/rules subcommands
that only touch files on disk work even with the daemon stopped, and
push a "reload" request to the daemon if it's running so changes take
effect without a restart.

See §12 for the full command reference.

**CLI framework: [Typer](https://typer.tiangolo.com/).** Chosen over
plain Click for the same reason the rest of this codebase leans on
type hints rather than docstring conventions or manual validation
(docs/TEST_COVERAGE.md, the `Protocol`-based modularity in §9.1/§9.2):
Typer derives each command's arguments/options/help text from type
hints and `typer.Option`/`typer.Argument` annotations, so a command's
signature *is* its CLI contract — no separate argparse/click
boilerplate to keep in sync with it by hand. It's built directly on
Click (so anything Click can do is still reachable if a future command
needs it) and gets `--install-completion` and Rich-formatted help for
free. `spork` is a Typer command **group** (`typer.Typer()` with
`@app.callback()` — subcommands land per §12 as M5 builds them);
`sporkd` is a single-command app (`typer.run(main)`) since the daemon
never has subcommands, just flags.

### 6.4 Module UML diagrams

One `classDiagram` per built module, in §6.1's component-tree order.
Protocols are stereotyped `<<Protocol>>`; a Protocol implementation is
drawn with a realization arrow labeled "structurally satisfies," never
plain inheritance, per this project's Protocol-based DI convention —
nothing here actually subclasses anything it implements. A free
function is drawn as a box stereotyped `<<function>>` so its
dependencies/raises are visible in the same diagram as the classes it
works with; it isn't a claim that the function is a class. A type
referenced from another module (e.g. `Source` inside
`providers.base`'s own diagram) is drawn as an empty box with just its
stereotype — the full definition lives in that other type's own
diagram, not duplicated here. Modules with no classes yet (`config.py`,
`llm/`, `alerts/`, `ipc/`, most of `cli/commands/`) don't get a diagram
until they have something to diagram, same as the component tree in
§6.1.

#### `spork.core.models`

```mermaid
classDiagram
    class NormalizedMessage {
        <<dataclass, frozen>>
        +message_id: str
        +thread_id: str
        +from_address: str
        +from_domain: str
        +subject: str
        +body_text: str
        +headers: dict
        +mailbox_ids: tuple
    }
```

The one type nearly every other module below depends on — consumers
aren't re-drawn on every diagram that just takes a `NormalizedMessage`
parameter, only where it's genuinely part of the module's own shape.

#### `spork.core.providers.base`

```mermaid
classDiagram
    class ActionApplier {
        <<Protocol>>
        +apply(message: NormalizedMessage, action: Action) None
    }
    class Provider {
        <<Protocol>>
        +build_source() Source
        +build_action_applier() ActionApplier
    }
    class Source { <<Protocol>> }

    Provider ..> Source : builds
    Provider ..> ActionApplier : builds
```

`Source` is fully defined in `spork.core.sources`' own diagram below;
`Action` is fully defined in `spork.core.rules`'.

#### `spork.core.providers.loader`

```mermaid
classDiagram
    class ProviderLoadError {
        <<Exception>>
    }
    class load_provider {
        <<function>>
        +load_provider(spec: str, kwargs: dict) Provider
    }
    class Provider { <<Protocol>> }

    load_provider ..> Provider : constructs
    load_provider ..> ProviderLoadError : raises
```

#### `spork.core.providers.jmap`

```mermaid
classDiagram
    class Trigger { <<Protocol>> }
    class ContentFetcher { <<Protocol>> }
    class Source { <<Protocol>> }
    class ActionApplier { <<Protocol>> }
    class Provider { <<Protocol>> }

    class JmapClient {
        -host: str
        -api_token: str
        +connect() None
        +fetch_new_messages(since_cursor: Optional~str~) Sequence
        +apply_action(message: NormalizedMessage, action: Action) None
    }
    class JmapPushTrigger {
        -client: JmapClient
        +wait() None
    }
    class MailboxInfo {
        <<dataclass, frozen>>
        +id: str
        +name: str
        +role: Optional~str~
    }
    class UnknownMailboxRoleError { <<Exception>> }
    class AmbiguousMailboxRoleError { <<Exception>> }
    class MailboxResolver {
        -fetch: function
        -by_role: Optional~dict~
        +resolve(role: str) str
        +refresh() None
    }
    class next_delay {
        <<function>>
        +next_delay(schedule: Sequence, attempt: int) float
    }
    class JmapProvider {
        -client: JmapClient
        -cursor: Optional~str~
        +build_source() Source
        +build_action_applier() ActionApplier
    }
    class _JmapContentFetcher {
        -client: JmapClient
        -cursor: Optional~str~
        +fetch() Sequence
    }
    class _JmapActionApplier {
        -client: JmapClient
        +apply(message: NormalizedMessage, action: Action) None
    }

    Trigger <|.. JmapPushTrigger : structurally satisfies
    ContentFetcher <|.. _JmapContentFetcher : structurally satisfies
    ActionApplier <|.. _JmapActionApplier : structurally satisfies
    Provider <|.. JmapProvider : structurally satisfies

    JmapPushTrigger --> JmapClient : wraps
    MailboxResolver ..> MailboxInfo : resolves from
    MailboxResolver ..> UnknownMailboxRoleError : raises
    MailboxResolver ..> AmbiguousMailboxRoleError : raises
    JmapProvider *-- JmapClient : constructs
    JmapProvider ..> JmapPushTrigger : builds
    JmapProvider ..> _JmapContentFetcher : builds
    JmapProvider ..> _JmapActionApplier : builds
    _JmapContentFetcher --> JmapClient : delegates to
    _JmapActionApplier --> JmapClient : delegates to
```

`backoff.next_delay()` is a pure function of `(schedule, attempt)`
with no dependency on the other classes here — drawn standalone
rather than wired into the rest, matching the code (`JmapPushTrigger`
doesn't call it yet; the daemon's future reconnect loop will).

#### `spork.core.providers.file`

```mermaid
classDiagram
    class Provider { <<Protocol>> }
    class ActionApplier { <<Protocol>> }
    class MessagesLoadError { <<Exception>> }
    class load_messages {
        <<function>>
        +load_messages(path) list
    }
    class _FileActionApplier {
        -log_path: Path
        +apply(message: NormalizedMessage, action: Action) None
    }
    class FileProvider {
        -messages_path: Path
        -actions_log_path: Path
        +build_source() Source
        +build_action_applier() ActionApplier
    }

    Provider <|.. FileProvider : structurally satisfies
    ActionApplier <|.. _FileActionApplier : structurally satisfies
    load_messages ..> MessagesLoadError : raises
    FileProvider ..> load_messages : uses
    FileProvider ..> _FileActionApplier : builds
```

#### `spork.core.sources`

```mermaid
classDiagram
    class Trigger {
        <<Protocol>>
        +wait() None
    }
    class ContentFetcher {
        <<Protocol>>
        +fetch() Sequence
    }
    class Source {
        <<Protocol>>
        +poll() Sequence
    }
    class TriggeredSource {
        -trigger: Trigger
        -fetcher: ContentFetcher
        +poll() Sequence
    }
    class ImmediateTrigger {
        +wait() None
    }
    class SequenceContentFetcher {
        -remaining: list
        -batch_size: int
        +fetch() Sequence
    }
    class IntervalTimer {
        -interval_seconds: float
        -sleep: function
        +wait() None
    }
    class FallbackSource {
        -primary: Source
        -secondary: Source
        -catch: tuple
        +poll() Sequence
    }

    Source <|.. TriggeredSource : structurally satisfies
    Source <|.. FallbackSource : structurally satisfies
    Trigger <|.. ImmediateTrigger : structurally satisfies
    Trigger <|.. IntervalTimer : structurally satisfies
    ContentFetcher <|.. SequenceContentFetcher : structurally satisfies
    TriggeredSource *-- Trigger
    TriggeredSource *-- ContentFetcher
    FallbackSource o-- Source : primary
    FallbackSource o-- Source : secondary
```

#### `spork.core.rules`

```mermaid
classDiagram
    class TextClassifier { <<Protocol>> }
    class Condition {
        <<pydantic BaseModel, extra=forbid>>
        +always: bool
        +from_domain_in: Optional~list~
        +local_classifier_category_in: Optional~list~
    }
    class Action {
        <<pydantic BaseModel, extra=forbid>>
        +type: str
        +mailbox: Optional~str~
        +reason: Optional~str~
    }
    class Rule {
        <<pydantic BaseModel, extra=forbid>>
        +id: str
        +description: str
        +when: Condition
        +action: Action
        +enabled: bool
    }
    class RuleVerdict {
        <<dataclass, frozen>>
        +action: Action
        +matched_rule_id: Optional~str~
    }
    class evaluate {
        <<function>>
        +evaluate(message, rules, default_unmatched_action, classifier) RuleVerdict
    }
    class RulesLoadError { <<Exception>> }
    class load_rules {
        <<function>>
        +load_rules(path) list
    }

    Rule *-- Condition
    Rule *-- Action
    RuleVerdict *-- Action
    evaluate ..> Rule : evaluates in order, first enabled match
    evaluate ..> RuleVerdict : produces
    evaluate ..> TextClassifier : classify(), lazily, at most once
    load_rules ..> Rule : produces
    load_rules ..> RulesLoadError : raises
```

#### `spork.core.classify`

```mermaid
classDiagram
    class ClassificationResult {
        <<dataclass, frozen>>
        +category: str
        +scores: dict
    }
    class TextClassifier {
        <<Protocol>>
        +classify(message: NormalizedMessage) ClassificationResult
    }
    class UnknownClassifierError { <<Exception>> }
    class register {
        <<function>>
        +register(name: str, factory: function) None
    }
    class get {
        <<function>>
        +get(name: str) TextClassifier
    }

    TextClassifier ..> ClassificationResult : returns
    get ..> TextClassifier : constructs from registered factory
    get ..> UnknownClassifierError : raises
```

#### `spork.core.dispatch`

```mermaid
classDiagram
    class TextClassifier { <<Protocol>> }
    class Dispatcher {
        -targets: dict
        +dispatch(message: NormalizedMessage) dict
    }
    class Combiner {
        <<Protocol>>
        +combine(results: dict) ClassificationResult
    }
    class CombineError { <<Exception>> }
    class PrimaryCombiner {
        -primary_name: str
        +combine(results: dict) ClassificationResult
    }
    class HighestConfidenceCombiner {
        +combine(results: dict) ClassificationResult
    }
    class DispatchingClassifier {
        -dispatcher: Dispatcher
        -combiner: Combiner
        +classify(message: NormalizedMessage) ClassificationResult
    }

    Combiner <|.. PrimaryCombiner : structurally satisfies
    Combiner <|.. HighestConfidenceCombiner : structurally satisfies
    TextClassifier <|.. DispatchingClassifier : structurally satisfies
    DispatchingClassifier *-- Dispatcher
    DispatchingClassifier *-- Combiner
    Dispatcher ..> TextClassifier : fans out to N named targets
    PrimaryCombiner ..> CombineError : raises
    HighestConfidenceCombiner ..> CombineError : raises
```

#### `spork.core.llm.base`

```mermaid
classDiagram
    class Action { <<pydantic BaseModel>> }
    class VerdictRequest {
        <<dataclass, frozen>>
        +subject: str
        +from_address: str
        +to_addresses: tuple
        +cleaned_body: str
        +thread_prior_subject: Optional~str~
        +thread_user_has_replied: bool
        +available_mailboxes: tuple
    }
    class Verdict {
        <<pydantic BaseModel>>
        +category: str
        +urgency: Literal
        +confidence: float
        +suggested_action: Action
        +summary: str
        +draft_reply: Optional~str~
        +reasoning: str
    }
    class LLMClient {
        <<Protocol>>
        +get_verdict(request: VerdictRequest) Verdict
    }

    Verdict *-- Action : suggested_action
    LLMClient ..> VerdictRequest : reads
    LLMClient ..> Verdict : returns
```

`Action` is fully defined in `spork.core.rules`'s own diagram — reused
here, not redefined, so a Tier 2 verdict and a Tier 1 rule produce the
exact same terminal-action shape.

#### `spork.core.llm.loader`

```mermaid
classDiagram
    class LLMClientLoadError { <<Exception>> }
    class load_llm_client {
        <<function>>
        +load_llm_client(spec: str, kwargs: dict) LLMClient
    }
    class LLMClient { <<Protocol>> }

    load_llm_client ..> LLMClient : constructs
    load_llm_client ..> LLMClientLoadError : raises
```

#### `spork.core.llm.clients.anthropic`

```mermaid
classDiagram
    class LLMClient { <<Protocol>> }
    class AnthropicLLMClient {
        -api_key: str
        -model: str
        -max_tokens: int
        +get_verdict(request: VerdictRequest) Verdict
    }

    LLMClient <|.. AnthropicLLMClient : structurally satisfies
    AnthropicLLMClient ..> NotImplementedError : raises (docs/ROADMAP.md M3)
```

`get_verdict()` requires a live Anthropic API call — same
settled-shape-stub reasoning as `JmapClient` (§9.3): constructor args
and the method signature are real, the call itself isn't yet.

#### `spork.core.actions`

```mermaid
classDiagram
    class ActionApplier { <<Protocol>> }
    class ActionExecutionError { <<Exception>> }
    class ActionExecutor {
        -applier: ActionApplier
        +execute(message: NormalizedMessage, action: Action) None
    }

    ActionExecutor --> ActionApplier : delegates non-escalate actions to
    ActionExecutor ..> ActionExecutionError : raises
```

#### `spork.core.state`

```mermaid
classDiagram
    class AuditEntry {
        <<dataclass, frozen>>
        +id: int
        +ts: str
        +jmap_id: str
        +event: str
        +detail_json: Optional~str~
    }
    class StateDB {
        -conn: Connection
        +get_cursor(account_id: str) Optional~str~
        +set_cursor(account_id: str, state: str) None
        +has_processed(jmap_id: str) bool
        +mark_processed(jmap_id: str, ...) None
        +write_audit_entry(...) None
        +get_audit_entries(jmap_id: Optional~str~) list
        +close() None
    }

    StateDB ..> AuditEntry : returns from get_audit_entries()
```

#### `spork.core.pipeline`

Two diagrams: the generic framework (`core.py`), then the concrete
message pipeline built on top of it (`meta.py`/`modules.py`/`default.py`)
— see §9.4 for the full explanation.

```mermaid
classDiagram
    class Payload~M~ {
        <<dataclass, frozen>>
        +text: str
        +meta: M
    }
    class Filter~M~ {
        <<Protocol>>
        +apply(payload: Payload~M~) Payload~M~
    }
    class Augment~M~ {
        <<Protocol>>
        +augment(payload: Payload~M~) Payload~M~
    }
    class Selector~M~ {
        <<Protocol>>
        +select(payload: Payload~M~) tuple
    }
    class UnknownBranchError { <<Exception>> }
    class Pipeline~M~ {
        -stages: list
        -selector: Optional~Selector~
        -routes: dict
        +run(payload: Payload~M~) Payload~M~
    }

    Pipeline --> Filter : runs each in order (via .apply)
    Pipeline --> Augment : runs each in order (via .augment)
    Pipeline --> Selector : follows its chosen branch
    Pipeline --> Pipeline : a route value is itself a Pipeline
    Pipeline ..> UnknownBranchError : raises
```

`core.py` knows nothing about messages, rules, or the state DB —
`Payload`/`Filter`/`Selector`/`Augment`/`Pipeline` are generic over a
metadata type `M`, provably reusable for a differently-shaped
pipeline, not just this one. `Filter` and `Selector` are conventionally
pure (no I/O); `Augment` is the type for a stage that reaches outside
the payload it was given (a database search, a contact lookup) —
`Pipeline.run` tells them apart by `isinstance`, dispatching to
`.augment()` or `.apply()` accordingly.

```mermaid
classDiagram
    class Filter { <<Protocol>> }
    class Selector { <<Protocol>> }
    class ActionExecutor
    class StateDB
    class evaluate { <<function>> }

    class MessageMeta {
        <<dataclass, frozen>>
        +message: NormalizedMessage
        +rules: Sequence~Rule~
        +default_unmatched_action: Action
        +classifier: Optional~TextClassifier~
        +verdict: Optional~RuleVerdict~
        +ts: Optional~str~
        +audit_event: Optional~str~
        +audit_detail_json: Optional~str~
    }
    class MissingMetaError { <<Exception>> }

    class IdempotencyGateSelector {
        -state_db: StateDB
        +select(payload) tuple
    }
    class TimestampFilter {
        -now: function
        +apply(payload) Payload
    }
    class RuleEvaluationSelector {
        +select(payload) tuple
    }
    class ApplyActionFilter {
        -executor: ActionExecutor
        +apply(payload) Payload
    }
    class RecordEscalationFilter {
        +apply(payload) Payload
    }
    class WriteAuditEntryFilter {
        -state_db: StateDB
        +apply(payload) Payload
    }
    class MarkProcessedFilter {
        -state_db: StateDB
        +apply(payload) Payload
    }

    Selector <|.. IdempotencyGateSelector : structurally satisfies
    Filter <|.. TimestampFilter : structurally satisfies
    Selector <|.. RuleEvaluationSelector : structurally satisfies
    Filter <|.. ApplyActionFilter : structurally satisfies
    Filter <|.. RecordEscalationFilter : structurally satisfies
    Filter <|.. WriteAuditEntryFilter : structurally satisfies
    Filter <|.. MarkProcessedFilter : structurally satisfies

    ApplyActionFilter ..> MissingMetaError : raises
    WriteAuditEntryFilter ..> MissingMetaError : raises
    MarkProcessedFilter ..> MissingMetaError : raises

    RuleEvaluationSelector ..> evaluate : Tier 1 evaluation
    ApplyActionFilter --> ActionExecutor : delegates non-escalate actions to
    IdempotencyGateSelector --> StateDB
    WriteAuditEntryFilter --> StateDB
    MarkProcessedFilter --> StateDB

    class build_default_pipeline {
        <<function>>
        +build_default_pipeline(executor, state_db, now) Pipeline
    }
    class process_message {
        <<function>>
        +process_message(message, rules, default_unmatched_action, executor, state_db, classifier, now) Optional~RuleVerdict~
    }
    build_default_pipeline ..> IdempotencyGateSelector : composes
    build_default_pipeline ..> TimestampFilter : composes
    build_default_pipeline ..> RuleEvaluationSelector : composes
    build_default_pipeline ..> ApplyActionFilter : composes
    build_default_pipeline ..> RecordEscalationFilter : composes
    build_default_pipeline ..> WriteAuditEntryFilter : composes
    build_default_pipeline ..> MarkProcessedFilter : composes
    process_message ..> build_default_pipeline : builds, then runs
```

The orchestrator §9 describes in prose — ties idempotency, evaluation,
action execution, and audit logging into the one call a real message
goes through, now composed from these seven modules instead of one
function body. `ActionExecutor`/`StateDB`/`evaluate` are fully defined
in their own diagrams above.

#### `spork.core.secrets`

```mermaid
classDiagram
    class SecretsError { <<Exception>> }
    class Secrets {
        <<dataclass, frozen>>
        -values: dict
        +get(name: str) str
    }
    class resolve_secrets {
        <<function>>
        +resolve_secrets(path, reason, provider, profile) Secrets
    }

    resolve_secrets ..> Secrets : produces
    resolve_secrets ..> SecretsError : raises
    Secrets ..> SecretsError : raises, on an unresolved get()
```

#### `spork.cli`

```mermaid
classDiagram
    class RulesLoadError { <<Exception>> }
    class load_rules { <<function>> }

    class app {
        <<Typer App>>
        spork
    }
    class rules_app {
        <<Typer App>>
        rules
    }
    class test {
        <<Typer command>>
        +test(rules_file: Path) None
    }
    class doctor {
        <<Typer command>>
        +doctor() None
    }

    app --> rules_app : add_typer("rules")
    app --> doctor : command("doctor")
    rules_app --> test : command("test")
    test ..> load_rules : loads/validates rules.toml
    test ..> RulesLoadError : catches, clean CLI error
    doctor ..> NotImplementedError : catches JMAP-connectivity stub, clean CLI error
```

#### `spork.daemon`

```mermaid
classDiagram
    class main {
        <<Typer command>>
        +main(version: bool) None
    }
    class run {
        <<function>>
        +run() None
    }

    run --> main : typer.run(main)
```

Still just the `--version`/`--help` handling plus a settled-shape
`NotImplementedError` for the real event loop (docs/ROADMAP.md M1) —
this diagram will grow substantially once the daemon actually wires
`spork.core`'s pieces together.

## 7. Data & configuration

### 7.1 Project layout (UV-managed)

Dashed boxes are planned, not built yet (`systemd/` lands with M6).

```mermaid
flowchart TD
    root["friendly-octo-spork/"] --> pyproject["pyproject.toml<br/>[project.scripts] sporkd + spork"]
    root --> uvlock["uv.lock"]
    root --> secretspec["secretspec.toml<br/>declared secrets, §7.3"]
    root --> claudemd["CLAUDE.md<br/>agent guidance"]
    root --> src["src/spork/...<br/>see §6.1"]
    root --> systemd["systemd/<br/>sporkd.service (M6)"]:::planned
    root --> tests["tests/<br/>mirrors src/spork/ 1:1"]
    root --> docs["docs/"]
    root --> readme["README.md"]

    docs --> design["DESIGN.md"]
    docs --> roadmap["ROADMAP.md"]
    docs --> coverage["TEST_COVERAGE.md"]

    classDef planned stroke-dasharray: 4 3,opacity:0.65
```

`uv sync` sets up the dev environment; `uv run sporkd` / `uv run spork`
during development. Packaged entry points (`sporkd`, `spork`) are what
the systemd unit and an installed `uv tool install` invoke.

### 7.2 App config (`config.toml`)

Lives at `$XDG_CONFIG_HOME/spork/config.toml` (default
`~/.config/spork/config.toml`). Not secret — safe to keep in a dotfiles
repo.

```toml
[jmap]
host = "api.fastmail.com"
account_email = "will@example.com"   # used to resolve the JMAP account ID

[polling]
push_enabled = true
fallback_poll_interval_seconds = 300
reconnect_backoff_seconds = [2, 5, 15, 60, 300]

[tiering]
default_unmatched_action = "escalate"   # "escalate" | "notify" | "ignore"
tier2_confidence_alert_threshold = 0.55  # below this, always alert (Tier 3)
tier2_confidence_autoact_threshold = 0.85 # above this, act without alert
local_classifier = "keyword_heuristic"    # name registered in classify/registry.py — swap
                                           # to experiment with a different local text-processing
                                           # backend; see §9.1

[llm]
model = "claude-sonnet-5"
max_tokens = 1024
daily_call_budget = 200          # hard stop; degrade to Tier 3-only past this

[alerts]
backend = "desktop"              # "desktop" | "webhook" | "none"
webhook_url_secret = "ALERT_WEBHOOK_URL"   # name of a secretspec entry

[state]
db_path = "~/.local/share/spork/state.sqlite3"

[rules]
path = "~/.config/spork/rules.toml"
```

### 7.3 Secrets (`secretspec.toml`)

Spork declares its secrets with [SecretSpec](https://github.com/cachix/secretspec)
rather than ad hoc `.env` files. `secretspec.toml` ships in the repo (it
declares *what* is needed, not the values); actual values live in
whatever backend the user configures (system keyring by default —
1Password or another provider is a per-user choice, not something Spork
hardcodes).

```toml
[project]
name = "spork"
revision = "1.0"

[profiles.default]
JMAP_API_TOKEN = { description = "Fastmail JMAP API token (Settings → Privacy & Security → New API token)" }
ANTHROPIC_API_KEY = { description = "Claude API key for Tier 2 classification" }
ALERT_WEBHOOK_URL = { description = "Optional webhook (e.g. ntfy/pushover) for alerts", required = false }

[profiles.development]
JMAP_API_TOKEN = { required = false, prompt = true }
ANTHROPIC_API_KEY = { required = false, prompt = true }

[providers]
default = "keyring://"
```

- `sporkd` resolves secrets once at startup via the SecretSpec Python
  SDK (not by shelling out to `secretspec run`, since it's a long-lived
  process) and holds them in memory only; they are never written to the
  state DB or logs.
- `spork doctor` runs the equivalent of `secretspec check` and reports
  missing/misconfigured secrets in plain language.
- Every secret access is covered by SecretSpec's built-in audit log
  (who/when/outcome) — Spork does not need to build its own.

### 7.4 State store (SQLite)

Single file, WAL mode, no external DB dependency. Tables (indicative,
not final):

- `processed_messages(jmap_id, thread_id, received_at, tier_reached, verdict_json, action_taken, processed_at)`
  — the dedupe/idempotency key. A message is only ever acted on once
  unless a manual `spork reclassify` forces it.
- `audit_log(id, ts, jmap_id, event, detail_json)` — human-readable
  trail for `spork logs`.
- `rule_stats(rule_id, matches, last_matched_at)` — powers
  `spork rules stats` so unused/over-firing rules are visible.
- `push_cursor(account_id, state)` — the last JMAP `state` string seen,
  so a restart resumes from where it left off instead of re-scanning the
  whole mailbox.
- `llm_usage(date, calls, tokens_in, tokens_out)` — feeds the daily
  budget check in §7.2.

### 7.5 Rules (`rules.toml`)

Rules are Tier 1 only — deterministic, no network calls, fast enough to
run on every message. A rule is a condition + action, evaluated in
order; first match wins per phase (a message can still be *tagged* by
multiple rules if authored that way, but only one terminal action fires).

```toml
[[rule]]
id = "known-newsletter-senders"
description = "File known newsletters straight to Reading"
when = { from_domain_in = ["substack.com", "newsletter.example.com"] }
action = { type = "move", mailbox = "Reading" }
enabled = true

[[rule]]
id = "calendar-invites"
when = { has_header = "text/calendar" }
action = { type = "tag", mailbox = "Calendar" }

[[rule]]
id = "vip-senders"
description = "Anything from these addresses always alerts, never auto-filed"
when = { from_in = ["boss@example.com", "spouse@example.com"] }
action = { type = "escalate", reason = "vip_sender" }

[[rule]]
id = "default-escalate"
description = "Fallback: anything unmatched goes to the LLM"
when = { always = true }
action = { type = "escalate" }
enabled = true

[[rule]]
id = "locally-scored-urgent"
description = "Local classifier (§9.1) flags urgency; skip straight to alert"
when = { local_classifier_category_in = ["urgent"] }
action = { type = "escalate", reason = "local_classifier_urgent" }
enabled = true
```

`local_classifier_category_in` is resolved by calling the configured
`TextClassifier` backend (§9.1) once per message and checking its
`category` — swapping `tiering.local_classifier` in `config.toml`
changes what this condition sees without editing the rule.

`when` conditions are a closed, declarative set (sender/domain lists,
subject/header regex, mailbox membership, list-unsubscribe header
presence, thread-has-prior-reply, etc.) — deliberately **not** arbitrary
Python, so `spork rules test <file>` can safely dry-run untrusted rule
edits against sample messages without executing user code. Complex
conditions that don't fit the schema are a signal to write a Sieve rule
(Tier 0) instead, or accept the message going to Tier 2.

`action.type = "escalate"` is what hands a message to Tier 2; everything
else is a terminal Tier 1 action and never invokes the LLM.

## 8. JMAP integration

- **Client library:** [`jmapc`](https://github.com/smkent/jmapc) — has
  Email query/get/set, EventSource push, and Fastmail-specific methods
  already wrapped; no need to hand-roll the protocol.
- **Auth:** bearer API token (from secretspec), scoped to the mail
  account only where Fastmail's token scoping allows it.
- **Push:** EventSource subscription to the mail account's state
  changes. On disconnect, exponential backoff per `config.toml`, with a
  poll-based fallback so a flaky connection degrades to "slower" rather
  than "silent."
- **Fetch pattern:** a single JMAP request batches `Email/query`
  (new/changed IDs since last cursor) and `Email/get` (headers + body
  for those IDs) using JMAP result references — one HTTP round trip per
  triage cycle, not N.
- **Mailboxes as tags:** Fastmail/JMAP allows a message to belong to
  multiple mailboxes. Spork uses this natively for triage buckets
  (`Urgent`, `Needs-Reply`, `FYI`, `Reading`, `Needs-Review`) via
  `Email/set` `mailboxIds` updates — no separate tag store.
  `Needs-Review` is the Tier 3 holding pen: Tier 2 verdicts below the
  autoact threshold land there in addition to alerting, so the human has
  a single place to work through them even if they miss the alert.
- **Drafts:** an LLM-suggested reply is written into the account's
  Drafts mailbox via `Email/set` (`keywords: {"$draft": true}`,
  correct `mailboxIds`, in-reply-to headers set for threading). Spork
  **never** calls `EmailSubmission/set`. Sending is always a human action
  from their normal mail client.
- **Sieve (Tier 0):** for the genuinely deterministic cases (known
  mailing lists, obvious auto-filing), push a Sieve script server-side
  via the Sieve JMAP extension (RFC 9661) / ManageSieve, so those
  messages are filed before Spork ever sees them and cost nothing. No
  Python library wraps the Sieve JMAP methods yet, so this is a small
  hand-rolled `SieveScript/get|set` client — tracked as its own
  roadmap item, not a blocker for v1.
- **Rate limits:** batch fetches, prefer push over polling, and back off
  on 429s using Fastmail's documented limits; the daemon logs (not
  crashes on) rate-limit responses.

## 9. Triage pipeline

```mermaid
flowchart TD
    newmsg(["new message"]) --> tier1{"Tier 1 rule engine<br/>(rules.toml, first match wins)"}
    tier1 -->|"terminal action<br/>(move / tag / ignore)"| done["apply, log, done"]
    tier1 -->|"escalate<br/>(explicit rule, or default-unmatched policy)"| tier2["Tier 2: Claude classification<br/>(see §10 for schema)"]
    tier2 --> conf{confidence}
    conf -->|"≥ autoact threshold"| act1["apply verdict's action, log<br/>(no alert unless verdict.urgent)"]
    conf -->|"< alert threshold"| act2["file to Needs-Review + alert (Tier 3)<br/>no auto-action"]
    conf -->|"between thresholds"| act3["apply action AND alert<br/>(acted on, but flagged for the human<br/>to sanity-check)"]
```

Rule *conditions* in the diagram above are plain deterministic matching
(sender, headers, regex — §7.5). Rules may additionally reference the
output of a **local classifier** (§9.1) as one more condition input, so
a rule can read e.g. "if the local classifier scores this `urgent` and
the sender isn't a known list, escalate" without that scoring logic
living in the rule engine itself.

**Orchestration: `spork.core.pipeline`** ties the idempotency check
(`StateDB.has_processed`), the rule engine, the action executor, and
the audit log into the single call a real message goes through: skip
if already processed; otherwise evaluate, act (or not), record. A
message is only ever marked processed *after* its action successfully
applies — if the executor raises, nothing is recorded, so a retry (the
next poll/push cycle) picks the same message up again rather than
silently losing it. `process_message()` (the public entry point M2
shipped, and every existing caller/test's contract) is a thin wrapper
over a pipeline **composed from independently testable/benchmarkable
Filter and Selector modules** — see §9.4.

**Interim policy for `escalate` before Tier 2 exists (M3).** A verdict
that resolves to `escalate` has nowhere to actually go until M3 builds
the Claude call — `process_message()` doesn't call the action executor
for it (which would reject `escalate` anyway, §9.3), writes an audit
entry noting the message is escalated-pending-Tier-2, and marks it
processed regardless, so the daemon doesn't re-evaluate (and re-pay any
classifier cost for) the same message every cycle while Tier 2 remains
unbuilt. This is a deliberate, temporary trade-off — once M3 lands,
this policy is revisited so escalated messages actually get a Tier 2
verdict instead of being marked done. Reprocessing an already-escalated
message once Tier 2 exists is what `spork reclassify` (M5) is for.

### 9.1 Modularity: pluggable local classifiers

Tier 2 (Claude) is the expensive, capable tier; Tier 1 rules (§7.5) are
free but purely deterministic. There's a useful middle tier — cheap,
local, *non*-LLM text processing (keyword/regex scoring today; nothing
rules out a small local model, spaCy pipeline, fastText classifier, or a
scikit-learn bag-of-words model later) that can produce signals like
"looks urgent" or "looks like a newsletter" for rules to key off, without
spending an API call. This is explicitly designed as a swap point, not a
fixed implementation, because the right technique here is genuinely an
open experiment — what scores well on one person's mail may not on
another's.

The contract is a small `Protocol` (`spork.core.classify.base.TextClassifier`):

```python
class TextClassifier(Protocol):
    def classify(self, message: NormalizedMessage) -> ClassificationResult:
        """Score/label a message. Must be local and fast — no network
        calls, no LLM. Implementations decide their own labels/scores;
        rules opt into whichever ones they care about by name."""
        ...
```

- **`ClassificationResult`** is deliberately loose (a category label plus
  an open `scores: dict[str, float]` bag) rather than a fixed enum, so a
  new backend isn't forced into categories designed for a different
  technique.
- **Registry, not inheritance.** Backends self-register under a string
  name (`spork.core.classify.registry`); `config.toml`'s
  `tiering.local_classifier` picks one by name. Swapping techniques is a
  one-line config change, never a code change to the rule engine or the
  daemon pipeline.
- **Default backend ships dependency-free**: a keyword/regex heuristic
  (`classify/keyword.py`) so the tool works out of the box with zero
  extra installs. Anything heavier (spaCy, a local embedding model, a
  small fine-tuned classifier) is an additional backend module behind
  the same `Protocol` — added, not swapped in by editing existing code.
- **No implicit fallback.** An unresolvable/misconfigured classifier name
  is a startup-time config error (`spork doctor` catches it), not a
  silent no-op — a rule that references classifier output should never
  quietly stop firing because a backend failed to load.
- This tier is optional: rules that don't reference classifier output
  never invoke it, so it costs nothing for a config that doesn't use it.

### 9.2 Modularity: message sources and multi-target dispatch

§9.1 makes *which classifier* swappable. This section makes *where
messages come from* and *how many classifiers see each one* swappable
too, using the same "protocol + small composable pieces" approach
rather than one bespoke pipeline hardcoded to JMAP.

**Sources: decoupling *when* from *what*.** Every way spork receives
mail decomposes into two independent concerns:

```python
class Trigger(Protocol):
    """Decides *when* to fetch — knows nothing about content."""

    def wait(self) -> None:
        """Block until it's time to fetch again."""
        ...


class ContentFetcher(Protocol):
    """Decides *what* to fetch, once triggered — knows nothing about timing."""

    def fetch(self) -> Sequence[NormalizedMessage]: ...


class Source(Protocol):
    """What the pipeline actually pulls from."""

    def poll(self) -> Sequence[NormalizedMessage]: ...
```

A generic `TriggeredSource(trigger, fetcher)` composes any `Trigger` +
any `ContentFetcher` into a `Source` by calling `trigger.wait()` then
`fetcher.fetch()`. Three concrete shapes this takes:

| Trigger | ContentFetcher | Notes |
|---|---|---|
| JMAP `EventSource` push | `Email/query`+`Email/get` batch | In practice implemented as one `Source`, not composed — the push payload's state token *is* the fetch call's argument, so splitting them buys nothing here. |
| Interval timer | IMAP `FETCH` | A real case for composing two independently-testable, independently-swappable pieces via `TriggeredSource`. |
| `ImmediateTrigger` (no-op wait) | `SequenceContentFetcher` (pre-loaded list) | The "replay a test/demo file through a for-loop" debug source — gets built for free from two small, otherwise-reusable pieces, no bespoke class needed. |

Only the third row exists yet (docs/ROADMAP.md); JMAP push and
IMAP-polling `Source`/`Trigger`/`ContentFetcher` implementations are
real-I/O work that lands with M1's remainder. The point of settling the
protocol now is that the rest of the pipeline (dispatch, rule engine)
never needs to know which row produced a given `NormalizedMessage`.

**Dispatch: one message, one or many classifier targets.** A
`Dispatcher` fans a single message out to any number of named
`TextClassifier` backends (§9.1) — "one" is just the N=1 case, no
special-cased path:

```python
class Dispatcher:
    def __init__(self, targets: Mapping[str, TextClassifier]) -> None: ...
    def dispatch(self, message: NormalizedMessage) -> dict[str, ClassificationResult | Exception]:
        """Run every target; a target that raises is captured as its
        own result entry rather than aborting the others — one broken
        experimental backend must never take production classification
        down with it."""
```

Failure isolation is deliberate: the whole reason to dispatch to
multiple targets is to run a *candidate* classifier alongside a
*production* one, and a candidate is allowed to be half-finished or
flaky.

That one primitive supports two different things people mean by
"running classifiers in parallel," without needing two different
mechanisms:

1. **Evaluation / shadow mode.** Call `dispatcher.dispatch()` directly
   and log/compare all N results. The actual triage decision is
   unaffected — a candidate classifier gets to prove itself on live
   traffic before anyone trusts its output.
2. **Ensemble feeding one decision.** Wrap the `Dispatcher` and a
   `Combiner` (reduces N results to 1) in a `DispatchingClassifier`:

   ```python
   class Combiner(Protocol):
       def combine(
           self, results: Mapping[str, ClassificationResult | Exception]
       ) -> ClassificationResult: ...


   class DispatchingClassifier:
       """A TextClassifier whose classify() dispatches to N targets and
       combines their results — from the rule engine's point of view,
       indistinguishable from a single classifier."""

       def __init__(self, dispatcher: Dispatcher, combiner: Combiner) -> None: ...
       def classify(self, message: NormalizedMessage) -> ClassificationResult: ...
   ```

   Because `DispatchingClassifier` satisfies the same `TextClassifier`
   protocol as any single backend, `spork.core.rules.engine.evaluate()`
   (§9) needs **zero changes** to consume an ensemble instead of one
   classifier — it was already decoupled from "how many techniques
   produced this answer" by §9.1's design.

Two built-in combiners cover the common cases: one that always defers
to a named primary target (shadow-mode-as-a-classifier: the others ran
and are inspectable, but only the primary's opinion is the decision),
and one that picks whichever successful result reports the highest
confidence score. Both are swappable the same way classifier backends
are — a `Combiner` is a small enough contract that a bespoke one
(majority vote, "escalate if any target says urgent") is cheap to add
later without touching `Dispatcher` or `DispatchingClassifier`.

### 9.3 Modularity: pluggable mail-backend providers

§9.2 settled *how a message gets acquired* (`Trigger`+`ContentFetcher`
→ `Source`) as a transport-agnostic shape. This section settles the
layer above it: JMAP is the only backend spork talks to today, but
it's built as one **provider** behind a common adapter, not baked into
the daemon, so a second backend (IMAP was the running example back in
§9.2) is an addition, not a rewrite.

```python
class ActionApplier(Protocol):
    """Applies one rule/verdict Action to a message on the remote backend."""

    def apply(self, message: NormalizedMessage, action: Action) -> None: ...


class Provider(Protocol):
    """What every mail-backend integration adapts to.

    A provider is the daemon's *entire* relationship to one remote
    source of truth — reading from it (`build_source`) and writing to
    it (`build_action_applier`) are two operations against the same
    backend, not separate concerns that happen to share one. Mailbox
    role resolution and anything else backend-specific is reached
    through whatever a provider hands back, not through this Protocol
    — but read and write both belong here.
    """

    def build_source(self) -> Source: ...
    def build_action_applier(self) -> ActionApplier: ...
```

`spork.core.actions.executor.ActionExecutor` (M2) is the one consumer
of `ActionApplier` — it takes whatever a provider's
`build_action_applier()` returns, applies `move`/`tag`/`ignore`
actions, and rejects `escalate` outright (reaching the executor with
one means something upstream routed a Tier-2-only action to the
terminal step by mistake). `ActionApplier` lives in
`spork.core.providers.base` alongside `Provider`, not in
`spork.core.actions` — it's provider-owned I/O; `ActionExecutor` is
generic business logic that depends on it, not the reverse.

- **Package layout: `spork.core.providers.<name>`.** JMAP's
  client/push/mailbox/backoff modules move from
  `spork.core.jmap` to `spork.core.providers.jmap` — a future IMAP
  backend lands as a sibling package (`spork.core.providers.imap`),
  not a special case bolted onto the JMAP one.
- **The Adapter: `JmapProvider`.** Wraps `JmapClient` +
  `JmapPushTrigger` (§8) into a `Source` via the existing
  `TriggeredSource` (§9.2) for `build_source()`, and wraps
  `JmapClient.apply_action()` (the third `NotImplementedError` stub
  alongside `connect()`/`fetch_new_messages()`, same reason — a live
  session is real-network work) for `build_action_applier()`.
  `JmapProvider` doesn't reimplement fetch/push/mutate logic, it
  composes pieces that already exist into the shape `Provider`
  promises.
- **Loadable at runtime: `spork.core.providers.loader`.** A provider is
  named in config as a `"module.path:ClassName"` spec (e.g.
  `"spork.core.providers.jmap.provider:JmapProvider"`) and resolved via
  `importlib` at startup, the same way `tiering.local_classifier`
  names a classifier backend (§9.1) — except here the payoff is bigger:
  spork never imports a provider's dependencies (`jmapc`, an eventual
  IMAP library) unless that provider is the one actually configured.
  Swapping providers, or adding a third-party one, is a config change
  plus an installed package — never an edit to `spork.core.providers`
  itself.
- **Fails loud on a bad spec.** A malformed spec, an unimportable
  module, a missing class, or a constructor that rejects the given
  config all raise a single `ProviderLoadError` — `spork doctor` (M5)
  catches this the same way it catches an unknown classifier name
  (§9.1).
- **A second, fully real Adapter: `FileProvider`.** `JmapProvider` is
  the only provider spork ships that talks to a live backend, and it's
  still mid-M1 (`connect()`/`fetch_new_messages()`/`apply_action()` are
  settled-shape `NotImplementedError` stubs) — which means until a
  live Fastmail session exists, nothing has ever actually exercised
  `Provider` as an *abstraction* end to end, only as one
  half-implemented instance of it. `spork.core.providers.file.FileProvider`
  closes that gap: it adapts a literal, explicitly-supplied JSON file
  of messages to `Provider`, with no NotImplementedError anywhere.
  `build_source()` replays the file's messages once via
  `ImmediateTrigger` + `SequenceContentFetcher` (§9.2); `build_action_applier()`
  appends every applied action to a JSON-lines log instead of mutating
  anything, since there's no real mailbox underneath to mutate. It is
  **not** a way to fake "recent mail" for `JmapProvider` or for `spork
  rules test` (§13) — spork has no local mail store to substitute for
  one, and `FileProvider` doesn't pretend to be JMAP or claim to be
  live mail at all. Its purpose is narrower and more useful: proving,
  with a real second implementation, that `Provider`'s read/write split
  actually holds for a backend other than JMAP — plus a genuinely handy
  building block for local dev/demo/CI work that wants a Provider
  without any network dependency.

### 9.4 Modularity: Filter/Selector/Augment pipeline modules

Message processing is a fixed sequence today, but M3 adds a real fork:
an escalated verdict needs to go somewhere — a Tier 2 LLM call —
before anything is applied, and building that LLM call's prompt is
going to need context a message doesn't carry on its own (a thread's
prior messages, a sender's contact record). Rather than growing
`process_message()`'s body with another
`if verdict.action.type == "escalate":` branch (the pattern that would
keep recurring at every future tier), `spork.core.pipeline` is built
from three structural kinds of module, generic over a metadata type
`M` (`spork.core.pipeline.core`):

```python
@dataclass(frozen=True, slots=True)
class Payload(Generic[M]):
    """The (text, metadata) unit every module reads and returns.

    `text` is whatever content payload is currently in flight — a
    message body for a cleaning/prompt-building chain, unused (left
    alone) by a module that only cares about `meta`. `meta` is a
    concrete, typed value per pipeline (never a loose dict — see
    MessageMeta below) so mypy --strict still catches a module reading
    a field another module never set.
    """

    text: str
    meta: M


class Filter(Protocol[M]):
    """A module that transforms one Payload into another. Always
    produces exactly one output — no branching, no routing.
    Conventionally *pure*: no I/O, deterministic given its input — see
    `Augment` for the type that's expected to reach outside the
    payload."""

    def apply(self, payload: Payload[M]) -> Payload[M]: ...


class Selector(Protocol[M]):
    """A module that reads one Payload and routes it to exactly one of
    its named branches, chosen per-payload — the sole place branching
    logic lives, so no Filter ever needs an if/else about what happens
    next. Conventionally pure like `Filter` — routing decisions read
    `meta`, they don't fetch anything to make one."""

    def select(self, payload: Payload[M]) -> tuple[str, Payload[M]]: ...


class Augment(Protocol[M]):
    """A module that enriches a Payload with additional context before
    passing it on — the type for I/O: a database search for a
    message's thread history, a contact-details lookup, anything that
    reaches outside the payload it was given.

    Same one-in-one-out shape as `Filter` and interchangeable with it
    inside a `Pipeline`'s stage list — the split is not about output
    shape, it's a signal to the reader (and to `Pipeline.run`, which
    dispatches on it via `isinstance`) that this stage is expected to
    talk to something external. Nothing in the type system stops a
    `Filter` from doing I/O; the split exists so a module's declared
    type alone tells a reader — and its own tests — whether to expect
    a real dependency.
    """

    def augment(self, payload: Payload[M]) -> Payload[M]: ...


Stage = Filter[M] | Augment[M]


class Pipeline(Generic[M]):
    """Composes modules: a straight-line chain of Filters/Augments,
    optionally ending in a Selector whose branches are themselves
    Pipelines.

    Recursive by construction — a `routes` value is just another
    Pipeline, so an arbitrarily deep branching tree is built by nesting
    Pipeline(...) calls, never by teaching this class about a specific
    branch's meaning. An empty Pipeline() (no stages, no selector) is
    the identity — the natural "this branch stops here." Filters and
    Augments interleave freely in one `stages` list — dispatched via
    `isinstance(stage, Augment)` (`.augment()`) or otherwise (`.apply()`)
    — so an Augment (fetch contact) can sit between two Filters
    (clean, then compose) with no separate list to keep in sync.
    """

    def __init__(
        self,
        stages: Sequence[Stage[M]] = (),
        *,
        selector: Selector[M] | None = None,
        routes: Mapping[str, "Pipeline[M]"] | None = None,
    ) -> None: ...
    def run(self, payload: Payload[M]) -> Payload[M]: ...
```

`spork.core.pipeline`'s three existing state-DB-touching modules
(`IdempotencyGateSelector`'s read, `WriteAuditEntryFilter`'s and
`MarkProcessedFilter`'s writes) predate the Filter/Selector purity
convention above and stay `Selector`/`Filter` rather than becoming
`Augment` — they're the pipeline's own bookkeeping (idempotency,
audit), not context fetched *for* a message, which is what `Augment`
is for. No concrete `Augment` ships yet: there's no live thread-search
or contact-lookup backend in this codebase to call (JMAP search is
still behind `NotImplementedError` — see §8), and stubbing one against
fake data would be exactly the thing CLAUDE.md's TDD rules forbid
faking. This section adds the framework-level `Augment` Protocol and
`Pipeline` support only; a concrete Augment lands when M3's
prompt-building chain actually needs one and can call something real.

`spork.core.pipeline.meta.MessageMeta` is the concrete metadata type
the M2/M3 message pipeline uses — `message`, `rules`,
`default_unmatched_action`, `classifier`, `verdict`, `ts`,
`audit_event`, `audit_detail_json`, all `Optional` until the module
responsible for that field has run. `spork.core.pipeline.modules`
implements the seven concrete Filters/Selectors that reproduce M2's
`process_message()` behavior exactly:

- **`IdempotencyGateSelector`** — branches `"skip"` (already processed)
  or `"continue"`.
- **`TimestampFilter`** — calls the injected clock exactly once; every
  later module reads the shared `meta.ts` rather than each calling its
  own clock (a real M2 behavior gap this refactor closes: the old
  `process_message()` called `now()` twice, once for the audit
  entry and once for `processed_at`, which could record two
  microseconds-apart timestamps for what's really one event).
- **`RuleEvaluationSelector`** — runs `rules.engine.evaluate()`, sets
  `meta.verdict`, branches `"terminal"` or `"escalate"`.
- **`ApplyActionFilter`** — calls `ActionExecutor.execute()` for a
  terminal verdict; sets `meta.audit_event`/`audit_detail_json`.
- **`RecordEscalationFilter`** — the `"escalate"` branch's counterpart:
  no action to apply, just sets `meta.audit_event =
  "escalated_pending_tier2"`.
- **`WriteAuditEntryFilter`** — writes whatever `meta.audit_event`/
  `audit_detail_json` describe via `state_db.write_audit_entry()`.
  Generic across both branches — it doesn't know or care which one set
  those fields.
- **`MarkProcessedFilter`** — writes `state_db.mark_processed()`.

`spork.core.pipeline.default.build_default_pipeline(...)` wires these
into the nested `Pipeline` `process_message()` runs — the same
construction M2's `process_message()` did inline, now named and
reusable on its own, and the exact seam M3's Tier 2 escalation work
slots into: the `"escalate"` route is a `Pipeline[MessageMeta]` like
any other, so replacing it with one that calls Claude first is a
change to *what pipeline that route points at*, never a rewrite of
`Pipeline`, `RuleEvaluationSelector`, or the `"terminal"` branch.

- **Independently validated.** A module's acceptance tests construct a
  bare `Payload` and assert what `.apply()`/`.select()`/`.augment()`
  returns — no `Pipeline`, no other module, no full `process_message()`
  call needed to test that `WriteAuditEntryFilter` writes the right
  entry, and (once one exists) a future `Augment`'s tests are free to
  mock exactly the one dependency it calls, nothing else in the chain.
- **Independently benchmarked.** `benchmarks/core/pipeline/` (outside
  `testpaths`, so it never runs as part of `uv run pytest` — a
  `pytest-benchmark` repeated-call timing run is a different kind of
  test than the correctness suite and shouldn't slow every push) times
  each module's `.apply()`/`.select()` in isolation via
  `pytest-benchmark`'s `benchmark` fixture. Run with
  `uv run pytest benchmarks/` — this is the seam that matters most for
  a future `Augment`: an I/O-bound lookup is exactly the kind of stage
  worth timing on its own, separate from the pure stages around it.
- **Composed.** `Pipeline` and `Payload`/`Filter`/`Selector`/`Augment`
  know nothing about messages, rules, or audit logs — `MessageMeta` and
  `spork.core.pipeline.modules` are one concrete use of a generic
  framework, provably reusable for a differently-shaped pipeline (M3's
  Tier 2 prompt-building chain — clean the body, look up thread/contact
  context, build the prompt, call Claude, parse the verdict — is a
  `Filter`/`Augment` chain over the same `Payload`/`Pipeline` machinery,
  not a new abstraction).

## 10. LLM integration (Claude API)

- **Model:** configurable, default `claude-sonnet-5` — cheap enough for
  per-message classification, capable enough for summarize/draft.
- **Input:** subject, from/to, a truncated/cleaned plaintext body
  (HTML stripped, quoted-reply chains collapsed), thread context (prior
  subject + whether the user has replied on this thread before), and
  the list of mailbox/tag names available so the model picks from a
  closed set rather than inventing categories.
- **Output:** structured (tool use / JSON schema) verdict:

```json
{
  "category": "needs_reply",
  "urgency": "high",
  "confidence": 0.78,
  "suggested_action": { "type": "tag", "mailbox": "Needs-Reply" },
  "summary": "Client is asking to move Thursday's call to Friday 2pm.",
  "draft_reply": "Hi ..., Friday 2pm works ...",
  "reasoning": "short justification, logged for audit, not shown in alerts"
}
```

- `category`/`suggested_action.mailbox` are validated against the closed
  set of configured mailboxes — an out-of-set value from the model is
  treated as a schema failure, not silently applied.
- `draft_reply` is optional and only populated for categories where a
  draft is configured as wanted (`config.toml` per-category toggle);
  when present it always goes through §7's draft-not-send path.
- **Cost control:**
  - Tier 1 already filters most volume out before any LLM call.
  - `daily_call_budget` hard-stops Tier 2 calls per day; once hit,
    everything that would've escalated instead goes straight to
    Needs-Review + alert ("LLM budget exhausted") so nothing is silently
    dropped.
  - Prompt kept short (truncated body, no full quoted history) to bound
    tokens per call; `llm_usage` table makes actual spend visible via
    `spork status`.

### 10.1 Modularity: the `LLMClient` adapter

Claude is the only Tier 2 backend spork talks to today, but — same
reasoning as §9.3's mail-backend `Provider` — it's built as one
**client** behind a common adapter, not called directly from the
pipeline, so a second backend (a different model provider entirely) is
an addition, not a rewrite.

```python
@dataclass(frozen=True, slots=True)
class VerdictRequest:
    """Everything an LLMClient needs to produce one Verdict — already
    assembled by the (not-yet-built) prompt-building step, so an
    LLMClient implementation never touches NormalizedMessage or the
    rule engine directly."""

    subject: str
    from_address: str
    to_addresses: tuple[str, ...]
    cleaned_body: str
    thread_prior_subject: str | None
    thread_user_has_replied: bool
    available_mailboxes: tuple[str, ...]


class Verdict(BaseModel):
    """One Tier 2 verdict — the parsed, schema-validated form of this
    section's JSON output. A pydantic model, not a dataclass (unlike
    VerdictRequest): this is the one place spork parses untrusted
    external structured output, same reasoning as `rules.schema`
    validating a hand-edited rules.toml."""

    model_config = ConfigDict(extra="forbid")

    category: str
    urgency: Literal["low", "medium", "high"]
    confidence: float  # Field(ge=0.0, le=1.0)
    suggested_action: Action  # reuses rules.schema.Action
    summary: str
    draft_reply: str | None = None
    reasoning: str


class LLMClient(Protocol):
    """What every Tier 2 backend adapts to: given one VerdictRequest,
    return one schema-validated Verdict."""

    def get_verdict(self, request: VerdictRequest) -> Verdict: ...
```

- **`Verdict` reuses `rules.schema.Action`** for `suggested_action` —
  the same terminal-action shape a Tier 1 rule produces, so
  `ActionExecutor` (M2) can consume either without knowing which tier
  produced it. `extra="forbid"` plus a `field_validator` rejecting
  `suggested_action.type == "escalate"` (a schema-level contradiction —
  a verdict already *is* Tier 2's output, there's nowhere further to
  escalate to) mean a malformed or hallucinated field is a validation
  failure at the client boundary, not something that reaches the
  executor. Validating `category`/`suggested_action.mailbox` against
  *this deployment's* configured set is deliberately a separate, later
  step (`docs/ROADMAP.md`'s "Verdict validation against configured
  mailbox/category set") — `Verdict` only enforces shape, not
  deployment-specific vocabulary.
- **Package layout: `spork.core.llm.clients.<name>`** — mirrors
  `spork.core.providers.<name>`. `AnthropicLLMClient` is the first (and
  today, only) implementation.
- **Loadable at runtime: `spork.core.llm.loader`** — a client is named
  in config (e.g.
  `[llm] client = "spork.core.llm.clients.anthropic:AnthropicLLMClient"`)
  and resolved via `importlib` at startup, identical mechanics to
  `spork.core.providers.loader.load_provider` (down to the error type's
  shape, `LLMClientLoadError`) — spork never imports the `anthropic`
  SDK unless an Anthropic client is the one actually configured.
- **`AnthropicLLMClient` is a settled-shape stub, like `JmapClient`.**
  `get_verdict()` requires a live Anthropic API call, which this
  environment can't exercise honestly — constructor args (`api_key`,
  `model`, `max_tokens`) and the method signature are settled now,
  `get_verdict()` raises `NotImplementedError` pointing at
  `docs/ROADMAP.md`'s M3 until a real call (and the recorded-response
  CI fixtures M3's last item calls for) lands. No `anthropic` import
  anywhere yet — same reason `jmapc` isn't imported by `JmapClient`
  (§9.3): the SDK isn't a dependency until there's a real call to make
  with it.

## 11. Safety & human-in-the-loop

- **Draft, never send.** No code path calls `EmailSubmission/set`. This
  is a hard invariant, not a config toggle, for v1.
- **Confidence gating.** Two thresholds (§7.2) create three bands:
  auto-act silently, auto-act + alert, alert-only-no-action. Defaults
  are conservative; tightening/loosening is a config change, not a code
  change.
- **Idempotency.** `processed_messages` ensures a message is only acted
  on once; reprocessing requires an explicit `spork reclassify <id>`.
- **Reversibility bias.** Default rule actions are mailbox
  moves/tags (reversible — move it back) rather than deletion. Deletion
  as an action type is deliberately out of scope for v1 rules.
- **Rule dry-run.** `spork rules test` evaluates a rule file against a
  sample of recent messages (fetched read-only) and prints what *would*
  happen, before it's enabled live.
- **Audit trail.** Every action taken (or alert raised) is logged with
  enough detail (`spork logs`) to answer "why did this happen to this
  email" after the fact.

## 12. Alerting

- Alert backends implement a small `Alerter` protocol
  (`notify(title, body, url=None, urgency=...)`), so backends are
  swappable via config without touching the daemon logic.
- **v1 backend: desktop notifications** — since `sporkd` runs as a
  systemd **user** service at login (same session as the user's
  desktop), it can talk to the session's notification service
  (`org.freedesktop.Notifications` over DBus, or `notify-send` as a
  simpler subprocess fallback).
- **Optional backend: webhook** — POST to a configured URL (ntfy,
  Pushover, a Slack incoming webhook, etc.) for when the user isn't at
  the machine. URL comes from a secretspec-managed secret, not plain
  config, since webhook URLs are bearer credentials.
- Alerts fire for: Tier 3 (below alert threshold), `urgency: high`
  verdicts regardless of confidence band, VIP-sender escalations, and
  daemon-health events (JMAP push disconnected > N minutes, LLM budget
  exhausted, daemon crash-looping).

## 13. CLI command reference (v1 surface)

```
spork status                  # daemon up/down, push connection state,
                               # queue depth, today's LLM spend vs budget
spork pause / resume          # stop/start Tier 1+2 processing without
                               # killing the daemon (push stays connected)

spork rules list              # show rules.toml, with per-rule match stats
spork rules test <file>       # dry-run a candidate rules.toml against
                               # recent mail, no side effects
spork rules edit              # open rules.toml in $EDITOR, validate on save,
                               # push a reload to sporkd if it's running
spork rules enable/disable <id>

spork config show             # effective config (secrets redacted)
spork config edit             # open config.toml in $EDITOR, validate on save

spork logs [--tail] [--since] [--message-id]
spork reclassify <message-id> # force a message back through the pipeline

spork doctor                  # secretspec check, JMAP auth check,
                               # systemd unit status, DB migration status
```

`spork rules test` genuinely requires a live JMAP connection — spork is
a pure client to JMAP as the source of truth (§9.3), with no local mail
store to substitute (beyond, potentially, a transient cache to survive
a mid-processing network drop, which is resilience, not an offline
mode). There's no fixture-file fallback for "recent mail": testing
against synthetic data isn't testing against recent mail, it's testing
against synthetic data, and the command would say something else if
that's what it did. Until M1's live JMAP fetch exists, `spork rules
test` loads and validates the given `rules.toml` (real, useful on its
own — catches a malformed file before it ever reaches the daemon) and
then fails clearly rather than pretending to dry-run anything.
`FileProvider` (§9.3) doesn't change this: it exists to prove the
`Provider` abstraction itself, not to give this command a fixture mode
it deliberately doesn't have.

## 14. systemd integration

`systemd/sporkd.service` (user unit, installed to
`~/.config/systemd/user/sporkd.service`):

```ini
[Unit]
Description=Spork JMAP email triage daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=%h/.local/bin/sporkd
Restart=on-failure
RestartSec=5
# Secrets are resolved by sporkd itself via the SecretSpec SDK at
# startup — no secret material is passed through the unit file.

[Install]
WantedBy=default.target
```

- `Type=notify` (sd_notify on successful JMAP session establishment) so
  `systemctl --user status` reflects real readiness, not just
  process-alive.
- `WantedBy=default.target` (not `graphical-session.target`) so it comes
  up on login whether or not a graphical session is present; the desktop
  alert backend degrades to "unavailable, log only" if there's no DBus
  session bus, rather than failing the whole unit.
- Install flow (`spork install-service` or documented manual steps):
  copy the unit file, `systemctl --user daemon-reload`,
  `systemctl --user enable --now sporkd`, `loginctl enable-linger
  <user>` if the user wants it running even when logged out entirely.

## 15. Security considerations

- Secrets never touch disk in Spork's own state (SQLite has no secret
  columns); SecretSpec's chosen provider (keyring by default) owns
  secret-at-rest storage.
- Local control socket is a Unix domain socket with filesystem
  permissions (0600, owned by the invoking user) — not a TCP port, so
  no network exposure and no auth scheme needed for v1.
- LLM prompts include email content by design (that's the point) — the
  design assumes the user is comfortable with their mail body going to
  the configured LLM provider. This is called out explicitly in the
  README, not buried.
- Rule conditions are a closed declarative schema specifically so
  `spork rules test` can be run against arbitrary/untrusted rule files
  without code execution risk.
- No outbound send capability at all in v1 — removes an entire class of
  "LLM did something embarrassing to a real recipient" risk.

## 16. Testing strategy

- **Unit:** rule engine (condition matching), verdict schema validation,
  action executor (mocked JMAP client), state DB migrations.
- **Contract/integration:** `jmapc` calls exercised against a recorded
  fixture (VCR-style cassette) of real (sanitized) JMAP responses, so
  tests don't require a live Fastmail account or network access in CI.
- **LLM:** prompt → verdict tests run against recorded Claude API
  responses for a fixed set of sample emails (not live calls in CI);
  a small manual/eval script (not CI-gated) for prompt-quality iteration
  against the live API.
- **End-to-end (manual, pre-release):** point at a real test Fastmail
  account, verify push connectivity, rule firing, draft creation, and
  systemd unit lifecycle.

## 17. Open questions / risks

- **Sieve JMAP client** (RFC 9661) has no existing Python library — needs
  to be hand-rolled. Scoping this small (get/set a single script) keeps
  it from blocking v1, which can ship with Tier 0 configured manually in
  Fastmail's UI instead.
- **Body cleaning for LLM input** (HTML stripping, quote-chain
  collapsing) is fiddly in practice; budget real iteration time here,
  it directly affects verdict quality.
- **Confidence calibration** — Claude's self-reported `confidence` is a
  starting point, not ground truth; the threshold defaults in §7.2 will
  need tuning against real usage before they're trustworthy.
- **DBus/notification availability** varies across desktop environments
  and headless setups (SSH-only login sessions) — the alert backend
  needs a clearly-communicated fallback (webhook, or log-only) rather
  than failing silently.
- **Multi-device Fastmail token** — if the user also uses Fastmail's own
  clients/rules concurrently, verify Spork's actions and Fastmail's
  native sort rules don't fight each other (e.g. both trying to move the
  same message).
