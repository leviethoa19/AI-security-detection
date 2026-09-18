# M5 evaluation architecture

The evaluator reuses `ReplayEngine`; it does not implement a second risk engine. A
versioned manifest points to scripted observation scenarios, assigns leakage-safe split
groups, records subgroups, and defines event ground-truth windows.

```text
evaluation manifest + scenario observations
                    |
          frame baseline / temporal config
                    |
                ReplayEngine
                    |
        greedy event-window matching
                    |
       Pandas tables + sklearn metrics
                    |
 JSON / CSV / Markdown / PNG report bundle
```

An event matches when type and track agree and its timestamp falls between the annotated
onset and window end. Predictions are consumed once. Extra predictions are false
positives; unmatched annotations are false negatives. A second prediction inside an
already matched window is categorized as a duplicate alert.

`splitGroup` is the leakage boundary. The loader rejects a group assigned to more than
one split, duplicate scenario identifiers, inverted event windows, and annotations beyond
the declared scenario duration.

The frame baseline changes only `highRiskMinPositiveFrames` from three to one. Every other
component remains shared, isolating the effect of temporal persistence. Generated reports
belong under `work/` and are excluded from Git; the measured summary is committed in
`docs/experiments`.
