"""Pure HTTP client: commands and readable output, without placement logic."""
import argparse
import shlex
import sys
from urllib.parse import urlencode
from sharedkv.terminal import color, ring_view, safe, stats_view
from sharedkv.transport import ApiError, request

HELP = '''put KEY VALUE               store or overwrite text
get KEY                     retrieve text
owner KEY                   ask the router for the current owner
ring [KEY] [--check]         show token order; optionally check existence
stats                       key counts, shares and client request counts
keys                        every stored key, routed owner and physical hosts
addnode ID HOST:PORT         register an empty storage process and migrate
placement modulo|consistent rebuild placement; populated data needs flush/reload
vnodes V                    set tokens per node; same flush/reload rule
membership                  registered nodes and migration state
reset-counters              clear client request counters
flush                       explicitly delete all registered stores' data
recover                     finish a failed migration's cleanup or rollback
quit                        leave this client'''


def command(base, words):
    if not words:
        return 0
    name, args = words[0], words[1:]
    api = lambda route, method='GET', data=None: request(base, route, method, data, timeout=120)
    if name in ('help', '?') and not args:
        print(HELP); return 0
    if name == 'put' and len(args) >= 2:
        key, value = args[0], ' '.join(args[1:])
        result = api('/put', 'POST', {'key': key, 'value': value})
        print(color('[STORED]')+' '+safe(key)+f"\n  {'Value:':<8}{safe(value)}\n  {'Owner:':<8}"+color(result['owner'], result['owner']))
    elif name == 'get' and len(args) == 1:
        result = api('/get?'+urlencode({'key': args[0]}))
        print(color('[FOUND]')+' '+safe(result['key'])+f"\n  {'Value:':<8}{safe(result['value'])}\n  {'Owner:':<8}"+color(result['owner'], result['owner']))
    elif name == 'owner' and len(args) == 1:
        result = api('/owner?'+urlencode({'key': args[0]}))
        print(f"{safe(args[0])}: owner "+color(result['owner'], result['owner']))
    elif name == 'ring' and len([a for a in args if a != '--check']) <= 1:
        keys = [a for a in args if a != '--check']
        if args.count('--check') > 1 or any(a.startswith('--') and a != '--check' for a in args):
            raise ValueError('Use ring [KEY] [--check].')
        if '--check' in args and not keys:
            raise ValueError('--check requires a key.')
        query = {'key': keys[0]} if keys else {}
        if '--check' in args: query['check'] = '1'
        print(ring_view(api('/ring?'+urlencode(query))))
    elif name == 'stats' and not args:
        print(stats_view(api('/stats')))
    elif name == 'keys' and not args:
        result = api('/keys')
        if not result['keys']: print('No stored keys.')
        for row in result['keys']:
            print(f"{safe(row['key'])}: owner={row['owner']} stored={','.join(row['stored_on'])}")
    elif name == 'addnode' and len(args) == 2:
        result = api('/admin/addnode', 'POST', {'id': args[0], 'addr': args[1]})
        print(color('[JOINED]')+f" {safe(args[0])}: membership {result['old_membership_version']} -> {result['new_membership_version']}")
        print(f"  Reassigned {result['reassigned_key_count']}; migrated {result['migrated']}; verified {result['verified']}. Writes resumed.")
        print(f"  Join time {result['seconds']:.3f} s; estimated serialized item size {result['estimated_item_bytes']:,} bytes (not wire traffic).")
    elif name in ('placement', 'vnodes') and len(args) == 1:
        body = {'mode': args[0]} if name == 'placement' else {'v': int(args[0])}
        result = api('/admin/'+name, 'POST', body)
        print(f"Placement {result['mode']}; V={result['vnodes_per_node']}; revision {result['placement_revision']}.")
        if result['reload_required']: print('Existing data was not moved. Run flush, then reload before Put/Get.')
    elif name == 'membership' and not args:
        result = api('/admin/membership')
        print(f"Membership v{result['version']}; migration={result['migration']['state']}; paused={result['paused_writes']}")
        for node in result['nodes']: print(f"  {color(node['id'], node['id'])} {node['addr']} {node['status']}")
    elif name in ('reset-counters', 'recover', 'flush') and not args:
        route = {'reset-counters': 'reset_counters', 'recover': 'recover', 'flush': 'flush'}[name]
        result = api('/admin/'+route, 'POST', {})
        print(color('[OK]')+' '+name+(f"; deleted {result['deleted']} items" if 'deleted' in result else ''))
    else:
        raise ValueError('Invalid command or arguments. Type help for the command list.')
    return 0


def execute(base, words):
    try:
        return command(base, words)
    except ApiError as exc:
        if exc.status == 404 and exc.code == 'not_found':
            print(color('[NOT FOUND]')+' '+safe(exc.details.get('key', ''))+f"\n  {'Owner:':<8}{exc.details.get('owner', 'unknown')}", file=sys.stderr)
            return 3
        print(color('[REJECTED]')+f' {exc.code}: {safe(exc)} (HTTP {exc.status})', file=sys.stderr)
        return 5 if exc.status >= 500 else 4
    except (ValueError, TypeError) as exc:
        print('Usage: '+safe(exc), file=sys.stderr); return 2
    except KeyboardInterrupt:
        print('\nCancelled; a timed-out mutation may already have taken effect.', file=sys.stderr); return 130


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--router', default='http://127.0.0.1:8000')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command: return execute(args.router, args.command)
    print('Text key-value prompt. Type help; quit to leave.')
    while True:
        try:
            words = shlex.split(input(color('>> User: ')))
            if words in (['quit'], ['exit']): return 0
            execute(args.router, words)
        except EOFError:
            print(); return 0
        except KeyboardInterrupt:
            print('\nCommand cancelled.'); continue
        except ValueError as exc:
            print('Usage: '+safe(exc), file=sys.stderr)


if __name__ == '__main__':
    raise SystemExit(main())
