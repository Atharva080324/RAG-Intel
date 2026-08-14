from scripts.evaluate_retrieval import page_metrics


def test_page_metrics_reports_first_relevant_rank():
    metrics = page_metrics([7, 9], [3, 9, 7])

    assert metrics == {"hit_at_k": True, "reciprocal_rank": 0.5, "first_relevant_rank": 2}


def test_page_metrics_reports_miss():
    metrics = page_metrics([7], [1, 2, 3])

    assert metrics == {"hit_at_k": False, "reciprocal_rank": 0.0, "first_relevant_rank": None}
