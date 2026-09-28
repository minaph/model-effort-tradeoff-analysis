# Text, visual, and review contract

## Canonical reader-facing text

When the page contains substantial prose, use a reviewed JSON object with stable keys such as:

```json
{
  "title": "...",
  "proposal": "...",
  "introduction": "...",
  "views": {
    "tradeoff": {"description": "...", "takeaway": "..."},
    "mds": {"description": "...", "overview": "...", "takeaway": "..."}
  },
  "method": {"simple": "...", "technical": "...", "missing": "..."},
  "sources": [{"label": "...", "url": "..."}]
}
```

Review this JSON alone before embedding it. The generator must read this file as its only text source; remove hard-coded fallback prose. Compare the embedded object with the reviewed JSON after generation.

For an HTML release, compare the JSON against the embedded `canonical-text` script or `window.D.text`, not against a second hand-written copy. Write a SHA-256 manifest immediately after generation and run `scripts/check_artifact_text.py` with the artifact root, integrity manifest, and forbidden-phrase JSON (use `[]` when the release has no stale-phrase list) so that omitting the stale-copy scan or silently appending visible HTML is not an accidental pass.

Write for nontechnical readers first, then define z/deviation scores, median, population SD, Pareto dominance, MDS, stress, and relative RMSE. Say what each visual makes knowable, with concrete candidate names and numbers. Explain that 3D Pareto means no other candidate is at least as good on all three desirable axes and strictly better on one; the result is a set, not a total ranking.

Do not call cross-benchmark performance spread “stability” unless repeated-run reliability was measured. Use “task-specific strengths and weaknesses” or an equivalent construct-valid label. Keep release history, reviewer disputes, superseded instructions, and implementation notes outside the public HTML.

## Difference and unit language

Represent changes as an ordered transition:

`A → B    Δ = B − A`

For derived scores use “deviation-score points” or the configured display unit; never show an unexplained `Δ`. Raw performance, cost, and latency retain their real units in detail tables. Explain that cost and latency were sign-flipped for desirable-direction scoring.

## Text-only review

Pass only the canonical text object to the language reviewer. Ask for audience clarity, construct-valid terminology, consistent labels, nontechnical-first explanations, and accurate takeaways. Do not pass the HTML or implementation details during this stage. Integrate accepted changes, then run the full artifact review.

## Full artifact review

Give an independent reviewer the current requirements, raw data, method JSON, generated HTML, scripts, and rendered images. Ask for independent recalculation of exclusions, standardization, medians, population SD, Pareto status, fixed edges, MDS fit scope, direction, units, view order, and interaction. The reviewer must not recompute MDS edges from spatial proximity.

For every reviewer suggestion, record accept/reject/defer and the reason. A suggestion that contradicts a later explicit requirement is overreach, even if it would simplify the interface. A reproducible hit-area bug, stale text, calculation mismatch, or unreported coverage gap is actionable.

## Visual and device coverage

Inspect every rendered graph, not only the source. For SVG, verify Japanese font rendering, shapes, labels, hit regions, arrows, and clipping. Test node and edge selection, difference-box selection, MDS arrow state, and 3D rotation/scroll behavior. If Chromium or a mobile device is unavailable, report static-render and VM-smoke coverage separately; never claim full browser/device validation.
