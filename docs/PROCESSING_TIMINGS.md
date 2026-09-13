# Processing timing diagnostics

`active_fire.performance.last_completed_processing` retains the latest successful
non-skipped processing run. It contains its completion time, input and new-source
incident counts, and eleven bounded stage measurements. A skipped poll does not
erase this record; a restart resets it. A failed or still-running cycle is not
represented by this completed record.

Each stage reports elapsed `wall_ms` and `thread_cpu_ms`. The latter measures the
coordinator thread, not executor workers. Across an `await`, it can include other
Home Assistant tasks running on that thread. Neither measurement is by itself a
continuous event-loop stall measurement. Place lookup and state saving include
asynchronous waiting. High wall time with low thread CPU points toward waiting;
high CPU in a synchronous stage identifies computation to investigate.

Compare the completion time and duration with observed disconnections. The JSON
does not contain per-observation data, coordinates, credentials, or new logs.
This is instrumentation only: no clustering, notification, scheduling, retention,
or provider polling policy is changed.

## Incident-family optimization

The subsequent family fix indexes fixed group anchors in Earth-centred spatial
cells. This only shortlists candidates: the original temporal, source, complete-
link diameter and stable-ID rules still decide membership in the original order.
It avoids testing obviously distant families and handles poles and the date line.

Both consolidation calls run in the HA executor on deep copies. Workers cannot
mutate live coordinator state, including after cancellation. Their CPU usage is
not included in the coordinator's `thread_cpu_ms`; compare stage wall time and
actual frontend responsiveness after deployment, not thread CPU alone. Dense
groups can still require pairwise work. Synthetic timing is not a prediction for
the Raspberry Pi or the user's data.
