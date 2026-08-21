"""vulture whitelist — every name below was hand-verified against the
real code, not blindly accepted from `--make-whitelist`'s output (see
static_analysis/README.md for how each category was checked). Never
executed as Python — vulture only parses this file's AST and matches
bare names against what it found unused elsewhere, exactly like its
own `--make-whitelist` output.

Regenerate a candidate list after adding a new Typer command / pydantic
model / Protocol implementation with:
    uv run vulture src/spork --make-whitelist
Diff it against this file rather than replacing it wholesale — a name
that's new here still needs the same by-hand check the existing ones
got, not an automatic add.
"""

# --- Typer CLI commands: registered via @app.command(), dispatched by
# Typer at runtime from the function's own name — never called directly
# by name from Python, so vulture has no call site to find.
init  # cli/commands/config.py
show  # cli/commands/config.py
edit  # cli/commands/config.py, cli/commands/rules.py (two files, one name)
test  # cli/commands/rules.py
list_rules  # cli/commands/rules.py
enable  # cli/commands/rules.py
disable  # cli/commands/rules.py
secrets_group  # cli/commands/secrets.py — the Typer sub-app itself

# --- Provider/backend/combiner classes: loaded by "module:Class" string
# spec (spork.core.providers.loader) or referenced only via a Protocol
# type annotation — structurally satisfied (CLAUDE.md "Conventions"),
# never instantiated by literal name anywhere vulture can see.
DesktopAlerter
SmtpAlerter
EntityContextProvider
MarkdownVaultContextProvider
PrimaryCombiner
HighestConfidenceCombiner
DispatchingClassifier
LiteLLMClient
RecordedLLMClient
FileProvider
MailboxResolver
JmapProvider
RecordedReceiptExtractionClient
FallbackSource
_.lookup_service  # EntityContextProvider — called only via ContextProvider's own callers
_.refresh  # MailboxResolver — called only via the Trigger Protocol

# --- pydantic model machinery: read by pydantic's metaclass/validator
# decorator at (de)serialization time, never referenced by name in
# application code. model_config repeats once per pydantic model.
model_config
cls  # field_validator's required first argument
_.disallow_overlapping_kwargs  # a model_validator, called by pydantic
_._suggested_action_must_be_terminal  # a field_validator, called by pydantic
reasoning  # Verdict's own field — read by pydantic, not by name in code
metadata  # Verdict's own field — same as reasoning
provided_by  # a context/entities model field — same reasoning

# --- Standard library / Protocol required signatures: present because
# the interface requires them, not because application code calls them
# by name. Unused *in the body* is the whole point of __exit__'s three
# arguments and HTMLParser's callback override.
_.handle_data  # HTMLParser callback override (llm/clean.py's _TagStripper)
exc_type  # StateDB.__exit__
exc_value  # StateDB.__exit__
traceback  # StateDB.__exit__
raise_errors  # _JmapcClient Protocol stub's kwarg — real jmapc.Client honors it structurally
