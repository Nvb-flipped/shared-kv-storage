"""Strict, dependency-free TOML settings shared by launchers and study tools."""
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
import math
import tomllib


class ConfigError(ValueError):
    """A configuration is invalid; no processes should be started."""


def integer(name, value, minimum=1, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        limit = f'{minimum}..{maximum}' if maximum is not None else f'>= {minimum}'
        raise ConfigError(f'{name} must be an integer {limit}.')


@dataclass(frozen=True)
class ClusterConfig:
    initial_nodes: tuple[str, ...] = ('A', 'B', 'C')
    joining_node: str = 'D'
    placement: str = 'consistent'
    vnodes: int = 16
    isolated: bool = True
    router_port: int = 8000
    storage_base_port: int = 5001
    startup_timeout: float = 5.0

    def __post_init__(self):
        if not isinstance(self.initial_nodes, (tuple, list)):
            raise ConfigError('initial_nodes must be an array of node IDs.')
        nodes = (*self.initial_nodes, self.joining_node)
        if not self.initial_nodes or any(not isinstance(n, str) or len(n) != 1 or not 'A' <= n <= 'Z' for n in nodes):
            raise ConfigError('Use nonempty initial_nodes and single uppercase node IDs A..Z.')
        if len(set(nodes)) != len(nodes) or 'router' in nodes:
            raise ConfigError('Initial and joining node IDs must be distinct.')
        if self.placement not in ('modulo', 'consistent'):
            raise ConfigError('placement must be modulo or consistent.')
        integer('vnodes', self.vnodes, 1, 1024)
        integer('router_port', self.router_port, 1, 65535)
        integer('storage_base_port', self.storage_base_port, 1, 65536-len(nodes))
        if type(self.isolated) is not bool:
            raise ConfigError('isolated must be true or false.')
        if not self.isolated and self.router_port in range(self.storage_base_port, self.storage_base_port+len(nodes)):
            raise ConfigError('Storage ports must not overlap the router port.')
        try:
            valid_timeout = type(self.startup_timeout) in (int, float) and math.isfinite(self.startup_timeout) and self.startup_timeout > 0
        except OverflowError:
            valid_timeout = False
        if not valid_timeout:
            raise ConfigError('startup_timeout must be a finite positive number of seconds.')


@dataclass(frozen=True)
class ExperimentConfig:
    keys: int = 1000
    uniform_reads: int = 1000
    additional_hot_reads: int = 500
    seed: int = 3010
    trials: int = 3
    modes: tuple[str, ...] = ('modulo', 'consistent')
    vnodes: tuple[int, ...] = (1, 2, 4, 8, 10, 16, 32, 64, 128)
    output: str = '../results/runs/study'

    def __post_init__(self):
        for name in ('keys', 'uniform_reads', 'trials'):
            integer(name, getattr(self, name))
        integer('additional_hot_reads', self.additional_hot_reads, 0)
        integer('seed', self.seed, 0)
        if not isinstance(self.modes, (tuple, list)) or not self.modes or any(not isinstance(m, str) or m not in ('modulo', 'consistent') for m in self.modes) or len(set(self.modes)) != len(self.modes):
            raise ConfigError('modes must be a nonempty array of distinct modulo/consistent values.')
        if not isinstance(self.vnodes, (tuple, list)) or not self.vnodes:
            raise ConfigError('vnodes must be a nonempty array of distinct integers.')
        for value in self.vnodes:
            integer('experiment.vnodes', value, 1, 1024)
        if len(set(self.vnodes)) != len(self.vnodes):
            raise ConfigError('vnodes must be a nonempty array of distinct integers.')
        if not isinstance(self.output, str) or not self.output.strip():
            raise ConfigError('output must be a nonempty path string.')

    def cases(self):
        return [(mode, v) for mode in self.modes for v in ((1,) if mode == 'modulo' else self.vnodes)]


@dataclass(frozen=True)
class StudyConfig:
    cluster: ClusterConfig
    experiment: ExperimentConfig

    def snapshot(self):
        return asdict(self)


def section(cls, data, name):
    if not isinstance(data, dict):
        raise ConfigError(f'[{name}] must be a TOML table.')
    unknown = set(data) - {f.name for f in fields(cls)}
    if unknown:
        raise ConfigError(f'Unknown [{name}] setting(s): {", ".join(sorted(unknown))}.')
    converted = dict(data)
    for key in ('initial_nodes', 'modes', 'vnodes'):
        if key in converted and (key != 'vnodes' or cls is ExperimentConfig):
            if not isinstance(converted[key], list):
                raise ConfigError(f'{name}.{key} must be an array.')
            converted[key] = tuple(converted[key])
    try:
        return cls(**converted)
    except TypeError as exc:
        raise ConfigError(f'Invalid [{name}] settings: {exc}') from exc


def load_config(path):
    """Paths in TOML are relative to its directory; CLI paths are relative to CWD."""
    path = Path(path)
    try:
        with path.open('rb') as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f'Cannot load {path.name}: {exc}') from exc
    if set(data) - {'cluster', 'experiment'}:
        raise ConfigError('Only [cluster] and [experiment] tables are supported.')
    cluster = section(ClusterConfig, data.get('cluster', {}), 'cluster')
    experiment = section(ExperimentConfig, data.get('experiment', {}), 'experiment')
    return StudyConfig(cluster, experiment)


def override(config, values):
    return replace(config, **{k: v for k, v in values.items() if v is not None})
