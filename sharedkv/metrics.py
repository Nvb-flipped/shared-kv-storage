"""Descriptive metrics over observed counts and router-returned owners."""
import statistics


def token_coverage(tokens, hash_space):
    """Count clockwise integer intervals from recorded tokens, without hashing keys."""
    if type(hash_space) is not int or hash_space <= 0 or not tokens:
        raise ValueError('Coverage requires tokens and a positive integer hash space.')
    positions = [token['pos'] for token in tokens]
    if any(type(p) is not int or not 0 <= p < hash_space for p in positions) or positions != sorted(positions):
        raise ValueError('Coverage requires sorted integer token positions within the hash space.')
    counts = dict.fromkeys(sorted({token['node'] for token in tokens}), 0)
    if len(set(positions)) == 1:
        # Equal-position ties use the first token, matching clockwise lookup.
        counts[tokens[0]['node']] = hash_space
    else:
        for i, token in enumerate(tokens):
            counts[token['node']] += (token['pos']-tokens[i-1]['pos']) % hash_space
    return counts


def balance(counts):
    values = list(counts.values())
    if not values or any(type(value) is not int or value < 0 for value in values):
        raise ValueError('Balance requires nonempty, nonnegative integer counts.')
    mean = statistics.mean(values)
    total = sum(values)
    return {'key_counts': counts, 'cv': statistics.pstdev(values)/mean if mean else 0,
            'max_min_ratio': max(values)/min(values) if min(values) else None,
            'shares': {n: c/total if total else 0 for n, c in counts.items()}}


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
