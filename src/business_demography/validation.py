"""Independent control totals and accounting-identity checks."""

from collections import defaultdict

from .decoder import MEASURES


def reconcile(records):
    """Report partial sums explicitly; unknown components can never pass."""
    checks = []
    details = [r for r in records if r.kind == "detail"]

    def compare(scope, group, year, measure, parts, control):
        missing = sum(r.value is None for r in parts)
        known_sum = sum(r.value for r in parts if r.value is not None)
        complete = bool(parts) and missing == 0
        declared = control.value
        residual = declared - known_sum if complete and declared is not None else None
        checks.append({"scope": scope, "group": group, "year": year, "measure": measure,
                       "known_sum": known_sum, "component_count": len(parts),
                       "unavailable_count": missing, "declared_total": declared,
                       "residual": residual,
                       "status": "incomplete" if residual is None else "pass" if residual == 0 else "fail"})

    for control in records:
        if control.kind == "group_total":
            parts = [r for r in details if r.group == control.group and r.measure == control.measure]
            compare("group", control.group, None, control.measure, parts, control)
        elif control.kind == "annual_total":
            parts = [r for r in details if r.year == control.year and r.measure == control.measure]
            compare("year", "", control.year, control.measure, parts, control)
        elif control.kind == "grand_total":
            for scope, kind in [("detail_to_grand", "detail"), ("annual_to_grand", "annual_total"),
                                ("groups_to_grand", "group_total")]:
                parts = [r for r in records if r.kind == kind and r.measure == control.measure]
                compare(scope, "", None, control.measure, parts, control)
    buckets = defaultdict(dict)
    for r in records:
        buckets[(r.kind, r.group, r.year)][r.measure] = r.value
    for (kind, group, year), values in buckets.items():
        available = all(values[m] is not None for m in MEASURES)
        residual = values["balance"] - (values["openings"] - values["closures"]) if available else None
        checks.append({"scope": "identity_" + kind, "group": group, "year": year,
                       "measure": "balance = openings - closures", "known_sum": None,
                       "component_count": 3, "unavailable_count": sum(v is None for v in values.values()),
                       "declared_total": values["balance"], "residual": residual,
                       "status": "incomplete" if residual is None else "pass" if residual == 0 else "fail"})
        for m in ("openings", "closures"):
            if values[m] is not None and values[m] < 0:
                checks.append({"scope": "nonnegative_" + kind, "group": group, "year": year,
                               "measure": m, "known_sum": None, "component_count": 1,
                               "unavailable_count": 0, "declared_total": values[m],
                               "residual": None, "status": "fail"})
    return checks


def annual_summary(records):
    """BI-ready aggregates derived from detail, never substituted controls."""
    buckets = defaultdict(list)
    for r in records:
        if r.kind == "detail":
            buckets[(r.year, r.measure)].append(r)
    rows = []
    for (year, measure), parts in sorted(buckets.items()):
        missing = sum(r.value is None for r in parts)
        known = sum(r.value for r in parts if r.value is not None)
        rows.append({"year": year, "measure": measure, "value": known if not missing else None,
                     "known_sum": known, "group_count": len(parts), "unavailable_count": missing,
                     "status": "complete" if not missing else "incomplete"})
    return rows
