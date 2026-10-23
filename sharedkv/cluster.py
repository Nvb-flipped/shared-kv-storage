"""Own process lifecycle; clients have no dependency on this launcher."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from .transport import ApiError, request
from .config import ClusterConfig, load_config, override

ROOT = Path(__file__).resolve().parents[1]


def child_interpreter():
    """Own the real PID even when Windows uses a venv redirector executable."""
    if sys.platform == 'win32' and sys.prefix != sys.base_prefix:
        # Mirror CPython's venv launcher environment, avoiding its intermediate
        # process while retaining this environment's packages and sys.prefix.
        environment = dict(os.environ)
        environment['__PYVENV_LAUNCHER__'] = sys.executable
        return sys._base_executable, environment
    return sys.executable, None


class Cluster:
    def __init__(self, mode='consistent', vnodes=16, isolated=True, storage_base_port=5001, progress=None,
                 initial_nodes=('A', 'B', 'C'), joining_node='D', router_port=8000, startup_timeout=5):
        config = ClusterConfig(tuple(initial_nodes), joining_node, mode, vnodes, isolated,
                               router_port, storage_base_port, startup_timeout)
        self.mode, self.vnodes, self.isolated = mode, vnodes, isolated
        self.initial_nodes, self.joining_node = config.initial_nodes, config.joining_node
        self.startup_timeout = config.startup_timeout
        nodes = (*self.initial_nodes, self.joining_node)
        self.progress = progress or (lambda message: None)
        self.processes, self.logs = {}, []
        if isolated:
            with ExitStack() as stack:
                sockets = [stack.enter_context(socket.socket()) for _ in range(len(nodes)+1)]
                for sock in sockets:
                    sock.bind(('127.0.0.1', 0))
                ports = [sock.getsockname()[1] for sock in sockets]
        else:
            ports = [router_port, *range(storage_base_port, storage_base_port+len(nodes))]
        self.temp = tempfile.TemporaryDirectory(prefix='sharedkv-')
        self.router_port, self.node_ports = ports[0], dict(zip(nodes, ports[1:]))
        self.url = f'http://127.0.0.1:{ports[0]}'
        self.addresses = {n: f'127.0.0.1:{p}' for n, p in self.node_ports.items()}

    @classmethod
    def from_config(cls, config, **kwargs):
        return cls(config.placement, config.vnodes, config.isolated, config.storage_base_port,
                   initial_nodes=config.initial_nodes, joining_node=config.joining_node,
                   router_port=config.router_port, startup_timeout=config.startup_timeout, **kwargs)

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
                    module = 'sharedkv.router'; port = self.router_port; route = '/admin/health'
                    args = ['--port', str(port), '--nodes', ','.join(f'{n}={self.addresses[n]}' for n in self.initial_nodes),
                            '--placement', self.mode, '--vnodes', str(self.vnodes)]
                else:
                    module = 'sharedkv.storage'; port = self.node_ports[node]; route = '/health'
                    args = ['--id', node, '--port', str(port)]
                self.progress(f'Starting {node} on 127.0.0.1:{port}...')
                log = (Path(self.temp.name)/(node+'.log')).open('w', encoding='utf-8'); self.logs.append(log)
                executable, environment = child_interpreter()
                proc = subprocess.Popen([executable, '-u', '-m', module, *args], cwd=ROOT, env=environment,
                                        stdout=log, stderr=subprocess.STDOUT)
                self.processes[node] = proc
                deadline = time.monotonic()+self.startup_timeout
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        detail = Path(log.name).read_text(errors='replace').strip()[-1200:]
                        raise RuntimeError(f'{node} exited. {detail}')
                    try:
                        health = request(f'http://127.0.0.1:{port}', route,
                                         timeout=min(1, max(.01, deadline-time.monotonic())))
                        if health['pid'] != proc.pid:
                            raise RuntimeError('Readiness response belongs to another process.')
                        self.progress(f'{node} ready (PID {proc.pid}).')
                        break
                    except ApiError:
                        time.sleep(.03)
                else:
                    raise RuntimeError(f'{node} did not answer its health check at 127.0.0.1:{port} '
                                       f'within {self.startup_timeout:g} seconds. '
                                       'Check the configured ports and startup_timeout.')
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
    p = argparse.ArgumentParser(description='Start a local study cluster and a separate HTTP client prompt.')
    p.add_argument('--config', type=Path, help='TOML settings; flags override [cluster].')
    p.add_argument('--placement', choices=['modulo', 'consistent'])
    p.add_argument('--vnodes', type=int)
    p.add_argument('--storage-base-port', type=int)
    p.add_argument('--router-port', type=int)
    p.add_argument('--nodes', help='Initial IDs separated by commas, for example A,B.')
    p.add_argument('--joining-node')
    p.add_argument('--startup-timeout', type=float)
    p.add_argument('--isolated', action=argparse.BooleanOptionalAction, default=None)
    p.add_argument('--dry-run', action='store_true', help='Validate and print settings without starting processes.')
    a = p.parse_args()
    try:
        settings = load_config(a.config).cluster if a.config else ClusterConfig(isolated=False)
        settings = override(settings, dict(placement=a.placement, vnodes=a.vnodes,
            storage_base_port=a.storage_base_port, router_port=a.router_port,
            initial_nodes=tuple(a.nodes.split(',')) if a.nodes is not None else None,
            joining_node=a.joining_node, startup_timeout=a.startup_timeout, isolated=a.isolated))
        if a.dry_run:
            from dataclasses import asdict
            print(json.dumps(asdict(settings), indent=2)); return 0
        print(f'Starting {len(settings.initial_nodes)+1} stores and the router...', flush=True)
        with Cluster.from_config(settings, progress=lambda message: print('[STARTUP] '+message, flush=True)) as cluster:
            print('Router: '+cluster.url, flush=True)
            print('Independent PIDs: '+', '.join(f'{n}={proc.pid}' for n, proc in cluster.processes.items()), flush=True)
            print(f"{'/'.join(cluster.initial_nodes)} are members. {cluster.joining_node} waits for: "
                  f"addnode {cluster.joining_node} {cluster.addresses[cluster.joining_node]}", flush=True)
            return subprocess.call([sys.executable, '-m', 'sharedkv.cli', '--router', cluster.url], cwd=ROOT)
    except (OSError, RuntimeError, ValueError) as exc:
        p.exit(1, f'Cannot start cluster: {exc}\nNo existing application was stopped.\n')
    except KeyboardInterrupt:
        print('\nCluster stopped.'); return 130


if __name__ == '__main__':
    raise SystemExit(main())
