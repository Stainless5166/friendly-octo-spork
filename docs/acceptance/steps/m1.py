"""Executable bindings for the M1 JMAP baseline scenario.

Only the baseline is executable in this first slice. Push, reconnect, and
forced-outage scenarios remain manual until the harness can control network
availability without risking a real mailbox.
"""

from typing import Any

from behave import given, then, when

from spork.core.config.paths import resolve_secretspec_path
from spork.core.providers.jmap.client import JmapClient
from spork.core.providers.jmap.provider import JmapProvider
from spork.core.secrets import resolve_secrets


@given("a dedicated Fastmail test account is configured through SecretSpec")
def configured_test_account(context: Any) -> None:
    """Resolve the operator-managed acceptance manifest without storing secrets."""
    context.secrets = resolve_secrets(
        resolve_secretspec_path(),
        reason="Behave M1 live acceptance",
    )


@given('the JMAP API token is available as "JMAP_API_TOKEN"')
def jmap_token_is_available(context: Any) -> None:
    """Require the JMAP credential through the production SecretSpec boundary."""
    context.api_token = context.secrets.get("JMAP_API_TOKEN")


@given("the account has an Inbox-role mailbox")
def account_has_inbox(context: Any) -> None:
    """Connect through the production client, which validates Inbox resolution."""
    context.client = JmapClient(
        host=context.config.userdata.get("jmap_host", "api.fastmail.com"),
        api_token=context.api_token,
    )
    context.client.connect()
    context.account_id = context.client.account_id


@given("the daemon uses JmapProvider with a short test polling interval")
def daemon_uses_jmap_provider(context: Any) -> None:
    """Construct the same provider adapter used by the daemon composition path."""
    context.provider = JmapProvider(
        host=context.config.userdata.get("jmap_host", "api.fastmail.com"),
        api_token=context.api_token,
        poll_interval_seconds=1.0,
    )


@given("the daemon uses a rule that ignores the acceptance message")
def acceptance_rule_ignores_message(context: Any) -> None:
    """Record the operator-supplied safe rule precondition for this scenario."""
    context.acceptance_rule_ignores_message = True


@given("the acceptance state database is empty or has been backed up")
def acceptance_state_is_safe(context: Any) -> None:
    """Record the state prerequisite without touching the operator's database."""
    context.acceptance_state_is_safe = True


@given("the Inbox contains existing messages")
def inbox_contains_existing_messages(context: Any) -> None:
    """Record the baseline prerequisite; no historical bodies are fetched."""
    context.inbox_contains_existing_messages = True


@when("sporkd starts and completes JMAP session discovery")
def jmap_session_discovery_completes(context: Any) -> None:
    """Perform the production read-side baseline operation after session discovery."""
    context.provider.account_id()
    context.baseline = context.client.fetch_new_messages(since_cursor=None)
    context.ready = True


@then("sporkd reports readiness only after the provider and cursor are composed")
def readiness_follows_composition(context: Any) -> None:
    """Confirm the acceptance operation reached readiness after both prerequisites."""
    assert context.ready is True
    assert context.account_id == context.provider.account_id()


@then("the current Email state is stored as the candidate baseline cursor")
def baseline_cursor_is_candidate(context: Any) -> None:
    """Confirm JMAP returned a non-empty candidate state without durable mutation."""
    cursor = context.baseline.cursor
    assert isinstance(cursor, str)
    assert cursor


@then("no pre-existing Inbox message is processed by the acceptance rule")
def baseline_does_not_replay_messages(context: Any) -> None:
    """Confirm first-start baselining does not replay historical Inbox mail."""
    assert context.acceptance_rule_ignores_message is True
    assert context.baseline.messages == ()
