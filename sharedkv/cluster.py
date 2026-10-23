"""Own process lifecycle; clients have no dependency on this launcher."""
from contextlib import ExitStack
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from .transport import ApiError, request

ROOT = Path(__file__).resolve().parents[1]


class Cluster:
    def __init__(self, mode='consistent', vnodes=16, isolated=True, storage_base_port=5001, progress=None):
        self.mode, self.vnodes, self.isolated = mode, vnodes, isolated
        if not 1 <= storage_base_port <= 65532:
            raise ValueError('Storage base port must be between 1 and 65532.')
        self.progress = progress or (lambda message: None)
        self.processes, self.logs = {}, []
        if isolated:
            with ExitStack() as stack:
                sockets = [stack.enter_context(socket.socket()) for _ in range(5)]
                for sock in sockets:
                    sock.bind(('127.0.0.1', 0))
                ports = [sock.getsockname()[1] for sock in sockets]
        else:
            ports = [8000, *range(storage_base_port, storage_base_port+4)]
            if len(set(ports)) != 5:
                raise ValueError('Storage ports must not overlap router port 8000.')
        self.temp = tempfile.TemporaryDirectory(prefix='sharedkv-')
        self.router_port, self.node_ports = ports[0], dict(zip('ABCD', ports[1:]))
        self.url = f'http://127.0.0.1:{ports[0]}'
        self.addresses = {n: f'127.0.0.1:{p}' for n, p in self.node_ports.items()}

    def api(self, route, method='GET', data=None):
        return request(self.url, route, method, data, timeout=120)

    def start(self):
        try:
            for port in [self.router_port, *self.node_ports.values()]:
                with socket.socket() as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(('127.0.0.1', port))
            for node in [*self.node_ports, 'router']:
                if node == 'router':
                    script = 'router.py'; port = self.router_port; route = '/admin/health'
                    args = ['--port', str(port), '--nodes', ','.join(f'{n}={self.addresses[n]}' for n in 'ABC'),
                            '--placement', self.mode, '--vnodes', str(self.vnodes)]
                else:
                    script = 'storage_node.py'; port = self.node_ports[node]; route = '/health'
                    args = ['--id', node, '--port', str(port)]
                self.progress(f'Starting {node} on 127.0.0.1:{port}...')
                log = (Path(self.temp.name)/(node+'.log')).open('w'); self.logs.append(log)
                proc = subprocess.Popen([sys.executable, '-u', str(ROOT/script), *args], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                self.processes[node] = proc
                deadline = time.monotonic()+5
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        detail = Path(log.name).read_text(errors='replace').strip()[-1200:]
                        raise RuntimeError(f'{node} exited. {detail}')
                    try:
                        health = request(f'http://127.0.0.1:{port}', route, timeout=1)
                        if health['pid'] != proc.pid:
                            raise RuntimeError('Readiness response belongs to another process.')
                        self.progress(f'{node} ready (PID {proc.pid}).')
                        break
                    except ApiError:
                        time.sleep(.03)
                else:
                    raise RuntimeError(f'{node} did not answer its health check at 127.0.0.1:{port} within 5 seconds. '
                                       'A port can bind successfully yet be unreachable in WSL. '
                                       'Try --storage-base-port 5101 for another local port range.')
            return self
        except BaseException:
            self.stop()
            raise

    def stop(self):
        for proc in reversed(list(self.processes.values())):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
        for log in self.logs:
            log.close()
        self.temp.cleanup()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()


def main():
    import argparse
    p = argparse.ArgumentParser(description='Start four storage processes, a router and a separate client prompt.')
    p.add_argument('--placement', choices=['modulo', 'consistent'], default='consistent')
    p.add_argument('--vnodes', type=int, default=16)
    p.add_argument('--storage-base-port', type=int, default=5001,
                   help='First of four consecutive storage ports (default: 5001).')
    a = p.parse_args()
    try:
        print('Starting four stores and the router...', flush=True)
        with Cluster(a.placement, a.vnodes, isolated=False, storage_base_port=a.storage_base_port,
                     progress=lambda message: print('[STARTUP] '+message, flush=True)) as cluster:
            print('Router: '+cluster.url, flush=True)
            print('Independent PIDs: '+', '.join(f'{n}={proc.pid}' for n, proc in cluster.processes.items()), flush=True)
            print(f"A/B/C are members. D waits for: addnode D {cluster.addresses['D']}", flush=True)
            return subprocess.call([sys.executable, str(ROOT/'client.py'), '--router', cluster.url])
    except (OSError, RuntimeError, ValueError) as exc:
        p.exit(1, f'Cannot start cluster: {exc}\nNo existing application was stopped.\n')
    except KeyboardInterrupt:
        print('\nCluster stopped.'); return 130


if __name__ == '__main__':
    main()
