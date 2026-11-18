"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb
from numbers import Integral

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    outcomes = {
        (POS, POS): "tp",
        ("PASS", POS): "fp",
        (POS, "PASS"): "fn",
        ("PASS", "PASS"): "tn",
    }
    for actual, predicted in zip(human, judge, strict=True):
        outcome = outcomes.get((actual, predicted))
        if outcome is None:
            raise ValueError("labels must be PASS or FAIL")
        counts[outcome] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    counts = confusion(human, judge)
    tp = counts["tp"]
    predicted_failures = tp + counts["fp"]
    actual_failures = tp + counts["fn"]
    precision = tp / predicted_failures if predicted_failures else 0.0
    recall = tp / actual_failures if actual_failures else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    counts = confusion(human, judge)
    n = len(human)
    human_failures = counts["tp"] + counts["fn"]
    judge_failures = counts["tp"] + counts["fp"]
    # Scale both agreement probabilities by n² to detect degeneracy exactly.
    expected = human_failures * judge_failures + (n - human_failures) * (n - judge_failures)
    possible = n * n
    if expected == possible:
        raise ValueError("Cohen's kappa is undefined for these labels")
    observed = n * (counts["tp"] + counts["tn"])
    return (observed - expected) / (possible - expected)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct and clip the failure rate; return NaN when it cannot be estimated."""
    denominator = sensitivity + specificity - 1.0
    if denominator == 0.0:
        return float("nan")
    corrected = (observed_rate + specificity - 1.0) / denominator
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    left = np.asarray(a, dtype=float)
    right = np.asarray(b, dtype=float)
    if left.ndim != 1 or left.shape != right.shape or left.size == 0:
        raise ValueError("bootstrap requires nonempty vectors of paired item scores")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("paired item scores must be finite")

    def mean_delta(pr, baseline, axis=-1):
        return np.mean(pr - baseline, axis=axis)

    delta = float(mean_delta(left, right))
    if left.size == 1 or np.array_equal(left, right):
        return delta, delta, delta

    interval = bootstrap(
        (left, right), mean_delta, paired=True, method="percentile",
        n_resamples=n_resamples, confidence_level=confidence, rng=np.random.default_rng(rng),
    ).confidence_interval
    return delta, float(interval.low), float(interval.high)


def _pass_k_counts(n: int, c: int, k: int) -> tuple[int, int, int]:
    if any(isinstance(value, bool) or not isinstance(value, Integral) for value in (n, c, k)):
        raise ValueError("n, c and k must be integer counts")
    n, c, k = map(int, (n, c, k))
    if not (0 <= c <= n and 1 <= k <= n):
        raise ValueError("expected 0 <= c <= n and 1 <= k <= n")
    return n, c, k


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    n, c, k = _pass_k_counts(n, c, k)
    total = comb(n, k)
    return (total - comb(n - c, k)) / total


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    n, c, k = _pass_k_counts(n, c, k)
    return comb(c, k) / comb(n, k)
