# Review adjudication record

Keep this record beside the release checkpoint, not in reader-facing HTML. It preserves why a reviewer request was accepted, rejected, or deferred without turning a historical discussion into a public method claim.

## Review metadata

- artifact/version:
- reviewer/model/effort:
- isolated context:
- request date:
- coverage actually performed:

## Finding ledger

| Finding | Evidence or reproduction | Decision | Reason | Change/checkpoint |
|---|---|---|---|---|
|  |  | accept / reject / defer |  |  |

Use `accept` for a reproducible defect or a requirement-backed change. Use `reject` for a request that contradicts a later explicit requirement, changes the analysis without evidence, or is only a preference. Use `defer` when the evidence is insufficient and add a follow-up eval.

## Exit rule

End a review cycle only when every must-fix finding has either been fixed and rechecked or has a documented, requirement-based rejection. Separate remaining optional polish from release-blocking defects. State static-render, VM, browser, and real-device coverage separately; never upgrade one coverage class into another.
