---- MODULE ControlPlaneDrain ----
(* Models spork.daemon.state.DaemonState.pending_control_plane_events and
   spork.daemon.loop._run_message_loop()'s drain step (docs/DESIGN.md
   Section 6.2.2, verification/README.md) -- not the whole daemon, just
   the one queue/drain protocol the code's own comments cite as the
   reason for this design: an IpcServer handler (pause/resume) enqueues
   an event by appending to a shared list; _run_message_loop() drains it
   once per iteration by (1) capturing the current list, (2) resetting
   the shared list to a fresh empty one -- both in one atomic step, no
   `await` between them -- then (3) writing each captured event to
   StateDB one at a time, each write its own `await`, so another
   coroutine (an IPC handler) can run in between any two writes.

   EVENTS is the finite set of distinct events ever enqueued, bounded so
   TLC can exhaust the whole state space. Two processes: IPC (enqueues
   every event in EVENTS, one at a time, in any order) and Loop (models
   _run_message_loop()'s repeated drain-and-write cycle). PlusCal labels
   are the only atomicity boundary -- the same granularity asyncio's
   cooperative scheduling gives real coroutines, where an `await` is the
   only place control can switch to another task. *)
EXTENDS Sequences, FiniteSets, Naturals

CONSTANT EVENTS

Range(seq) == {seq[i] : i \in 1..Len(seq)}

(* --algorithm ControlPlaneDrain
variables
    pending = <<>>,        \* DaemonState.pending_control_plane_events
    draining = <<>>,       \* _run_message_loop()'s local `pending` variable, mid-drain
    written_log = <<>>,    \* the sequence of events actually written to StateDB, in order
    to_enqueue = EVENTS;   \* events IPC still has left to enqueue, any order

fair process IPC = "ipc"
begin
    Enqueue:
        while to_enqueue # {} do
            with e \in to_enqueue do
                pending := Append(pending, e);
                to_enqueue := to_enqueue \ {e};
            end with;
        end while;
end process;

fair process Loop = "loop"
begin
    LoopStep:
        while TRUE do
            \* The atomic capture-and-reset: two plain Python
            \* statements with no `await` between them in the real
            \* code, so IPC cannot interleave between them here either.
            draining := pending;
            pending := <<>>;
            DrainWrite:
                while draining # <<>> do
                    written_log := Append(written_log, Head(draining));
                    draining := Tail(draining);
                end while;
        end while;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "7be584e4" /\ chksum(tla) = "a1beed26")
VARIABLES pending, draining, written_log, to_enqueue, pc

vars == << pending, draining, written_log, to_enqueue, pc >>

ProcSet == {"ipc"} \cup {"loop"}

Init == (* Global variables *)
        /\ pending = <<>>
        /\ draining = <<>>
        /\ written_log = <<>>
        /\ to_enqueue = EVENTS
        /\ pc = [self \in ProcSet |-> CASE self = "ipc" -> "Enqueue"
                                        [] self = "loop" -> "LoopStep"]

Enqueue == /\ pc["ipc"] = "Enqueue"
           /\ IF to_enqueue # {}
                 THEN /\ \E e \in to_enqueue:
                           /\ pending' = Append(pending, e)
                           /\ to_enqueue' = to_enqueue \ {e}
                      /\ pc' = [pc EXCEPT !["ipc"] = "Enqueue"]
                 ELSE /\ pc' = [pc EXCEPT !["ipc"] = "Done"]
                      /\ UNCHANGED << pending, to_enqueue >>
           /\ UNCHANGED << draining, written_log >>

IPC == Enqueue

LoopStep == /\ pc["loop"] = "LoopStep"
            /\ draining' = pending
            /\ pending' = <<>>
            /\ pc' = [pc EXCEPT !["loop"] = "DrainWrite"]
            /\ UNCHANGED << written_log, to_enqueue >>

DrainWrite == /\ pc["loop"] = "DrainWrite"
              /\ IF draining # <<>>
                    THEN /\ written_log' = Append(written_log, Head(draining))
                         /\ draining' = Tail(draining)
                         /\ pc' = [pc EXCEPT !["loop"] = "DrainWrite"]
                    ELSE /\ pc' = [pc EXCEPT !["loop"] = "LoopStep"]
                         /\ UNCHANGED << draining, written_log >>
              /\ UNCHANGED << pending, to_enqueue >>

Loop == LoopStep \/ DrainWrite

Next == IPC \/ Loop

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(IPC)
        /\ WF_vars(Loop)

\* END TRANSLATION 

NoDuplicateWrites ==
    \A i, j \in 1..Len(written_log) : i # j => written_log[i] # written_log[j]

AllEventsEventuallyWritten == <>(Range(written_log) = EVENTS)
====
