"""Shared contract tests run against this repository, once per registered profile."""

from meds_algorithm.conformance.suite import AlgorithmConformanceTests


class TestConformance(AlgorithmConformanceTests):
    """Keep shared checks inherited; implement adapters in e2e.py."""
