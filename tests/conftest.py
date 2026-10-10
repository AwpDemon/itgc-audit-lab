from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "audit" / "evidence" / "fy26-baseline"
REMEDIATION = ROOT / "audit" / "evidence" / "fy26-remediation"


@pytest.fixture(scope="session")
def baseline():
    from itgc.evidence import Evidence
    return Evidence.load(BASELINE)


@pytest.fixture(scope="session")
def rcm():
    from itgc.engine import load_rcm
    return load_rcm()


@pytest.fixture(scope="session")
def baseline_results(baseline, rcm):
    from itgc.engine import run_tests
    return run_tests(baseline, rcm)
