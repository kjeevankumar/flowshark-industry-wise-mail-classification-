"""Evaluation framework to benchmark Rule-based vs. Hybrid NLP classification.

Computes:
- Overall Accuracy
- Per-category Precision, Recall, and F1-score
- Confusion matrix
- Human review flag rate
"""

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from app.evaluation.benchmark_dataset import BENCHMARK_DATASET, BenchmarkSample
from app.services.llm_provider import FallbackLLMProvider
from app.services.nlp_preprocessor import NLPPreprocessor
from app.services.rule_classifier import RuleBasedClassifier


class ClassifierEvaluator:
    """Evaluates classification accuracy and confusion matrix against ground truth."""

    def __init__(self):
        self.rule_engine = RuleBasedClassifier()
        self.nlp = NLPPreprocessor()
        self.fallback_hybrid = FallbackLLMProvider()

    def evaluate_rule_only(self, samples: List[BenchmarkSample] = BENCHMARK_DATASET) -> Dict[str, Any]:
        """Run pure rule-based keyword/pattern evaluation."""
        y_true = []
        y_pred = []
        for s in samples:
            res = self.rule_engine.evaluate(
                cleaned_body=s.body,
                subject=s.subject,
                is_reply=s.subject.lower().startswith("re:"),
            )
            y_true.append(s.expected_intent)
            y_pred.append(res.intent)
        return self._compute_metrics(y_true, y_pred, name="Rule-Based Only")

    def evaluate_hybrid(self, samples: List[BenchmarkSample] = BENCHMARK_DATASET) -> Dict[str, Any]:
        """Run hybrid NLP preprocessing + rule signals + heuristic fallback evaluation."""
        y_true = []
        y_pred = []
        requires_review_count = 0

        for s in samples:
            preprocessed = self.nlp.preprocess(
                body_plain=s.body,
                body_html=None,
                subject=s.subject,
            )
            res = self.fallback_hybrid.classify_email(
                subject=s.subject,
                preprocessed=preprocessed,
            )
            y_true.append(s.expected_intent)
            y_pred.append(res.intent)
            if res.requires_human_review:
                requires_review_count += 1

        results = self._compute_metrics(y_true, y_pred, name="Hybrid (NLP + Rules + Heuristic Fallback)")
        results["requires_human_review_count"] = requires_review_count
        results["human_review_rate"] = round(requires_review_count / len(samples), 3)
        return results

    def _compute_metrics(self, y_true: List[str], y_pred: List[str], name: str) -> Dict[str, Any]:
        total = len(y_true)
        correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
        accuracy = round(correct / total, 4)

        categories = sorted(list(set(y_true + y_pred)))
        per_class: Dict[str, Dict[str, float]] = {}

        # Build confusion matrix
        matrix: Dict[str, Dict[str, int]] = {c1: {c2: 0 for c2 in categories} for c1 in categories}
        for yt, yp in zip(y_true, y_pred):
            matrix[yt][yp] += 1

        f1_scores = []
        for cat in categories:
            tp = matrix[cat][cat]
            fp = sum(matrix[other][cat] for other in categories if other != cat)
            fn = sum(matrix[cat][other] for other in categories if other != cat)

            precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0.0
            recall = round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0.0
            f1 = round((2 * precision * recall) / (precision + recall), 3) if (precision + recall) > 0 else 0.0

            if cat in y_true:
                f1_scores.append(f1)

            per_class[cat] = {
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "support": sum(1 for yt in y_true if yt == cat),
            }

        macro_f1 = round(sum(f1_scores) / len(f1_scores), 3) if f1_scores else 0.0

        return {
            "name": name,
            "sample_count": total,
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "per_class": per_class,
            "confusion_matrix": matrix,
        }

