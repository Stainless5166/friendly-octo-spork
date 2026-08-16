# Automated acceptance specification (not @manual): the same push/
# fallback guarantee m1_jmap.feature's @fallback scenario describes,
# driven by the mitmproxy fault-injection harness (docs/ROADMAP.md M1c,
# tests/support/jmap_mitm.py) instead of a live Fastmail account. Runs
# on every `uv run behave` with no live credentials, no
# SPORK_ACCEPTANCE_LIVE opt-in, and no real network — the harness
# answers every request locally.
#
# This complements, not replaces, m1_jmap.feature's @fallback and
# @network-recovery scenarios: those remain the real evidence for M1's
# exit criterion (an actual forced network drop against a real
# account). This feature proves the same Source-composition behavior
# (JmapProvider.build_checkpointed_source: push primary, poll
# secondary, shared cursor) is automatable and regression-tested on
# every run, not just verifiable by hand once.

@m1 @fault-injection
Feature: JMAP push/fallback under simulated transport failure
  Spork's JmapProvider composes a push-triggered primary source with a
  polling secondary sharing one candidate cursor. When push fails, mail
  is not lost: the poll fallback serves the cycle, and push is retried
  automatically on the next cycle with no explicit "switch back" step.

  Background:
    Given the JMAP fault-injection harness is running
    And sporkd uses JmapProvider routed through the harness

  Scenario: Push disconnect falls back to polling, and push recovers on the next cycle
    Given the EventSource connection will fail on the next cycle
    When the first source cycle runs
    Then the batch is served by polling after push fails
    And the shared cursor advances from the poll response
    When the EventSource connection becomes available again
    And the next source cycle runs
    Then the batch is served by push with no wasted fallback
    And the shared cursor advances again
