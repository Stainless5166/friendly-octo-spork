"""process_message(): idempotency + rule evaluation + action + audit (§9),
built from composable Filter/Selector/Augment modules (§9.4).
"""

from __future__ import annotations

from spork.core.pipeline.core import Augment as Augment
from spork.core.pipeline.core import Filter as Filter
from spork.core.pipeline.core import Payload as Payload
from spork.core.pipeline.core import Pipeline as Pipeline
from spork.core.pipeline.core import Selector as Selector
from spork.core.pipeline.core import UnknownBranchError as UnknownBranchError
from spork.core.pipeline.default import build_default_pipeline as build_default_pipeline
from spork.core.pipeline.default import process_message as process_message
from spork.core.pipeline.meta import MessageMeta as MessageMeta
from spork.core.pipeline.meta import MissingMetaError as MissingMetaError
