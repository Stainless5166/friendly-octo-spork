"""Acceptance test for replaying recorded JMAP flows through the mitm harness.

docs/ROADMAP.md M1c: `tests/fixtures/jmap/flows/*.flow` were recorded
once against the live account and are gitignored (real account
content, same privacy rule as the corpus) — nobody else's clone has
them, so this test skips instead of failing when they're absent,
rather than pretending CI can exercise something it genuinely can't.
Where they exist, `jmap_mitm_harness(replay_flows=...)` answers from
the real captured request/response shapes via mitmproxy's own
ServerPlayback addon, not this harness's hand-built canned responses —
proving the recordings are actually wired in, not just sitting on
disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spork.core.providers.jmap.client import JmapClient
from tests.support.jmap_mitm import jmap_mitm_harness

_FLOWS_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "jmap" / "flows"
_SESSION_FLOW = _FLOWS_DIR / "m1_live_session.flow"

pytestmark = pytest.mark.skipif(
    not _SESSION_FLOW.exists(),
    reason=f"{_SESSION_FLOW} not present locally (gitignored, M1c real-account recording)",
)


def test_baseline_fetch_replays_from_the_recorded_flow_not_a_canned_response() -> None:
    """No set_mailbox_response()/set_email_get_response() configured at all —
    every answer comes from the real recorded Session/Mailbox/get/Email/get
    exchange, proving replay_flows is actually driving the response, not
    this harness's usual hand-built fallback."""
    with jmap_mitm_harness(host="api.fastmail.com", replay_flows=[str(_SESSION_FLOW)]) as harness:
        client = JmapClient(
            host="api.fastmail.com", api_token="fake-token", client_factory=harness.client_factory()
        )

        client.connect()
        result = client.fetch_new_messages(since_cursor=None)

        assert client.account_id  # the real captured account id, not a fixture
        assert result.cursor  # the real captured baseline Email state
        assert result.messages == ()
        assert harness.requests_forwarded_upstream() == 0
