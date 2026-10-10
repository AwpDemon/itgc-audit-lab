"""Shared structures for control tests."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..evidence import Evidence
from ..sampling import band_for_population, sample_size, select

BUILTIN_ACCOUNTS = {"administrator", "guest", "krbtgt"}
AUDITOR_ACCOUNTS = {"svc_audit_ro"}

PASS, FAIL, NA = "Pass", "Exception", "N/A"


@dataclass
class Row:
    """One tested item: its attribute results and supporting detail (one workpaper line)."""
    item: str
    attrs: dict[str, str]                       # attribute code -> Pass / Exception / N/A
    detail: dict[str, object] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def has_exception(self) -> bool:
        return FAIL in self.attrs.values()


@dataclass
class TestResult:
    control_id: str
    approach: str                               # analytic | sample
    population_desc: str
    population_size: int
    sample_size: int
    selection: str                              # how items were chosen
    rows: list[Row]
    notes: list[str] = field(default_factory=list)
    completeness: dict[str, object] = field(default_factory=dict)
    analytic_rows: list[Row] | None = None      # sampled controls: same test over 100% (study only)

    @property
    def exceptions(self) -> list[Row]:
        return [r for r in self.rows if r.has_exception]

    @property
    def conclusion(self) -> str:
        return "Not effective" if self.exceptions else "Effective"

    def exception_items(self) -> list[str]:
        return [r.item for r in self.exceptions]

    def to_dict(self) -> dict:
        def row(r: Row) -> dict:
            return {"item": r.item, "attrs": r.attrs, "detail": r.detail, "notes": r.notes,
                    "exception": r.has_exception}
        return {"control_id": self.control_id, "approach": self.approach,
                "population_desc": self.population_desc, "population_size": self.population_size,
                "sample_size": self.sample_size, "selection": self.selection,
                "conclusion": self.conclusion, "exceptions": len(self.exceptions),
                "exception_items": self.exception_items(), "notes": self.notes,
                "completeness": self.completeness, "rows": [row(r) for r in self.rows],
                "analytic_exception_items": None if self.analytic_rows is None else
                [r.item for r in self.analytic_rows if r.has_exception]}


def verdict(ok: bool | None) -> str:
    if ok is None:
        return NA
    return PASS if ok else FAIL


def account_kind(u: dict) -> str:
    sam = (u.get("sam") or "").lower()
    ou = (u.get("ou") or "").lower()
    if sam in BUILTIN_ACCOUNTS:
        return "builtin"
    if sam in AUDITOR_ACCOUNTS:
        return "auditor"
    if "service accounts" in ou or sam.startswith("svc_"):
        return "service"
    if "admins" in ou or sam.startswith("adm-"):
        return "admin"
    if u.get("employee_id"):
        return "person"
    return "generic"


def run_sampled(control_id: str, ev: Evidence, items: list[str], evaluate: Callable[[str], Row],
                risk: str, frequency: str | None = None, key: str | None = None,
                population_desc: str = "") -> TestResult:
    """Select a random sample, test it, and also run the same test over 100% for the sampling study."""
    n = sample_size(len(items), risk=risk, frequency=frequency)
    seed_key = f"{ev.standard.get('fiscal_year', 'FY2026')}:{key or control_id}"
    chosen = select(items, n, seed_key)
    band = frequency or band_for_population(len(items))
    rows = [evaluate(i) for i in chosen]
    analytic = [evaluate(i) for i in sorted(items)]
    return TestResult(control_id, "sample", population_desc, len(items), len(chosen),
                      f"Random selection (seed '{seed_key}'), {band} band, {risk} risk -> n={n}",
                      rows, analytic_rows=analytic)
