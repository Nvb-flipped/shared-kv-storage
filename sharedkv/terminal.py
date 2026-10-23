"""Format router responses. No hashing, token search or membership decisions."""
import shutil

COLORS = {'A': '#56B4E9', 'B': '#E69F00', 'C': '#77C9AC', 'D': '#CC79A7'}
PATTERNS = {'A': '#', 'B': '/', 'C': '=', 'D': '+'}


def safe(value):
    return ''.join(c if c.isprintable() else repr(c)[1:-1] for c in str(value))


def color(text, node=None):
    rgb = COLORS.get(node, '#56B4E9').lstrip('#')
    r, g, b = [int(rgb[i:i+2], 16) for i in (0, 2, 4)]
    return f'\033[38;2;{r};{g};{b}m{safe(text)}\033[0m'


def ring_view(data, width=None):
    lines = []
    if data['placement_mode'] == 'modulo':
        lines += ['Placement: modulo hashing', 'Nodes (sorted): '+', '.join(data['nodes_sorted'])]
        if 'key' in data:
            lines += [f"hash({safe(data['key'])}) = {data['key_hash']}",
                      f"owner index = {data['key_hash']} % {len(data['nodes_sorted'])} = {data['owner_index']}",
                      'Owner: '+color(data['owner'], data['owner'])]
    else:
        tokens = data['tokens']
        columns = max(1, min(60, (width or shutil.get_terminal_size((80, 24)).columns)-4))
        lines += [f"Ring: consistent hashing; {data['total_tokens']} tokens ({data['vnodes_per_node']} per node)",
                  'Clockwise token order from 0% to 100%; one letter per token.',
                  'Columns show token rank, not proportional hash-space distance.']
        marker = data.get('owner_token_index')
        for start in range(0, len(tokens), columns):
            lines.append('  '+''.join(color(t['node'], t['node']) for t in tokens[start:start+columns]))
            if marker is not None and start <= marker < start+columns:
                lines.append('  '+' '*(marker-start)+'^'+(' (wrap-around)' if data['wrap_around'] else ''))
        if 'key' in data:
            token = data['owner_token']
            lines += [f"Key {safe(data['key'])}; integer hash {data['key_hash']}",
                      f"Next token: {token['node']}/{token['label']} @ {100*token['pos']/data['hash_space']:.3f}% -> owner {data['owner']}"]
        lines.append('Hash-space coverage (not stored-key share):')
        for node, share in data['node_shares'].items():
            lines.append(f"  {color(node, node)} {100*share['fraction']:6.2f}% ({share['tokens']} tokens)")
    if 'exists' in data:
        lines.append(f"Stored on {data['owner']}: {'yes' if data['exists'] else 'no'}")
    elif 'key' in data:
        lines.append('Placement only; existence was not checked. Use --check to probe storage.')
    if data.get('pending_owner'):
        lines.append('Migration: pending new owner '+data['pending_owner'])
    if data.get('reload_required'):
        lines.append('Placement changed: flush and reload before Put/Get.')
    return '\n'.join(lines)


def stats_view(data):
    lines = [f"placement={data['placement_mode']}  vnodes={data['vnodes_per_node']}  membership=v{data['membership_version']}  paused={str(data['paused_writes']).lower()}",
             f"migration={data['migration_state']}  reload_required={data['reload_required']}",
             'Node  Status     Keys   Key share   Requests  Request share']
    total = data['key_counts_total']
    requests = sum(n['request_count'] for n in data['nodes'])
    for node in data['nodes']:
        count, traffic, name = node['key_count'], node['request_count'], node['id']
        key_share = f'{100*count/total:.1f}%' if count is not None and total else ('0.0%' if count == 0 else 'unknown')
        request_share = 100*traffic/requests if requests else 0
        bar = PATTERNS.get(name, '#')*round(request_share/100*20)
        lines.append(f"{color(name, name)}     {node['status']:<9} {str(count):>5} {key_share:>10} {traffic:>10} {request_share:>10.1f}%  {color(bar, name)}")
    lines += [f'Total stored items: {total}; client forwards: {requests}.',
              'Requests include Put/Get attempts and misses; inspections and migration are excluded.']
    if not data['counts_complete']:
        lines.append('Some stores are unavailable; the stored-item total is incomplete.')
    if data['top_keys_by_requests']:
        lines.append('Top requested keys:')
        lines += [f"  {safe(row['key'])} -> {row['owner']} ({row['requests']} requests)" for row in data['top_keys_by_requests']]
    return '\n'.join(lines)
