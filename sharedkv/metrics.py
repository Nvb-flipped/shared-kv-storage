"""Descriptive metrics over observed counts and router-returned owners."""
import statistics


def balance(counts):
    values = list(counts.values())
    mean = statistics.mean(values)
    return {'key_counts': counts, 'cv': statistics.pstdev(values)/mean if mean else 0,
            'max_min_ratio': max(values)/min(values) if min(values) else None,
            'shares': {n: c/sum(values) if sum(values) else 0 for n, c in counts.items()}}


def movement(before, after):
    if before.keys() != after.keys():
        raise ValueError('Movement requires the same original keys.')
    nodes = sorted(set(before.values()) | set(after.values()))
    matrix = {a: {b: 0 for b in nodes} for a in nodes}
    for key, old in before.items():
        matrix[old][after[key]] += 1
    count = sum(a != after[k] for k, a in before.items())
    return {'reassigned_key_count': count, 'fraction': count/len(before) if before else 0,
            'retained': len(before)-count, 'matrix_counts': matrix}
