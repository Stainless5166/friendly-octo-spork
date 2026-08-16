"""Read-only context/knowledgebase retrieval for Tier 2 (docs/DESIGN.md §10.8).

A generic seam, deliberately not tied to any one note-taking tool
(the user explicitly asked for a "read-only context/knowledgebase
interface", not a bespoke Obsidian integration) — `ContextProvider` is
structurally satisfied by whatever backend supplies relevant
background for a message, the same relationship `LLMClient`/`Provider`
have to their own backends.
"""

from __future__ import annotations
