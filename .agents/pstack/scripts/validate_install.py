"""Validate the local adaptation; optionally verify discovery without a model turn."""

from __future__ import annotations

import argparse
import hashlib
import json
import queue
import re
import shutil
import subprocess
import threading
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
SKILLS = ROOT / '.agents' / 'skills'


def validate_files() -> dict:
    manifest = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))
    errors = []
    names = manifest['installed_skills']
    for name in names:
        skill = SKILLS / name
        entry = skill / 'SKILL.md'
        if not entry.is_file():
            errors.append(f'Missing skill: {name}')
            continue
        content = entry.read_text(encoding='utf-8')
        match = re.match(r'^---\n(.*?)\n---\n', content, re.S)
        if not match:
            errors.append(f'Invalid frontmatter: {name}')
            continue
        metadata = yaml.safe_load(match.group(1))
        if set(metadata) != {'name', 'description'} or metadata.get('name') != name:
            errors.append(f'Unexpected manifest fields/name: {name}')
        description = metadata.get('description')
        if not isinstance(description, str) or not description.strip() or len(description) > 1024:
            errors.append(f'Invalid description: {name}')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name) > 64:
            errors.append(f'Invalid skill name: {name}')
        ui = yaml.safe_load((skill / 'agents' / 'openai.yaml').read_text(encoding='utf-8'))
        if f'${name}' not in ui['interface']['default_prompt']:
            errors.append(f'Invocation mismatch: {name}')
        if not isinstance(ui['policy']['allow_implicit_invocation'], bool):
            errors.append(f'Invalid invocation policy: {name}')
        source_content = (PACKAGE / 'upstream' / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8')
        source_match = re.match(r'^---\n(.*?)\n---\n', source_content, re.S)
        source_meta = yaml.safe_load(source_match.group(1))
        expected_implicit = not source_meta.get('disable-model-invocation', False)
        if ui['policy']['allow_implicit_invocation'] != expected_implicit:
            errors.append(f'Changed invocation policy: {name}')
    for relative, expected_hash in manifest['source_files'].items():
        source = PACKAGE / relative
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected_hash:
            errors.append(f'Preserved source changed: {relative}')
    if len(manifest['principles']) != 24 or len(manifest['playbooks']) != 23:
        errors.append('Expected 24 principles and 23 playbooks')
    for slug in manifest['playbooks']:
        if not (SKILLS / 'poteto-mode' / 'playbooks' / f'{slug}.md').is_file():
            errors.append(f'Missing translated playbook: {slug}')
        if not (PACKAGE / 'upstream' / 'skills' / 'poteto-mode' / 'playbooks' / f'{slug}.md').is_file():
            errors.append(f'Missing preserved playbook: {slug}')
    for name in manifest['principles']:
        original = (PACKAGE / 'upstream' / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8')
        body = re.sub(r'^---\n.*?\n---\n', '', original, count=1, flags=re.S).strip()
        active = (SKILLS / name / 'SKILL.md').read_text(encoding='utf-8')
        if body not in active:
            errors.append(f'Principle text not preserved: {name}')
    files = [p for name in names for p in (SKILLS / name).rglob('*.md')]
    files.extend(p for p in PACKAGE.glob('*.md'))
    links_checked = 0
    for path in files:
        for raw_target in re.findall(r'(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)', path.read_text(encoding='utf-8')):
            target = raw_target.strip().split(' "', 1)[0].strip('<>')
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            resolved = (path.parent / unquote(parsed.path)).resolve()
            if not resolved.exists():
                errors.append(f'Broken link in {path.relative_to(ROOT)}: {target}')
            links_checked += 1
    models = json.loads((PACKAGE / 'models.json').read_text(encoding='utf-8'))
    if not isinstance(models.get('default'), str) or not isinstance(models.get('roles'), dict):
        errors.append('Invalid routing configuration shape')
    if errors:
        raise ValueError('\n'.join(errors))
    return {'skills': len(names), 'principles': 24, 'playbooks': 23, 'source_files': len(manifest['source_files']), 'local_links_checked': links_checked}


def check_discovery() -> dict:
    binary = shutil.which('codex')
    if not binary:
        raise RuntimeError('codex is not on PATH; discovery not checked')
    version = subprocess.check_output([binary, '--version'], text=True).strip()
    process = subprocess.Popen([binary, 'app-server', '--stdio'], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8')
    messages = queue.Queue()

    def reader():
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except json.JSONDecodeError:
                pass

    threading.Thread(target=reader, daemon=True).start()

    def request(identifier, method, params):
        process.stdin.write(json.dumps({'id': identifier, 'method': method, 'params': params}) + '\n')
        process.stdin.flush()
        while True:
            message = messages.get(timeout=30)
            if message.get('id') == identifier:
                if 'error' in message:
                    raise RuntimeError(message['error'])
                return message['result']

    expected = set(json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8'))['installed_skills'])
    try:
        request(1, 'initialize', {'clientInfo': {'name': 'pstack-local-validation', 'version': '1.0.0'}})
        process.stdin.write(json.dumps({'method': 'initialized'}) + '\n')
        process.stdin.flush()
        cwds = [str(ROOT), str(ROOT / 'dashboard')]
        response = request(2, 'skills/list', {'cwds': cwds, 'forceReload': True})
        reports = []
        for cwd in cwds:
            entries = [e for e in response['data'] if Path(e['cwd']).resolve() == Path(cwd).resolve()]
            if len(entries) != 1:
                raise ValueError(f'Unexpected discovery entry count for {cwd}')
            entry = entries[0]
            own_skills = [s for s in entry['skills'] if Path(s['path']).resolve().is_relative_to(SKILLS.resolve())]
            found = {s['name'] for s in own_skills}
            duplicates = len(own_skills) != len(found)
            if duplicates or found != expected or entry['errors']:
                raise ValueError({'cwd': cwd, 'missing': sorted(expected-found), 'unexpected': sorted(found-expected), 'duplicates': duplicates, 'errors': entry['errors']})
            for skill in own_skills:
                if skill['scope'] != 'repo' or not skill['enabled']:
                    raise ValueError(f'Not enabled as repo skill: {skill["name"]}')
                if not skill.get('interface') or skill['interface']['defaultPrompt'] != f'Use ${skill["name"]} for this project task.':
                    raise ValueError(f'UI metadata not parsed: {skill["name"]}')
            reports.append({'cwd': str(Path(cwd).relative_to(ROOT)) or '.', 'enabled_repo_skills': len(found), 'errors': entry['errors'], 'interface_metadata': 'parsed'})
        return {'version': version, 'discovery': reports, 'model_turns_sent': 0, 'invocation_policy_enforcement': 'not exposed by skills/list; not verified'}
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discovery', action='store_true', help='Initialize a temporary app-server and list skills; no model turn')
    args = parser.parse_args()
    result = {'files': validate_files()}
    if args.discovery:
        result.update(check_discovery())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
