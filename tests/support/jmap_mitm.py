"""In-process mitmproxy harness for JMAP fault-injection tests (docs/ROADMAP.md M1c).

Drives the real, unmodified production client_factory
(`spork.core.providers.jmap.client._default_client_factory`, i.e. real
`jmapc.Client`) through a local mitmproxy instance instead of a fake
jmapc-shaped test double. The addon always answers requests locally —
built from canned responses configured by the test, or a synthetic
fault (truncation, HTTP failure, EventSource death, latency) — and
never dials a real upstream host, so this is safe to run with no
network access and no real credentials.

The harness intercepts at the wire level (real HTTP over a real
`requests.Session`, matching by JMAP wire semantics: `.well-known/jmap`
session discovery, the batched method-call API endpoint, and the
EventSource stream) rather than injecting a fake jmapc client object,
so it can exercise `JmapClient`/`JmapPushTrigger` against genuine
transport failures instead of only test-double exceptions.

Recording real traffic against the maintainer's live account
(`tests/fixtures/jmap/flows/`, M1c's second checklist item) is a
separate, explicitly manual step — not exercised by this module.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import jmapc
from jmapc import methods as jmapc_methods
from jmapc.session import (
    Session,
    SessionCapabilities,
    SessionCapabilitiesCore,
    SessionPrimaryAccount,
)
from mitmproxy import http, options
from mitmproxy.tools.dump import DumpMaster

from spork.core.providers.jmap.client import ClientFactory, _default_client_factory

_WELL_KNOWN_PATH = "/.well-known/jmap"
_API_PATH = "/api/"
_EVENTSOURCE_PATH = "/eventsource/"
_ACCOUNT_ID = "account-1"
_STARTUP_TIMEOUT_SECONDS = 10.0


@dataclass
class _FaultState:
    """Mutable configuration shared between the harness and its addon.

    One-shot faults (`fail_next_*`, `truncate_after_bytes`) apply to
    exactly the next intercepted response and then clear themselves,
    mirroring how a single real disconnect or transient error behaves.
    """

    host: str
    session_state: str = "session-state-0"
    mailbox_response: list[dict[str, object]] | None = None
    email_get_response: tuple[str, list[object]] | None = None
    truncate_after_bytes: int | None = None
    fail_next_status: int | None = None
    fail_next_retry_after: float | None = None
    latency_seconds: float = 0.0
    disconnect_event_stream_after_events: int | None = None
    forwarded_upstream: int = field(default=0)
    eventsource_call_count: int = field(default=0)

    def session_json(self) -> dict[str, object]:
        """Build a wire-correct JMAP Session object via jmapc's own Model.to_dict()."""
        session = Session(
            username="acceptance@example.test",
            api_url=f"https://{self.host}{_API_PATH}",
            download_url=(
                f"https://{self.host}/download/{{accountId}}/{{blobId}}/{{name}}?type={{type}}"
            ),
            upload_url=f"https://{self.host}/upload/{{accountId}}/",
            event_source_url=(
                f"https://{self.host}{_EVENTSOURCE_PATH}"
                "?types={types}&closeafter={closeafter}&ping={ping}"
            ),
            state=self.session_state,
            primary_accounts=SessionPrimaryAccount(mail=_ACCOUNT_ID),
            capabilities=SessionCapabilities(
                core=SessionCapabilitiesCore(
                    max_size_upload=50_000_000,
                    max_concurrent_upload=4,
                    max_size_request=10_000_000,
                    max_concurrent_requests=4,
                    max_calls_in_request=16,
                    max_objects_in_get=500,
                    max_objects_in_set=500,
                    collation_algorithms={"i;ascii-casemap"},
                )
            ),
        )
        return session.to_dict()

    def method_response(self, name: str, call_id: str) -> list[object] | None:
        """Build one canned methodResponses entry, or None if nothing was configured."""
        if name == "Mailbox/get" and self.mailbox_response is not None:
            mailboxes = [
                jmapc.Mailbox(
                    id=cast_str(m.get("id")),
                    name=cast_str(m.get("name")),
                    role=cast_str(m.get("role")),
                )
                for m in self.mailbox_response
            ]
            response = jmapc_methods.MailboxGetResponse(
                account_id=_ACCOUNT_ID,
                not_found=[],
                state="mailbox-state-0",
                data=mailboxes,
            )
            return [name, response.to_dict(), call_id]
        if name == "Email/get" and self.email_get_response is not None:
            state, data = self.email_get_response
            response = jmapc_methods.EmailGetResponse(
                account_id=_ACCOUNT_ID,
                not_found=[],
                state=state,
                data=list(data),
            )
            return [name, response.to_dict(), call_id]
        return None


def cast_str(value: object) -> str | None:
    """Narrow a loosely-typed canned-response field back to str | None."""
    return value if isinstance(value, str) or value is None else str(value)


class _JmapMockAddon:
    """mitmproxy addon answering every request locally from `_FaultState`."""

    def __init__(self, state: _FaultState) -> None:
        self.state = state

    async def request(self, flow: http.HTTPFlow) -> None:
        state = self.state
        if state.latency_seconds:
            await asyncio.sleep(state.latency_seconds)

        if state.fail_next_status is not None:
            status = state.fail_next_status
            headers = {}
            if state.fail_next_retry_after is not None:
                headers["Retry-After"] = str(int(state.fail_next_retry_after))
            state.fail_next_status = None
            state.fail_next_retry_after = None
            flow.response = http.Response.make(status, b"", headers)
            return

        path = flow.request.path.partition("?")[0]
        if path == _WELL_KNOWN_PATH:
            body = json.dumps(state.session_json()).encode()
        elif path == _API_PATH:
            body = self._api_body(flow)
        elif path == _EVENTSOURCE_PATH:
            state.eventsource_call_count += 1
            if state.eventsource_call_count > 1:
                # sseclient (jmapc's SSE transport) swallows a clean end-of-
                # stream and silently reconnects on its own fixed 3s retry,
                # never surfacing it to JmapPushTrigger (see
                # https://github.com/mitmproxy/mitmproxy/issues/4469's
                # client-side mirror: sseclient.SSEClient.__next__ catches
                # StopIteration/RequestException and retries internally).
                # A real disconnect only reaches spork's own backoff when
                # the *reconnect* attempt itself fails outright, so that's
                # what disconnect_event_stream_after models past the first
                # call.
                flow.response = http.Response.make(503, b"")
                return
            body = self._eventsource_body(state)
            flow.response = self._truncate(
                http.Response.make(
                    200,
                    body,
                    {"Content-Type": "text/event-stream", "Connection": "close"},
                )
            )
            return
        else:
            body = None

        if body is None:
            # No canned response for this request: fail closed, never forward
            # upstream (there is no real upstream for the harness's fake host).
            flow.response = http.Response.make(502, b"no canned response configured")
            return

        flow.response = self._truncate(
            http.Response.make(200, body, {"Content-Type": "application/json"})
        )

    def _api_body(self, flow: http.HTTPFlow) -> bytes | None:
        state = self.state
        try:
            request_json = json.loads(flow.request.content or b"{}")
        except json.JSONDecodeError:
            return None
        method_calls = request_json.get("methodCalls", [])
        method_responses = []
        for call in method_calls:
            name, _args, call_id = call
            response = state.method_response(name, call_id)
            if response is None:
                return None
            method_responses.append(response)
        return json.dumps(
            {"methodResponses": method_responses, "sessionState": state.session_state}
        ).encode()

    def _eventsource_body(self, state: _FaultState) -> bytes:
        n_events = state.disconnect_event_stream_after_events
        if not n_events:
            return b""
        frames = []
        for _ in range(n_events):
            payload = json.dumps({"changed": {_ACCOUNT_ID: {"Email": state.session_state}}})
            frames.append(f"event: state\ndata: {payload}\n\n")
        return "".join(frames).encode()

    def _truncate(self, response: http.Response) -> http.Response:
        state = self.state
        if state.truncate_after_bytes is not None:
            n = state.truncate_after_bytes
            state.truncate_after_bytes = None
            response.content = (response.content or b"")[:n]
        return response


class JmapMitmHarness:
    """Test-facing handle: fault configuration + the real production client_factory."""

    def __init__(self, state: _FaultState, host: str) -> None:
        self._state = state
        self.host = host

    def set_mailbox_response(self, mailboxes: list[dict[str, object]]) -> None:
        """Configure the canned Mailbox/get response for the next connect()."""
        self._state.mailbox_response = mailboxes

    def set_email_get_response(self, *, state: str, data: list[object]) -> None:
        """Configure the canned Email/get baseline response."""
        self._state.email_get_response = (state, data)

    def truncate_next_response(self, *, after_bytes: int) -> None:
        """Cut the very next response body short, regardless of which request it answers."""
        self._state.truncate_after_bytes = after_bytes

    def fail_next_request(self, *, status: int, retry_after: float | None = None) -> None:
        """Answer the very next request with an HTTP failure instead of a body."""
        self._state.fail_next_status = status
        self._state.fail_next_retry_after = retry_after

    def add_latency(self, *, seconds: float) -> None:
        """Delay every subsequent response by this many seconds (sticky, not one-shot)."""
        self._state.latency_seconds = seconds

    def disconnect_event_stream_after(self, *, n_events: int) -> None:
        """Serve exactly n_events SSE frames on the EventSource path, then close."""
        self._state.disconnect_event_stream_after_events = n_events

    def requests_forwarded_upstream(self) -> int:
        """Always 0 today: the addon never dials a real upstream host."""
        return self._state.forwarded_upstream

    def client_factory(self) -> ClientFactory:
        """Return the real, unmodified production client_factory (not a test double)."""
        return _default_client_factory


class _Runner:
    """Owns the background asyncio loop mitmproxy's DumpMaster runs in."""

    def __init__(self, addon: _JmapMockAddon, confdir: str) -> None:
        self._addon = addon
        self._confdir = confdir
        self.master: DumpMaster | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        asyncio.run(self._amain())

    async def _amain(self) -> None:
        opts = options.Options(listen_host="127.0.0.1", listen_port=0)
        self.master = DumpMaster(opts, with_termlog=False, with_dumper=False)
        opts.set(f"confdir={self._confdir}", "connection_strategy=lazy", "http2=false")
        self.master.addons.add(self._addon)
        self._loop = asyncio.get_running_loop()
        run_task = asyncio.ensure_future(self.master.run())
        deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            proxyserver = self.master.addons.get("proxyserver")
            if proxyserver and proxyserver.listen_addrs():
                break
            await asyncio.sleep(0.01)
        self._ready.set()
        await run_task

    def start(self) -> tuple[str, int]:
        self._thread.start()
        if not self._ready.wait(timeout=_STARTUP_TIMEOUT_SECONDS):
            raise RuntimeError("mitmproxy harness did not start in time")
        assert self.master is not None
        proxyserver = self.master.addons.get("proxyserver")
        host, port = proxyserver.listen_addrs()[0][:2]
        return host, port

    def stop(self) -> None:
        assert self.master is not None
        assert self._loop is not None
        self._loop.call_soon_threadsafe(self.master.shutdown)
        self._thread.join(timeout=5)


@contextmanager
def jmap_mitm_harness(*, host: str = "jmap.acceptance.test") -> Iterator[JmapMitmHarness]:
    """Start the harness, route real JMAP traffic through it, and tear it down.

    Sets HTTP_PROXY/HTTPS_PROXY/REQUESTS_CA_BUNDLE for the duration of the
    `with` block (covering both jmapc's requests.Session-based calls and
    the bare `requests.get` sseclient uses for EventSource, since neither
    is otherwise reachable from this harness), and restores the prior
    environment on exit.
    """
    state = _FaultState(host=host)
    addon = _JmapMockAddon(state)
    with tempfile.TemporaryDirectory(prefix="spork-jmap-mitm-") as confdir:
        runner = _Runner(addon, confdir)
        proxy_host, proxy_port = runner.start()
        ca_path = os.path.join(confdir, "mitmproxy-ca-cert.pem")
        deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
        while not os.path.exists(ca_path) and time.monotonic() < deadline:
            time.sleep(0.02)

        previous_env = {
            key: os.environ.get(key) for key in ("HTTP_PROXY", "HTTPS_PROXY", "REQUESTS_CA_BUNDLE")
        }
        os.environ["HTTP_PROXY"] = f"http://{proxy_host}:{proxy_port}"
        os.environ["HTTPS_PROXY"] = f"http://{proxy_host}:{proxy_port}"
        os.environ["REQUESTS_CA_BUNDLE"] = ca_path
        try:
            yield JmapMitmHarness(state, host)
        finally:
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            runner.stop()
