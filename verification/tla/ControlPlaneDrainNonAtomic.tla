---- MODULE ControlPlaneDrainNonAtomic ----
(* A deliberately regressed variant of ControlPlaneDrain.tla, to check
   the model actually distinguishes correct from broken rather than
   passing either way. Splits the capture-and-reset step into two
   separate labels (an interleaving point in between) instead of one --
   modeling what a careless future refactor could introduce (e.g. an
   `await` accidentally landing between reading and resetting `pending`,
   or reverting to `.clear()` mid-iteration): an event IPC enqueues in
   that gap is invisible to `draining` (already captured) AND gets wiped
   by the reset that follows, since it only reached the OLD `pending`
   list a moment before that list is discarded. verification/README.md
   records what TLC actually finds. *)
EXTENDS Sequences, FiniteSets, Naturals

CONSTANT EVENTS

Range(seq) == {seq[i] : i \in 1..Len(seq)}

(* --algorithm ControlPlaneDrainNonAtomic
variables
    pending = <<>>,
    draining = <<>>,
    written_log = <<>>,
    to_enqueue = EVENTS;

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
            draining := pending;
            \* BUG: reset moved to its own label -- an `await`-shaped
            \* gap where IPC can now interleave between capture and
            \* reset, unlike the real code's two-statements-no-await
            \* atomicity.
            Reset:
                pending := <<>>;
            DrainWrite:
                while draining # <<>> do
                    written_log := Append(written_log, Head(draining));
                    draining := Tail(draining);
                end while;
        end while;
end process;

end algorithm; *)
\* BEGIN TRANSLATION (chksum(pcal) = "963b4ef5" /\ chksum(tla) = "914df653")
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
            /\ pc' = [pc EXCEPT !["loop"] = "Reset"]
            /\ UNCHANGED << pending, written_log, to_enqueue >>

Reset == /\ pc["loop"] = "Reset"
         /\ pending' = <<>>
         /\ pc' = [pc EXCEPT !["loop"] = "DrainWrite"]
         /\ UNCHANGED << draining, written_log, to_enqueue >>

DrainWrite == /\ pc["loop"] = "DrainWrite"
              /\ IF draining # <<>>
                    THEN /\ written_log' = Append(written_log, Head(draining))
                         /\ draining' = Tail(draining)
                         /\ pc' = [pc EXCEPT !["loop"] = "DrainWrite"]
                    ELSE /\ pc' = [pc EXCEPT !["loop"] = "LoopStep"]
                         /\ UNCHANGED << draining, written_log >>
              /\ UNCHANGED << pending, to_enqueue >>

Loop == LoopStep \/ Reset \/ DrainWrite

Next == IPC \/ Loop

Spec == /\ Init /\ [][Next]_vars
        /\ WF_vars(IPC)
        /\ WF_vars(Loop)

\* END TRANSLATION 

NoDuplicateWrites ==
    \A i, j \in 1..Len(written_log) : i # j => written_log[i] # written_log[j]

AllEventsEventuallyWritten == <>(Range(written_log) = EVENTS)
====
