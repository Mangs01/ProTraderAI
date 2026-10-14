"""Strict in-memory contracts and a deterministic, network-free provider.

Approval is an explicit operator attestation bound to canonical snapshot bytes.
It is not authentication and cannot determine whether an operator mislabels data.
Text is never interpreted as instructions or used to construct executable actions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
import re


class ValidationError(ValueError):
    """Rejected input; messages deliberately omit submitted values."""


VERSION = "AI-R1-SNAPSHOT-1"
REPORT_VERSION = "AI-R1-REPORT-1"
DISCLAIMER = "Research commentary only. No trading advice, approval, or execution authority."
METRICS = ("number_of_trades", "gross_pnl", "charges", "net_pnl",
           "maximum_drawdown", "profit_factor")
FIELDS = {"schema_version", "research_label", "source_description",
          "evaluation_period", "evidence_limitations", *METRICS}
# Deliberately narrow text vocabulary: no URLs, paths, code punctuation or IDs.
TEXT = re.compile(r"[A-Za-z][A-Za-z ,.;'-]{0,239}\Z")
FORBIDDEN = re.compile(
    r"(?i)stage[\s_-]*[bc]\b|sealed|withheld|credential|password|secret|"
    r"token|api[\s_-]*key|account|client[\s_-]*(id|code)|broker|"
    r"buy|sell|order|execute|execution|shell|command|import|eval|exec|"
    r"ignore|override|instruction|system|prompt|personal|email|phone|"
    r"address|candle|\.env|\.\.|https?|file|path"
)


def _require(condition):
    if not condition:
        raise ValidationError("Research boundary validation failed")


def _text(value):
    _require(type(value) is str and TEXT.fullmatch(value) is not None)
    _require(FORBIDDEN.search(value) is None)
    # Long opaque strings may be identifiers or secrets.
    _require(all(len(word) <= 24 for word in re.findall(r"[A-Za-z]+", value)))


def validate_snapshot(value):
    """Return a detached JSON-compatible copy; no discovery, I/O or coercion."""
    _require(type(value) is dict and all(type(k) is str for k in value))
    _require(set(value) <= FIELDS)
    _require({"schema_version", "research_label", "source_description",
              "evaluation_period", "evidence_limitations"} <= set(value))
    _require(value["schema_version"] == VERSION)
    _text(value["research_label"])
    _text(value["source_description"])
    period = value["evaluation_period"]
    _require(type(period) is dict and set(period) == {"start", "end"})
    for item in period.values():
        _require(type(item) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}", item) is not None)
        try:
            date.fromisoformat(item)
        except ValueError:
            raise ValidationError("Invalid evaluation period") from None
    _require(period["start"] <= period["end"])
    limits = value["evidence_limitations"]
    _require(type(limits) is list and len(limits) <= 8)
    for item in limits:
        _text(item)
    for key in METRICS:
        if key not in value:
            continue
        metric = value[key]
        if key == "number_of_trades":
            _require(type(metric) is int and 0 <= metric <= 1_000_000)
        else:
            _require(type(metric) in (int, float) and abs(metric) <= 1_000_000_000_000)
            _require(math.isfinite(metric))
            if key in ("charges", "maximum_drawdown", "profit_factor"):
                _require(metric >= 0)
            if key == "profit_factor":
                _require(metric <= 1_000_000)
    return json.loads(json.dumps(value, allow_nan=False))


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SnapshotApproval:
    snapshot_sha256: str


def approve_snapshot(value, *, operator_approved=False):
    """Call only following an affirmative operator review of this exact snapshot."""
    _require(operator_approved is True)
    return SnapshotApproval(_digest(validate_snapshot(value)))


class ResearchProvider(ABC):
    """In-memory structured commentary contract; no tools or external adapters."""

    @abstractmethod
    def _report(self, snapshot):
        """Called by analyze only after snapshot validation and approval."""


def _statement(category, text):
    return {"category": category, "text": text}


class MockResearchProvider(ResearchProvider):
    """Fixed templates; input prose cannot affect generated report instructions."""

    def _report(self, snapshot):
        metrics = {key: snapshot[key] for key in METRICS if key in snapshot}
        missing = [key for key in METRICS if key not in snapshot]
        limitations = [_statement("FACT_FROM_INPUT", item)
                       for item in snapshot["evidence_limitations"]]
        limitations.append(_statement("AI_INTERPRETATION",
            "Input figures are operator supplied and have not been independently audited."))
        notes = [_statement("AI_INTERPRETATION",
            "Historical summaries cannot establish future performance.")]
        if missing:
            notes.append(_statement("FACT_FROM_INPUT",
                                    "Missing metrics: " + ", ".join(missing)))
        return {
            "schema_version": REPORT_VERSION,
            "snapshot_sha256": _digest(snapshot),
            "verified_input_metrics": {"category": "FACT_FROM_INPUT", "values": metrics},
            "observations": [_statement("AI_INTERPRETATION",
                "Summary metrics alone do not establish robustness or causality.")],
            "potential_limitations": limitations,
            "hypotheses_requiring_independent_testing": [_statement("UNVERIFIED_HYPOTHESIS",
                "Results may vary across independent evaluation periods.")],
            "uncertainty_notes": notes,
            "non_trading_disclaimer": DISCLAIMER,
        }


def validate_report(report, snapshot):
    """Reject added fields, fabricated metrics and altered provenance labels."""
    snapshot = validate_snapshot(snapshot)
    expected = MockResearchProvider()._report(snapshot)
    _require(type(report) is dict and set(report) == set(expected))
    _require(report["schema_version"] == REPORT_VERSION)
    _require(report["snapshot_sha256"] == _digest(snapshot))
    metrics = report["verified_input_metrics"]
    _require(type(metrics) is dict and set(metrics) == {"category", "values"})
    _require(metrics["category"] == "FACT_FROM_INPUT")
    _require(type(metrics["values"]) is dict)
    _require(set(metrics["values"]) == set(expected["verified_input_metrics"]["values"]))
    for key, value in metrics["values"].items():
        _require(type(value) is type(snapshot[key]) and value == snapshot[key])
    # AI-R1 is mock-only. An exact template allowlist also prevents output prose
    # from smuggling commands, secrets, extra conclusions or new authority.
    _require(report == expected)
    return json.loads(json.dumps(report, allow_nan=False))


def analyze(value, *, approval=None, provider=None):
    snapshot = validate_snapshot(value)
    _require(type(approval) is SnapshotApproval and approval.snapshot_sha256 == _digest(snapshot))
    provider = MockResearchProvider() if provider is None else provider
    _require(type(provider) is MockResearchProvider)
    # A separate copy prevents accidental provider mutation of the verified input.
    return validate_report(provider._report(validate_snapshot(snapshot)), snapshot)
