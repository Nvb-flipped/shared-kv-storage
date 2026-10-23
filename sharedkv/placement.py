"""Integer SHA-256 placement. Imported by the router, never by clients."""
from bisect import bisect_left
import hashlib

SPACE = 2**256


def hash_integer(text):
    return int.from_bytes(hashlib.sha256(text.encode('utf-8')).digest(), 'big')


class Placement:
    def __init__(self, members, mode='consistent', vnodes=16):
        if mode not in ('modulo', 'consistent') or type(vnodes) is not int or not 1 <= vnodes <= 1024:
            raise ValueError('Use modulo/consistent and an integer V from 1 to 1024.')
        self.members = sorted(members)
        if not self.members or len(set(self.members)) != len(self.members):
            raise ValueError('Membership must be nonempty with distinct IDs.')
        self.mode, self.vnodes = mode, vnodes
        self.tokens = sorted((hash_integer(f'{node}#{i}'), node, i) for node in self.members for i in range(vnodes)) if mode == 'consistent' else []
        self.positions = [token[0] for token in self.tokens]

    @staticmethod
    def token_json(token):
        position, node, i = token
        return {'pos': position, 'node': node, 'label': f'{node.lower()}{i+1}'}

    def locate(self, key):
        value = hash_integer(key)
        if self.mode == 'modulo':
            index = value % len(self.members)
            return {'key': key, 'key_hash': value, 'owner': self.members[index], 'owner_index': index,
                    'nodes_sorted': self.members}
        insertion = bisect_left(self.positions, value)
        index = insertion % len(self.tokens)
        return {'key': key, 'key_hash': value, 'owner': self.tokens[index][1],
                'owner_token': self.token_json(self.tokens[index]), 'owner_token_index': index,
                'wrap_around': insertion == len(self.tokens)}

    def owner(self, key):
        return self.locate(key)['owner']

    def view(self):
        result = {'placement_mode': self.mode, 'vnodes_per_node': self.vnodes, 'hash_space': SPACE}
        if self.mode == 'modulo':
            return dict(result, nodes_sorted=self.members)
        coverage = {node: 0 for node in self.members}
        for i, (position, node, _) in enumerate(self.tokens):
            coverage[node] += (position-self.tokens[i-1][0]) % SPACE if len(self.tokens) > 1 else SPACE
        result.update(total_tokens=len(self.tokens), tokens=[self.token_json(t) for t in self.tokens],
                      node_shares={node: {'tokens': self.vnodes, 'fraction': coverage[node]/SPACE,
                                          'hash_units': coverage[node]} for node in self.members})
        return result
