# Annual input contract

Version 1 requires exactly these top-level fields: `schema_version`,
`measure_order`, `years`, `groups`, `annual_totals`, and `grand_total`.
The sample JSON is a complete example.

- `measure_order` names `balance`, `closures`, and `openings` exactly once.
- `years` is a nonempty, ascending list of distinct integer years.
- Each group has a unique `id`, a `cells` list aligned with the years, and a
  separate `total`. Group order is significant for compressed state.
- `annual_totals` aligns with the same years. `grand_total` is a separate cell.
- No missing position is padded or silently truncated. Represent an absent
  position explicitly with JSON `null`.

## Compact cells

`C` supplies integer values. `R` is a three-bit repetition mask, defaulting to
zero. A set bit reuses that slot from the preceding vector in the same stream
and schema; unset slots consume `C` values in schema order. Thus with the default
measure order, `R=2` repeats closures and `C` supplies balance and openings.
`R=7` repeats all three measures and requires an empty `C` list.

**A repeat mask does not repeat years and does not mean suppression.**

Four independent state streams exist: annual detail, group totals, annual
controls, and the grand total. Detail state persists across group boundaries.
Inserting a subtotal must not replace the preceding detail vector. Group-total
repetition likewise uses the previous group total, not the last annual detail.

`S`, when supplied, is an explicit per-cell permutation of the three measure
names. Each permutation has its own predecessor. Without `S`, the cell uses
the declared `measure_order`; it does not inherit a preceding override.

`R` must be an integer between 0 and 7. `C` must contain exactly one value for
each unset bit. Invalid shapes, unknown fields, booleans, and fractional counts
are rejected rather than coerced. An unavailable predecessor remains unknown.

## Unavailable values

Within `C`, JSON `null` means unknown. Explicit unavailable values can also be
written as `{"status": "missing"}`, `{"status": "unknown"}`, or
`{"status": "suppressed"}`. These are neutral-contract extensions, not a claim
that a particular upstream response uses those markers.

A whole-cell `null` means a missing observation and invalidates predecessor
state. Repetition cannot reach across that gap. Unknown and suppressed values
stay unavailable when repeated. No arithmetic identity is used to infer them.

## Adapter boundary

`normalize_annual_response(document, measure_map)` accepts one hierarchical
result with a flat integer year axis. The caller must inspect its descriptor
and explicitly map the three measure codes. Subtotal aliases are taken from
that descriptor, not guessed from numeric suffixes. Other transport metadata
is discarded. Unsupported hierarchy or cell fields cause a decoding error.

The adapter is intentionally narrow. It is not a universal compressed-table
decoder. Use the neutral input contract for other formats and preserve unknown
semantics until independently verified.
