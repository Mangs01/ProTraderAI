"""Synthetic-only demonstration: python -B -m ai_research --approve-synthetic."""

import argparse
import json

from .foundation import VERSION, analyze, approve_snapshot


def synthetic_snapshot():
    return {
        "schema_version": VERSION,
        "research_label": "Synthetic demonstration",
        "source_description": "Hand authored aggregate example",
        "evaluation_period": {"start": "2026-01-01", "end": "2026-01-31"},
        "number_of_trades": 20,
        "gross_pnl": 1200.0,
        "charges": 200.0,
        "net_pnl": 1000.0,
        "maximum_drawdown": 350.0,
        "profit_factor": 1.4,
        "evidence_limitations": ["Synthetic example only"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline synthetic research commentary only")
    parser.add_argument("--approve-synthetic", action="store_true",
                        help="Attest approval of the built-in synthetic snapshot")
    args = parser.parse_args(argv)
    if not args.approve_synthetic:
        parser.error("Explicit --approve-synthetic approval is required")
    snapshot = synthetic_snapshot()
    approval = approve_snapshot(snapshot, operator_approved=True)
    print(json.dumps(analyze(snapshot, approval=approval), indent=2))


if __name__ == "__main__":
    main()
