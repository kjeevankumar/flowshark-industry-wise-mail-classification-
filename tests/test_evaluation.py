"""Automated tests for evaluation framework and benchmark dataset."""

from app.evaluation.evaluator import ClassifierEvaluator


def test_rule_based_evaluation():
    """Verify that pure rule-based classifier achieves solid baseline on ground truth."""
    evaluator = ClassifierEvaluator()
    metrics = evaluator.evaluate_rule_only()

    assert metrics["sample_count"] == 15
    assert metrics["accuracy"] >= 0.70  # Baseline rule-based accuracy
    assert "new_enquiry" in metrics["per_class"]
    assert "negotiation" in metrics["per_class"]
    assert "confusion_matrix" in metrics


def test_hybrid_evaluation():
    """Verify that hybrid NLP + rule-based classifier handles negations, newsletters, and intents."""
    evaluator = ClassifierEvaluator()
    metrics = evaluator.evaluate_hybrid()

    assert metrics["sample_count"] == 15
    # Hybrid pipeline should score >= 0.85 accuracy on benchmark dataset
    assert metrics["accuracy"] >= 0.85
    assert metrics["macro_f1"] >= 0.80

    # Ensure newsletters / promo were correctly categorized as 'other'
    assert metrics["per_class"]["other"]["recall"] >= 0.80

    # Ensure negations were handled
    assert metrics["confusion_matrix"]["new_enquiry"]["new_enquiry"] == 2
    assert metrics["confusion_matrix"]["negotiation"]["negotiation"] == 3
