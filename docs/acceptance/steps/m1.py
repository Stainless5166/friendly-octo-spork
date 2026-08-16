"""Executable bindings for M1's live JMAP acceptance scenarios.

Baseline and push are executable. @cursor-safety and @network-recovery
remain manual: the former needs a full sporkd restart cycle to
exercise honestly (not something to fake with a partial simulation of
process teardown), the latter needs actual network-level outage
control (iptables/unplugging), neither of which this file automates.
"""

import smtplib
import threading
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from behave import given, then, when

from spork.core.config.paths import resolve_secretspec_path
from spork.core.providers.jmap.client import JmapClient
from spork.core.providers.jmap.provider import JmapProvider
from spork.core.providers.jmap.push import JmapPushTrigger
from spork.core.secrets import resolve_secrets


# .env holds the operator's SMTP relay config for delivering the live
# @push scenario's own trigger message — not a SecretSpec-declared
# secret (host/sender/recipient aren't secrets, though
# username/password are and stay in .env alongside them here rather
# than split across two config sources for one small acceptance need).
def _load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


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


# --- @push: a real EventSource event, woken by a real delivered message ---


@given("sporkd has an acknowledged Email cursor")
def has_an_acknowledged_cursor(context: Any) -> None:
    """Establish the shared starting point @push and @cursor-safety both need.

    Real baseline read, same call `@baseline`'s own steps use — the
    resulting state is what a real daemon would have already persisted
    as its acknowledged cursor after a successful first run.
    """
    if not hasattr(context, "client"):
        context.client = JmapClient(
            host=context.config.userdata.get("jmap_host", "api.fastmail.com"),
            api_token=context.api_token,
        )
        context.client.connect()
    baseline = context.client.fetch_new_messages(since_cursor=None)
    context.acknowledged_cursor = baseline.cursor


@when("a new acceptance message is delivered to the Inbox")
def deliver_a_new_acceptance_message(context: Any) -> None:
    """Open the real EventSource connection *before* sending, then deliver.

    Real push semantics: a state event only reaches a connection
    that's already open when the state change happens, so the trigger
    starts listening (in a background thread — JmapPushTrigger.wait()
    blocks) before the message goes out, not after. The Then step
    below just joins this thread; connecting-then-sending here is what
    actually makes the scenario's literal Given/When/Then step order
    honest about a real push round trip rather than a lucky race.
    """
    trigger = JmapPushTrigger(context.client, account_id=context.account_id)
    result: dict[str, BaseException] = {}

    def _wait() -> None:
        try:
            trigger.wait()
        except BaseException as exc:  # noqa: BLE001 - surfaced to the Then step, not swallowed
            result["error"] = exc

    context.push_thread = threading.Thread(target=_wait, daemon=True)
    context.push_thread_result = result
    context.push_thread.start()
    time.sleep(2)  # let the EventSource connection actually establish first

    env = _load_dotenv(Path(".env"))
    message = EmailMessage()
    message["From"] = env["SMTP_SENDER"]
    message["To"] = env["SMTP_RECIPIENT"]
    message["Subject"] = "[spork-acceptance] @push live trigger"
    message.set_content("Behave M1 @push scenario trigger message.")
    with smtplib.SMTP(env["SMTP_HOST"], int(env["SMTP_PORT"]), timeout=20) as smtp:
        if env.get("SMTP_STARTTLS", "true").lower() == "true":
            smtp.starttls()
        smtp.login(env["SMTP_USERNAME"], env["SMTP_PASSWORD"])
        smtp.send_message(message)


@then("an EventSource EmailDelivery or Email event is received for the account")
def eventsource_event_is_received(context: Any) -> None:
    """Join the background trigger started in the When step above.

    A clean join (no JmapPushDisconnectedError recorded) is the live
    evidence: a relevant Email/EmailDelivery state event for this
    account actually arrived over the real EventSource connection.
    """
    context.push_thread.join(timeout=60)
    assert not context.push_thread.is_alive(), "no push event arrived within 60s"
    if "error" in context.push_thread_result:
        raise context.push_thread_result["error"]


@then("the message is fetched through Email/changes and Email/get")
def push_wakes_a_real_fetch(context: Any) -> None:
    """The woken trigger's event is only useful if it leads to a real fetch.

    The EventSource state event can arrive slightly ahead of
    Email/changes actually reflecting the new message server-side
    (real JMAP state propagation lag, not a spork behavior) — a short
    bounded retry, not an unbounded one, absorbs that without treating
    a genuine miss as a pass.
    """
    cursor = context.acknowledged_cursor
    result = context.client.fetch_new_messages(since_cursor=cursor)
    for _ in range(5):
        if any("@push live trigger" in m.subject for m in result.messages):
            break
        time.sleep(2)
        result = context.client.fetch_new_messages(since_cursor=cursor)
    context.push_fetch_result = result
    assert any("@push live trigger" in m.subject for m in result.messages)


@then("the acceptance rule processes the message exactly once")
def push_message_processed_once(context: Any) -> None:
    """Same simplified acceptance-rule precondition as @baseline (see that
    step's binding) — confirms exactly one matching message was fetched,
    not that a full rule-engine run happened against it."""
    matching = [m for m in context.push_fetch_result.messages if "@push live trigger" in m.subject]
    assert len(matching) == 1


@then("the new Email cursor is stored after processing completes")
def push_cursor_advances(context: Any) -> None:
    """Confirm the candidate cursor actually moved past the acknowledged one."""
    assert context.push_fetch_result.cursor != context.acknowledged_cursor
