"""Keep a short, consistent route between maintained Markdown pages."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ORDER = ['README.md', 'use-cases.md', 'configuration.md', 'reproduction.md', 'architecture.md', 'api.md', 'metrics.md', 'experiment-design.md',
         'results.md', 'demo.md', 'scope.md', 'spec-decisions.md', 'ai-use.md']
LABELS = ['Documentation map', 'Study use cases', 'Configuration', 'Reproduction', 'Architecture', 'API reference', 'Math and metrics', 'Experiment design',
          'Measured results', 'Demonstration', 'Requirements and evidence', 'Spec decisions', 'Attribution']


def update_page(path):
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'\n<!-- navigation:start -->.*?<!-- navigation:end -->\n', '\n', text, flags=re.S)
    text = re.sub(r'\n<!-- reading:start -->.*?<!-- reading:end -->\n?', '\n', text, flags=re.S).rstrip()
    text = re.sub(r'\n<!-- contents:start -->.*?<!-- contents:end -->\n?', '\n', text, flags=re.S)
    name = path.name
    if name not in ORDER: return
    i = ORDER.index(name)
    breadcrumb = '[Project home](../README.md) / [Documentation map](README.md)'
    first, rest = text.split('\n', 1)
    contents = ''
    if name in ('architecture.md', 'api.md', 'metrics.md', 'results.md', 'demo.md'):
        headings = re.findall(r'^## (.+)$', text, re.M)
        def slug(value):
            return re.sub(r'[^\w\s-]', '', value.lower()).replace(' ', '-')
        contents = '\n<!-- contents:start -->\nOn this page: '+ ' · '.join(f'[{h}](#{slug(h)})' for h in headings)+'\n<!-- contents:end -->\n'
    text = first+'\n\n<!-- navigation:start -->\n'+breadcrumb+'\n<!-- navigation:end -->\n'+contents+'\n'+rest.lstrip('\n')
    choices = ['[Documentation map](README.md)']
    if i > 0: choices.append(f'Previous: [{LABELS[i-1]}]({ORDER[i-1]})')
    if i+1 < len(ORDER): choices.append(f'Next: [{LABELS[i+1]}]({ORDER[i+1]})')
    text += '\n\n<!-- reading:start -->\n'+' · '.join(choices)+'\n<!-- reading:end -->\n'
    path.write_text(text, encoding='utf-8', newline='\n')


def main():
    for name in ORDER: update_page(ROOT/'docs'/name)
    print(f'Updated navigation on {len(ORDER)} documentation pages.')


if __name__ == '__main__': main()
