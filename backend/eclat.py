from collections import defaultdict
from itertools import combinations


def overlap_pairs(baskets: dict[int, set[int]], min_support_pct: int, min_lift: float):
    """Eclat depth two, where vertical lists hold unique confirmed slips."""
    vertical = defaultdict(set)
    for request, item_ids in baskets.items():
        for item in item_ids:
            vertical[item].add(request)
    n = len(baskets)
    frequent = [item for item, slips in sorted(vertical.items()) if 100 * len(slips) >= n * min_support_pct]
    rows = []
    for a, b in combinations(frequent, 2):
        intersect = len(vertical[a] & vertical[b])
        if 100 * intersect < n * min_support_pct:
            continue
        count_a, count_b = len(vertical[a]), len(vertical[b])
        lift = intersect * n / (count_a * count_b)
        if lift >= min_lift:
            rows.append((a, b, count_a, count_b, intersect, intersect / n,
                         intersect / count_a, intersect / count_b, lift))
    return sorted(rows, key=lambda row: (-row[-1], -row[4], row[:2]))
