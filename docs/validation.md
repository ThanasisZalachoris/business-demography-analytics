# Validation and research limitations

## Evidence used to select the implementation

Several legacy experiments interpreted repetition as a row count, advanced a
year cursor by the mask, inferred values from short arrays, or hid flagged cells
as if they were suppressed. None was accepted as a canonical implementation.
The canonical input for remediation was a saved flat annual response with an
explicit measure descriptor and independent totals.

The inspected descriptor establishes balance, closures, and openings ordering.
Each group already has one cell per year plus a subtotal. Bitmask decoding with
separate detail and subtotal state preserves that cardinality and satisfies the
saved response's annual controls, group controls, grand total, and arithmetic
identities. This evidence supports the narrow annual adapter, not an assumption
about every possible compressed-response format.

## Historical discrepancy

A legacy workbook records residuals of 2,619 for balance, 3,679 for openings,
and 1,196 for closures. They remain historical findings; no values were changed
to eliminate them. Its declared totals differ from the available annual
response, so the files cannot be treated as the same snapshot.

The exact original response needed to reproduce those historical residuals
was not available. Consequently their precise per-cell attribution remains
unresolved. Incorrect cursor/repetition and short-array logic is present in the
legacy code, but is not presented as a proven complete explanation of those
three historical numbers.

A separate in-memory check of the available annual response covered 24 groups
and 14 years. All 336 group/year combinations decoded, with no unavailable
values, zero residuals against every supplied control, and consistent
balance identities. No real records, labels, transport metadata, or raw
responses are distributed here. This private-data check cannot be independently
reproduced from the public repository; public reproducibility uses invented
fixtures only.

## Public acceptance checks

Tests cover all eight repetition masks, separate state streams, schema order,
missing and suppressed values, first-row repetition without a predecessor,
duplicate identifiers, malformed cells, axis alignment, negative counts,
independent control failures, cancellation of errors across years, adapter
boundaries, CLI exit codes, and byte-identical output on repeated runs.

An aggregate is complete only when all components are known. A partial sum is
reported as `known_sum`; the aggregate value and reconciliation residual remain
blank. Control totals are never substituted for missing detail.

Quarterly and nested responses were identified as different inputs and are
outside this release. No benchmark accuracy, predictive result, or substantive
business conclusion is claimed.
