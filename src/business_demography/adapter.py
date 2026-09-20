"""Strict adapter for one flat annual hierarchical-response shape.

    Business meaning is supplied explicitly by the caller. Metadata and
    transport identifiers are discarded. Nested time axes are unsupported.
"""

from .decoder import DecodeError, MEASURES, integer


def normalize_annual_response(document, measure_map):
    """Convert an inspected annual response to the neutral version-1 contract.

    No field-name inference, repeat expansion, value repair, or I/O occurs.
    The caller must verify measure_map against the response descriptor.
    """
    try:
        if len(document["results"]) != 1:
            raise DecodeError("Exactly one result is supported")
        data = document["results"][0]["result"]["data"]
        datasets = data["dsr"]["DS"]
        if len(datasets) != 1:
            raise DecodeError("Exactly one dataset is supported")
        dataset = datasets[0]
        selected = [s for s in data["descriptor"]["Select"] if s and s.get("Kind") == 2]
        codes = [s["Value"] for s in selected]
        if len(codes) != 3 or set(codes) != set(measure_map) or set(measure_map.values()) != set(MEASURES):
            raise DecodeError("An explicit one-to-one mapping for three measures is required")
        aliases = dict(measure_map)
        for entry in selected:
            for alias in entry.get("Subtotal", []):
                if alias is not None:
                    if alias in aliases and aliases[alias] != measure_map[entry["Value"]]:
                        raise DecodeError("Conflicting subtotal alias")
                    aliases[alias] = measure_map[entry["Value"]]
        axes = [h["DM2"] for h in dataset["SH"] if "DM2" in h]
        if len(axes) != 1:
            raise DecodeError("Exactly one annual axis is supported")
        years = [row["G1"] for row in axes[0]]
        if any(not integer(y) for y in years) or any("M" in row for row in axes[0]):
            raise DecodeError("Only a flat integer annual axis is supported")
        group_blocks = [h["DM1"] for h in dataset["PH"] if "DM1" in h]
        total_blocks = [h["DM0"] for h in dataset["PH"] if "DM0" in h]
        if len(group_blocks) != 1 or len(total_blocks) != 1 or len(total_blocks[0]) != 1:
            raise DecodeError("Ambiguous hierarchy")

        def cell(raw):
            if not isinstance(raw, dict) or set(raw) - {"C", "R", "S"}:
                raise DecodeError("Unsupported compact-cell keys")
            out = {k: v for k, v in raw.items() if k in {"C", "R"}}
            if "S" in raw:
                out["S"] = [aliases[s["N"]] for s in raw["S"]]
            return out

        def split(items):
            if len(items) != len(years) + 1:
                raise DecodeError("Expected one cell per year and one separate subtotal")
            return [cell(c) for c in items[:-1]], cell(items[-1])

        groups = []
        for raw_group in group_blocks[0]:
            cells, total = split(raw_group["X"])
            groups.append({"id": raw_group["G0"], "cells": cells, "total": total})
        annual, grand = split(total_blocks[0][0]["X"])
        return {"schema_version": 1, "measure_order": [measure_map[c] for c in codes],
                "years": years, "groups": groups, "annual_totals": annual, "grand_total": grand}
    except (KeyError, TypeError, IndexError) as exc:
        raise DecodeError("Unsupported annual response structure or schema alias") from exc
