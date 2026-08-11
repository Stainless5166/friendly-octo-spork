"""Fan a message out to one or more classifier targets (docs/DESIGN.md §9.2).

Sits alongside `spork.core.classify`, not inside it: classify defines
what a single backend looks like; this package is purely about
*routing* a message to N of them and, optionally, reducing N results
back to the one decision the rule engine (`spork.core.rules`) acts on.
"""
