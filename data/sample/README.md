# Invented sample data

`annual_counts.json` was constructed for offline demonstration and regression
testing. Groups A, B, and C are fictional categories. No real-world values,
identifiers, documents, credentials, or transport metadata are included.

The three-year detail totals are balance 16, closures 16, and openings 32.
The controls are explicitly supplied in the fixture rather than calculated
by the pipeline from the same detail that they validate.

Unavailable and suppressed values are exercised by the test suite, including
their effect on aggregates and validation status.
