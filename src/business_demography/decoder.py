"""Decode an explicit annual compact-table contract without imputing values."""

from dataclasses import dataclass

MEASURES = ("balance", "closures", "openings")
UNAVAILABLE = {"missing", "unknown", "suppressed"}


@dataclass(frozen=True)
class Value:
    value: int | None
    status: str


@dataclass(frozen=True)
class Record:
    group: str
    year: int | None
    measure: str
    value: int | None
    status: str
    kind: str


class DecodeError(ValueError):
    """The payload is outside the supported, unambiguous contract."""


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def read_value(value):
    if value is None:
        return Value(None, "unknown")
    if integer(value):
        return Value(value, "observed")
    if isinstance(value, dict) and set(value) == {"status"}:
        if value["status"] in UNAVAILABLE:
            return Value(None, value["status"])
    raise DecodeError("Values must be integer counts, null, or an unavailable status")


class Stream:
    """Repeat bits reuse slots in the previous vector of the same schema.

    State persists across groups. Each table role owns a separate Stream;
    a group subtotal must never become the preceding annual detail vector.
    """

    def __init__(self, schema):
        self.default_schema = tuple(schema)
        self.previous = {}

    def decode(self, cell):
        if cell is None:
            # An absent cell invalidates the predecessor; never jump over it.
            self.previous.clear()
            return {m: Value(None, "missing") for m in MEASURES}
        if not isinstance(cell, dict) or set(cell) - {"C", "R", "S"}:
            raise DecodeError("Unsupported cell structure")
        schema = cell.get("S", self.default_schema)
        if not isinstance(schema, (list, tuple)) or len(schema) != 3:
            raise DecodeError("A cell schema must contain three measures")
        if any(not isinstance(m, str) for m in schema) or set(schema) != set(MEASURES):
            raise DecodeError("A cell schema must name each measure exactly once")
        schema = tuple(schema)
        mask = cell.get("R", 0)
        if not integer(mask) or not 0 <= mask <= 7:
            raise DecodeError("Repeat mask must be an integer from 0 to 7")
        values = cell.get("C")
        if not isinstance(values, list) or len(values) != 3 - mask.bit_count():
            raise DecodeError("Value count does not match schema and repeat mask")
        previous = self.previous.get(schema, [Value(None, "unknown")] * 3)
        supplied = iter(values)
        result = []
        for i in range(3):
            if mask & (1 << i):
                old = previous[i]
                result.append(Value(old.value, "repeated" if old.value is not None else old.status))
            else:
                result.append(read_value(next(supplied)))
        self.previous[schema] = result
        return dict(zip(schema, result))


def decode(payload):
    """Return detail and declared controls as separate, typed records."""
    required = {"schema_version", "measure_order", "years", "groups", "annual_totals", "grand_total"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise DecodeError("Payload must contain exactly the documented fields")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise DecodeError("Unsupported schema version")
    schema = payload["measure_order"]
    if not isinstance(schema, list) or len(schema) != 3 or any(not isinstance(m, str) for m in schema) or set(schema) != set(MEASURES):
        raise DecodeError("measure_order must name each measure exactly once")
    years = payload["years"]
    if not isinstance(years, list) or not years or any(not integer(y) for y in years):
        raise DecodeError("Years must be a nonempty integer list")
    if years != sorted(set(years)):
        raise DecodeError("Years must be unique and ascending")
    groups = payload["groups"]
    if not isinstance(groups, list) or not groups:
        raise DecodeError("At least one group is required")
    totals = payload["annual_totals"]
    if not isinstance(totals, list) or len(totals) != len(years):
        raise DecodeError("Annual controls must align with years; use null for missing cells")
    details, subtotals, annual, grand = (Stream(schema) for _ in range(4))
    records = []
    seen = set()

    def append(stream, cell, group, year, kind):
        for measure, item in stream.decode(cell).items():
            records.append(Record(group, year, measure, item.value, item.status, kind))

    for group in groups:
        if not isinstance(group, dict) or set(group) != {"id", "cells", "total"}:
            raise DecodeError("A group requires id, cells, and total")
        label = group["id"]
        if not isinstance(label, str) or not label.strip() or label in seen:
            raise DecodeError("Group identifiers must be nonempty and unique")
        seen.add(label)
        if not isinstance(group["cells"], list) or len(group["cells"]) != len(years):
            raise DecodeError("Group cells must align with years; no padding or truncation")
        for year, cell in zip(years, group["cells"]):
            append(details, cell, label, year, "detail")
        append(subtotals, group["total"], label, None, "group_total")
    for year, cell in zip(years, totals):
        append(annual, cell, "", year, "annual_total")
    append(grand, payload["grand_total"], "", None, "grand_total")
    return records
