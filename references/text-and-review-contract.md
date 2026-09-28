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

For an HTML release, embed the exact reviewed JSON in `<script id="canonical-text" type="application/json">` (attribute order does not matter), or the supported literal `window.D.text` payload. Bind every static text-bearing element to its canonical string using `data-text-key="/path/to/key"`, a JSON Pointer. Numbers and data labels intended for display must also have canonical string representations. The checker resolves pointers and compares text after HTML whitespace normalization, including nested inline formatting. Static non-whitespace text without a binding is an error, including SVG labels, titles, and descriptions.

Bind UI text attributes with `data-text-attr-alt`, `data-text-attr-title`, `data-text-attr-aria-label`, `data-text-attr-placeholder`, or the supported visible input `data-text-attr-value`, each holding a JSON Pointer. Ordinary checkbox state values are not reader-facing copy. See the generated radar HTML for an executable example.

Write a SHA-256 manifest immediately after generation and run `scripts/check_artifact_text.py` with the artifact root, integrity manifest, and forbidden-phrase JSON (use `[]` when no stale phrases apply). The checker excludes its canonical, forbidden-phrase, and manifest input files from stale-phrase scanning. The manifest detects changes after it was written; it is not immutable and does not prove that a reviewer approved the source.

The static checker verifies embedded-source equality, bound static text, supported UI attributes, stale phrases, and post-generation integrity. It does not execute JavaScript, evaluate CSS-generated content, or inspect text later cloned from templates. Script, style, template, and comment contents are outside static text coverage. Inspect rendered runtime states in a browser before claiming complete visible-copy validation. Legacy HTML without bindings needs regeneration; embedding matching JSON alone is insufficient.

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
