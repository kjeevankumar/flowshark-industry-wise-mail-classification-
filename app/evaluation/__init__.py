"""Evaluation module initialization."""

from app.evaluation.benchmark_dataset import BENCHMARK_DATASET, BenchmarkSample
from app.evaluation.evaluator import ClassifierEvaluator

__all__ = ["BENCHMARK_DATASET", "BenchmarkSample", "ClassifierEvaluator"]

