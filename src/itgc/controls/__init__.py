"""Registry of control tests, keyed by RCM control id."""
from .access import test_ac01, test_ac02, test_ac03, test_ac04, test_ac05, test_ac06, test_ac07
from .change import test_cm01, test_cm02, test_cm03, test_cm04
from .operations import test_ops01, test_ops02, test_ops03, test_ops04

REGISTRY = {
    "AC-01": test_ac01, "AC-02": test_ac02, "AC-03": test_ac03, "AC-04": test_ac04,
    "AC-05": test_ac05, "AC-06": test_ac06, "AC-07": test_ac07,
    "CM-01": test_cm01, "CM-02": test_cm02, "CM-03": test_cm03, "CM-04": test_cm04,
    "OPS-01": test_ops01, "OPS-02": test_ops02, "OPS-03": test_ops03, "OPS-04": test_ops04,
}
