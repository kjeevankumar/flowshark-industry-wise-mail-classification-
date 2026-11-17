"""Evaluation framework for Industry-Wise Email Classification in FlowShark.

Measures:
- Sender Industry Accuracy
- Target Industry Accuracy
- Per-industry Precision, Recall, and F1-score
- Macro-averaged F1 score
- Confusion Matrix
- Abstention Rate (percentage correctly/overall classified as 'Unknown')
- Cross-industry Disambiguation Accuracy
"""

from collections import defaultdict
import json
import logging
from typing import Any, Dict, List, Tuple

from app.evaluation.industry_benchmark_dataset import INDUSTRY_BENCHMARK_DATASET, IndustryBenchmarkSample
from app.services.industry_rule_classifier import IndustryRuleClassifier
from app.services.industry_taxonomy import INDUSTRY_TAXONOMY, get_all_industries
from app.services.llm_provider import FallbackLLMProvider
from app.services.nlp_preprocessor import NLPPreprocessor

logger = logging.getLogger("flowshark.evaluation")


class IndustryClassifierEvaluator:
    """Evaluates industry classification engine accuracy, precision, recall, and abstention."""

    def __init__(self):
        self.rule_engine = IndustryRuleClassifier()
        self.nlp = NLPPreprocessor()
        self.fallback_hybrid = FallbackLLMProvider()

    def evaluate_benchmark(
        self, samples: List[IndustryBenchmarkSample] = INDUSTRY_BENCHMARK_DATASET
    ) -> Dict[str, Any]:
        """Run comprehensive industry benchmark evaluation."""
        y_sender_true: List[str] = []
        y_sender_pred: List[str] = []
        y_target_true: List[str] = []
        y_target_pred: List[str] = []

        cross_industry_total = 0
        cross_industry_correct = 0

        ambiguous_total = 0
        ambiguous_correct = 0

        review_required_count = 0
        results_breakdown: List[Dict[str, Any]] = []

        for sample in samples:
            # Preprocess and classify through rule engine & hybrid fallback
            preprocessed = self.nlp.preprocess(
                body_plain=sample.body,
                body_html=None,
                subject=sample.subject,
            )

            pred = self.rule_engine.evaluate(
                cleaned_body=sample.body,
                subject=sample.subject,
                sender_email=sample.sender,
            )

            # Record predictions
            s_true = sample.expected_sender_industry
            s_pred = pred.sender_industry or "Unknown"
            t_true = sample.expected_target_industry
            t_pred = pred.target_industry or "Unknown"

            y_sender_true.append(s_true)
            y_sender_pred.append(s_pred)
            y_target_true.append(t_true)
            y_target_pred.append(t_pred)

            if pred.requires_review:
                review_required_count += 1

            # Cross-industry tracking
            if sample.is_cross_industry:
                cross_industry_total += 1
                if s_true == s_pred and t_true == t_pred and s_pred != t_pred:
                    cross_industry_correct += 1

            # Ambiguous/abstention tracking
            if sample.is_ambiguous:
                ambiguous_total += 1
                if s_pred == "Unknown" and t_pred == "Unknown":
                    ambiguous_correct += 1

            results_breakdown.append({
                "id": sample.id,
                "sender_expected": s_true,
                "sender_predicted": s_pred,
                "target_expected": t_true,
                "target_predicted": t_pred,
                "sender_match": s_true == s_pred,
                "target_match": t_true == t_pred,
                "confidence": pred.confidence,
                "requires_review": pred.requires_review,
            })

        # Calculate metrics
        total = len(samples)
        sender_acc = round(sum(1 for yt, yp in zip(y_sender_true, y_sender_pred) if yt == yp) / total, 4)
        target_acc = round(sum(1 for yt, yp in zip(y_target_true, y_target_pred) if yt == yp) / total, 4)

        sender_metrics = self._compute_class_metrics(y_sender_true, y_sender_pred)
        target_metrics = self._compute_class_metrics(y_target_true, y_target_pred)

        cross_acc = round(cross_industry_correct / max(1, cross_industry_total), 4)
        abstention_rate = round(sum(1 for p in y_target_pred if p == "Unknown") / total, 4)
        ambiguous_recall = round(ambiguous_correct / max(1, ambiguous_total), 4)

        confusion_matrix = self._compute_confusion_matrix(y_target_true, y_target_pred)

        return {
            "total_samples": total,
            "sender_industry_accuracy": sender_acc,
            "target_industry_accuracy": target_acc,
            "overall_accuracy": round((sender_acc + target_acc) / 2, 4),
            "macro_f1_sender": sender_metrics["macro_f1"],
            "macro_f1_target": target_metrics["macro_f1"],
            "cross_industry_accuracy": cross_acc,
            "cross_industry_samples": cross_industry_total,
            "abstention_rate": abstention_rate,
            "ambiguous_precision_recall": ambiguous_recall,
            "human_review_rate": round(review_required_count / total, 4),
            "per_industry_target": target_metrics["per_class"],
            "confusion_matrix": confusion_matrix,
            "breakdown": results_breakdown,
        }

    def _compute_class_metrics(self, y_true: List[str], y_pred: List[str]) -> Dict[str, Any]:
        classes = sorted(list(set(y_true + y_pred)))
        per_class: Dict[str, Dict[str, float]] = {}
        f1_scores: List[float] = []

        for cls in classes:
            tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == cls and yp == cls)
            fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != cls and yp == cls)
            fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == cls and yp != cls)

            prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
            rec = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
            f1 = round(2 * prec * rec / (prec + rec), 4) if (prec + rec) > 0 else 0.0

            per_class[cls] = {
                "precision": prec,
                "recall": rec,
                "f1": f1,
                "support": sum(1 for yt in y_true if yt == cls),
            }
            f1_scores.append(f1)

        macro_f1 = round(sum(f1_scores) / max(1, len(f1_scores)), 4)
        return {
            "macro_f1": macro_f1,
            "per_class": per_class,
        }

    def _compute_confusion_matrix(self, y_true: List[str], y_pred: List[str]) -> Dict[str, int]:
        matrix: Dict[str, int] = defaultdict(int)
        for yt, yp in zip(y_true, y_pred):
            key = f"{yt} -> {yp}"
            matrix[key] += 1
        return dict(matrix)


def run_evaluation_cli():
    evaluator = IndustryClassifierEvaluator()
    results = evaluator.evaluate_benchmark()

    print("\n" + "=" * 70)
    print(" FlowShark AI Industry Classification Benchmark Report")
    print("=" * 70)
    print(f"Total Benchmark Samples:      {results['total_samples']}")
    print(f"Sender Industry Accuracy:     {results['sender_industry_accuracy'] * 100:.2f}%")
    print(f"Target Industry Accuracy:     {results['target_industry_accuracy'] * 100:.2f}%")
    print(f"Overall Industry Accuracy:    {results['overall_accuracy'] * 100:.2f}%")
    print(f"Macro F1 Score (Target):      {results['macro_f1_target']:.4f}")
    print(f"Macro F1 Score (Sender):      {results['macro_f1_sender']:.4f}")
    print(f"Cross-Industry Disambig Acc:  {results['cross_industry_accuracy'] * 100:.2f}% ({results['cross_industry_samples']} cases)")
    print(f"Abstention Rate (Unknown):    {results['abstention_rate'] * 100:.2f}%")
    print(f"Ambiguous Case Recall:        {results['ambiguous_precision_recall'] * 100:.2f}%")
    print(f"Human Review Flag Rate:       {results['human_review_rate'] * 100:.2f}%")
    print("-" * 70)
    print("Per-Industry Performance (Target Industry):")
    for ind, metrics in results["per_industry_target"].items():
        print(f"  {ind:<32} P: {metrics['precision']:.2f} | R: {metrics['recall']:.2f} | F1: {metrics['f1']:.2f} | Count: {metrics['support']}")
    print("=" * 70 + "\n")
    return results


if __name__ == "__main__":
    run_evaluation_cli()
