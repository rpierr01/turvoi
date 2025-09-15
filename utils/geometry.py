from typing import List, Tuple, Optional

# Boîte : (x1, y1, x2, y2)
def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    if inter == 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0

def greedy_match_iou(set_a: List[Tuple[float, float, float, float]],
                     set_b: List[Tuple[float, float, float, float]]) -> Optional[float]:
    """Appariement glouton 1-à-1 et moyenne des IoU des paires appariées."""
    if not set_a or not set_b:
        return None
    used_b = set()
    total, matches = 0.0, 0
    for a in set_a:
        best, best_j = 0.0, None
        for j, b in enumerate(set_b):
            if j in used_b:
                continue
            v = iou(a, b)
            if v > best:
                best, best_j = v, j
        if best_j is not None:
            used_b.add(best_j)
            total += best
            matches += 1
    return (total / matches) if matches else 0.0
