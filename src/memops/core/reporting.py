from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from memops.core.metrics import MetricsReport
from memops.core.retrievals import RetrievalTrace


WORSE_WHEN_HIGHER = {
    "retrieval_latency_ms_avg",
    "memory_tokens_loaded_total",
    "context_pressure_score",
    "memory_churn_rate",
    "duplicate_rate",
    "contradiction_score",
    "stale_recall_rate",
    "empty_retrieval_rate",
}


@dataclass(slots=True)
class ThresholdRule:
    metric: str
    operator: str
    warning: float | int | None = None
    error: float | int | None = None


@dataclass(slots=True)
class ThresholdFinding:
    metric: str
    severity: str
    actual: float | int
    threshold: float | int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RegressionRule:
    metric: str
    operator: str
    warning_delta: float | int | None = None
    error_delta: float | int | None = None


@dataclass(slots=True)
class RegressionFinding:
    metric: str
    severity: str
    actual_delta: float | int
    threshold: float | int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HealthReport:
    session_id: str
    framework: str
    agent_id: str
    status: str
    metrics: dict[str, Any]
    findings: list[ThresholdFinding] = field(default_factory=list)
    problematic_recalls: list[RetrievalTrace] = field(default_factory=list)

    @classmethod
    def from_metrics(
        cls,
        metrics: MetricsReport,
        findings: list[ThresholdFinding],
        problematic_recalls: list[RetrievalTrace] | None = None,
    ) -> "HealthReport":
        status = "healthy"
        if any(item.severity == "error" for item in findings):
            status = "error"
        elif findings:
            status = "warning"
        return cls(
            session_id=metrics.session_id,
            framework=metrics.framework,
            agent_id=metrics.agent_id,
            status=status,
            metrics=dict(metrics.values),
            findings=findings,
            problematic_recalls=list(problematic_recalls or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "framework": self.framework,
            "agent_id": self.agent_id,
            "status": self.status,
            "metrics": self.metrics,
            "findings": [item.to_dict() for item in self.findings],
            "problematic_recalls": [item.to_dict() for item in self.problematic_recalls],
        }


@dataclass(slots=True)
class ComparisonReport:
    baseline_session_id: str
    candidate_session_id: str
    deltas: dict[str, dict[str, Any]]
    regressions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def regression_count(self) -> int:
        return len(self.regressions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_session_id": self.baseline_session_id,
            "candidate_session_id": self.candidate_session_id,
            "deltas": self.deltas,
            "regressions": self.regressions,
            "regression_count": self.regression_count,
        }


@dataclass(slots=True)
class CheckResult:
    kind: str
    status: str
    exit_code: int
    summary: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "exit_code": self.exit_code,
            "summary": self.summary,
            "payload": self.payload,
        }


def default_thresholds() -> list[ThresholdRule]:
    return [
        ThresholdRule(metric="retrieval_latency_ms_avg", operator=">=", warning=500, error=1500),
        ThresholdRule(metric="context_pressure_score", operator=">=", warning=100, error=250),
        ThresholdRule(metric="memory_churn_rate", operator=">=", warning=0.4, error=0.7),
        ThresholdRule(metric="duplicate_rate", operator=">=", warning=0.1, error=0.25),
        ThresholdRule(metric="contradiction_score", operator=">=", warning=0.1, error=0.3),
        ThresholdRule(metric="stale_recall_rate", operator=">=", warning=0.2, error=0.5),
        ThresholdRule(metric="empty_retrieval_rate", operator=">=", warning=0.2, error=0.5),
    ]


def default_regression_thresholds() -> list[RegressionRule]:
    return [
        RegressionRule(metric="retrieval_latency_ms_avg", operator=">=", warning_delta=250, error_delta=1000),
        RegressionRule(metric="context_pressure_score", operator=">=", warning_delta=50, error_delta=100),
        RegressionRule(metric="memory_churn_rate", operator=">=", warning_delta=0.15, error_delta=0.3),
        RegressionRule(metric="duplicate_rate", operator=">=", warning_delta=0.05, error_delta=0.15),
        RegressionRule(metric="contradiction_score", operator=">=", warning_delta=0.05, error_delta=0.15),
        RegressionRule(metric="stale_recall_rate", operator=">=", warning_delta=0.1, error_delta=0.25),
        RegressionRule(metric="empty_retrieval_rate", operator=">=", warning_delta=0.1, error_delta=0.25),
        RegressionRule(metric="memory_tokens_loaded_total", operator=">=", warning_delta=100, error_delta=500),
    ]


def evaluate_thresholds(metrics: MetricsReport, rules: list[ThresholdRule]) -> list[ThresholdFinding]:
    findings: list[ThresholdFinding] = []
    for rule in rules:
        value = metrics.values.get(rule.metric)
        if not isinstance(value, (int, float)):
            continue
        if rule.error is not None and _compare(value, rule.operator, rule.error):
            findings.append(
                ThresholdFinding(
                    metric=rule.metric,
                    severity="error",
                    actual=value,
                    threshold=rule.error,
                    message=f"{rule.metric} is {value} which breaches error threshold {rule.error}",
                )
            )
            continue
        if rule.warning is not None and _compare(value, rule.operator, rule.warning):
            findings.append(
                ThresholdFinding(
                    metric=rule.metric,
                    severity="warning",
                    actual=value,
                    threshold=rule.warning,
                    message=f"{rule.metric} is {value} which breaches warning threshold {rule.warning}",
                )
            )
    return findings


def evaluate_regressions(report: ComparisonReport, rules: list[RegressionRule]) -> list[RegressionFinding]:
    findings: list[RegressionFinding] = []
    for rule in rules:
        payload = report.deltas.get(rule.metric)
        if not payload:
            continue
        delta = payload.get("delta")
        if not isinstance(delta, (int, float)):
            continue
        if rule.error_delta is not None and _compare(delta, rule.operator, rule.error_delta):
            findings.append(
                RegressionFinding(
                    metric=rule.metric,
                    severity="error",
                    actual_delta=delta,
                    threshold=rule.error_delta,
                    message=f"{rule.metric} regression delta is {delta} which breaches error threshold {rule.error_delta}",
                )
            )
            continue
        if rule.warning_delta is not None and _compare(delta, rule.operator, rule.warning_delta):
            findings.append(
                RegressionFinding(
                    metric=rule.metric,
                    severity="warning",
                    actual_delta=delta,
                    threshold=rule.warning_delta,
                    message=f"{rule.metric} regression delta is {delta} which breaches warning threshold {rule.warning_delta}",
                )
            )
    return findings


def compare_reports(baseline: HealthReport, candidate: HealthReport) -> ComparisonReport:
    deltas: dict[str, dict[str, Any]] = {}
    regressions: list[dict[str, Any]] = []
    shared_metrics = set(baseline.metrics) & set(candidate.metrics)

    for metric in sorted(shared_metrics):
        before = baseline.metrics.get(metric)
        after = candidate.metrics.get(metric)
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            continue
        delta = round(after - before, 4)
        changed = delta != 0
        regressed = metric in WORSE_WHEN_HIGHER and delta > 0
        deltas[metric] = {
            "baseline": before,
            "candidate": after,
            "delta": delta,
            "changed": changed,
            "regressed": regressed,
        }
        if regressed:
            regressions.append(
                {
                    "metric": metric,
                    "baseline": before,
                    "candidate": after,
                    "delta": delta,
                }
            )

    return ComparisonReport(
        baseline_session_id=baseline.session_id,
        candidate_session_id=candidate.session_id,
        deltas=deltas,
        regressions=regressions,
    )


def export_report(path: str | Path, payload: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output


def load_threshold_rules(path: str | Path | None = None) -> list[ThresholdRule]:
    if path is None:
        return default_thresholds()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rules_payload = payload["thresholds"] if isinstance(payload, dict) and "thresholds" in payload else payload
    if not isinstance(rules_payload, list):
        raise ValueError("Threshold config must be a list or an object containing 'thresholds'.")
    return [
        ThresholdRule(
            metric=item["metric"],
            operator=item["operator"],
            warning=item.get("warning"),
            error=item.get("error"),
        )
        for item in rules_payload
    ]


def load_regression_rules(path: str | Path | None = None) -> list[RegressionRule]:
    if path is None:
        return default_regression_thresholds()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rules_payload = payload["regressions"] if isinstance(payload, dict) and "regressions" in payload else payload
    if not isinstance(rules_payload, list):
        raise ValueError("Regression config must be a list or an object containing 'regressions'.")
    return [
        RegressionRule(
            metric=item["metric"],
            operator=item["operator"],
            warning_delta=item.get("warning_delta"),
            error_delta=item.get("error_delta"),
        )
        for item in rules_payload
    ]


def check_health_report(report: HealthReport, *, fail_on: str = "error") -> CheckResult:
    if fail_on not in {"error", "warning"}:
        raise ValueError("fail_on must be 'error' or 'warning'.")
    has_error = any(item.severity == "error" for item in report.findings)
    has_warning = any(item.severity == "warning" for item in report.findings)
    failing = has_error or (fail_on == "warning" and has_warning)
    summary = (
        f"health check {report.status}: {len(report.findings)} finding(s) for session {report.session_id}"
    )
    return CheckResult(
        kind="health",
        status="fail" if failing else "pass",
        exit_code=1 if failing else 0,
        summary=summary,
        payload=report.to_dict(),
    )


def check_regression_report(
    report: ComparisonReport,
    findings: list[RegressionFinding],
    *,
    fail_on: str = "error",
) -> CheckResult:
    if fail_on not in {"error", "warning"}:
        raise ValueError("fail_on must be 'error' or 'warning'.")
    has_error = any(item.severity == "error" for item in findings)
    has_warning = any(item.severity == "warning" for item in findings)
    failing = has_error or (fail_on == "warning" and has_warning)
    summary = (
        f"regression check {'fail' if failing else 'pass'}: {len(findings)} finding(s), "
        f"{report.regression_count} regressed metric(s)"
    )
    return CheckResult(
        kind="regression",
        status="fail" if failing else "pass",
        exit_code=1 if failing else 0,
        summary=summary,
        payload={
            **report.to_dict(),
            "regression_findings": [item.to_dict() for item in findings],
        },
    )


def _compare(actual: float | int, operator: str, threshold: float | int) -> bool:
    if operator == ">=":
        return actual >= threshold
    if operator == ">":
        return actual > threshold
    if operator == "<=":
        return actual <= threshold
    if operator == "<":
        return actual < threshold
    raise ValueError(f"Unsupported operator: {operator}")
