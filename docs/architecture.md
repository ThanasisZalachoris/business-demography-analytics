# Engineering architecture and evidence boundaries

## From response investigation to an explicit contract

The underlying research inspected saved analytical responses rather than
assuming that a short value array was an ordinary table row. Notebook probes
examined nested keys, axis lengths, descriptors, and cell shapes. Alternative
decoders treated repetition as row expansion, cursor movement, or abbreviated
measure vectors. Those alternatives are evidence of investigation, not equally
valid implementations.

The remediation selected a saved flat annual response with explicit measure
metadata and independent controls. A per-measure repetition bitmask, separate
detail/subtotal state, and descriptor-defined measure order satisfied its
cardinality and reconciliation constraints. This is a constrained inference
supported by available evidence, not a universal specification of compressed
responses. Historical mismatches from a different snapshot remain unresolved;
see [validation findings](validation.md).

## Capability boundary

| Area | Evidence in the original workflow | Public implementation |
| --- | --- | --- |
| Reverse engineering | Structural probes, descriptor inspection, competing decoders, axis/cardinality checks | Documented contract, explicit mapping, narrow structural adapter |
| Programmatic collection | HTTP GET and JSON parsing experiments with recorded errors | Offline inputs; successful automated acquisition and endpoint discovery are not claimed |
| HTTP resilience | No established retry or rate-limit implementation in the annual workflow reviewed | No HTTP transport, retry policy, or rate-limit handling |
| Document retrieval and PDF/OCR | Not established as part of this annual-count workflow | No document downloader, PDF parser, or OCR component |
| Parsing and transformation | Nested response traversal, dataframe construction, measure mapping, spreadsheet and matrix exports | Typed records and long-form CSV/JSON with explicit value status |
| Validation | Group/year/grand controls, arithmetic identities, residual diagnostics | Independent checks with pass, fail, and incomplete outcomes |
| Recovery | Saved responses allow analysis to be rerun independently of acquisition | Whole-input reruns; no checkpoint/resume or transactional output guarantee |
| Reproducibility | Persisted inputs supported iterative investigation | Fixed output order and line endings, input hash, no timestamps, byte-equality tests |

Unrelated document-processing experiments are not evidence for capabilities of
this annual pipeline. The scope here is deliberately traceable to the inspected
annual implementation and its remediation.

## Module responsibilities and invariants

**Adapter boundary.** `adapter.py` accepts only the supported flat annual shape.
The caller verifies the three-measure mapping against the descriptor. The
adapter discards transport metadata and resolves subtotal aliases from schema
information. Unsupported hierarchies are rejected instead of flattened by
guesswork. The CLI consumes the neutral contract directly.

**Stateful decoding.** `decoder.py` validates the contract before producing
typed records. A repeat bit reuses a measure slot, not a year. Detail, group
totals, annual controls, and the grand total have separate predecessor streams;
schema permutations have separate state as well. Detail state carries across
group boundaries without being overwritten by a subtotal. This separation is
essential: plausible-looking values can otherwise be assigned to the wrong
measure or period while aggregate checks conceal the error.

**Unavailable values.** Missing, unknown, and suppressed values remain explicit.
A missing whole cell invalidates predecessor state. The public status markers
are contract extensions, not claims about the original response encoding. An
incomplete aggregate exposes its known partial sum and coverage while leaving
its value and reconciliation residual unavailable. Controls never repair detail.

**Independent validation.** `validation.py` compares detail-derived aggregates
with declared group, annual, and grand totals and checks the balance identity
independently. Multiple levels help detect errors that cancel at a higher level.
Negative net balance is valid; negative opening or closure counts are flagged.
Internal consistency does not establish source accuracy or dataset completeness.

**Delivery and failure behavior.** `pipeline.py` writes reproducible detail,
summary, declared-control, reconciliation, and validation artifacts. Failed or
incomplete checks still produce diagnostic reports and a nonzero validation exit
code. Malformed input and I/O errors have a separate failure code. This supports
automated quality gates, but it is not resumable or atomic batch processing.

## Reviewable evidence

The repository tests exercise all eight repeat masks, independent state streams,
schema order, unavailable predecessors, malformed inputs, reconciliation
failures, cancellation across years, adapter boundaries, CLI behavior, and
identical output on repeated runs. The synthetic demonstration permits reviewers
to reproduce these behaviors without access to private inputs.

Original notebook inspection supports the historical context above; those
notebooks and source-specific configuration are intentionally not distributed.
The private response validation described in the validation notes is historical
evidence, not a result reproducible from the bundled sample. No production
availability, collection success rate, OCR accuracy, throughput, or business
impact metric is claimed.
