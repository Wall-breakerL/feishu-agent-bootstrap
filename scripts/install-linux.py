#!/usr/bin/env python3
"""Install pinned Linux x86_64 native tools in an isolated directory.

Python 3.11+. Downloads only public, integrity-pinned official artifacts.
Does not install login state, change shell profiles, or start any service.
"""
import argparse
import base64
import concurrent.futures
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import tarfile
import tempfile
import urllib.request

ARTIFACTS = {
    'cc-connect': {
        'version': '1.5.0', 'format': 'tar',
        'entrypoint': 'cc-connect-v1.5.0-linux-amd64',
        'url': 'https://github.com/chenhg5/cc-connect/releases/download/v1.5.0/cc-connect-v1.5.0-linux-amd64.tar.gz',
        'sha256': '72859035a1ee011b710204fc508de711838f919eb2ae6f104f1ddb3e5cd8ca87',
    },
    'mihomo': {
        'version': '1.19.31', 'format': 'gz',
        'entrypoint': 'mihomo',
        'url': 'https://github.com/MetaCubeX/mihomo/releases/download/v1.19.31/mihomo-linux-amd64-compatible-v1.19.31.gz',
        'sha256': '04cf9f09671704f839ddbee2e93069dc831a4123a75281e725d1d96ab9ac1afc',
    },
    'codex': {
        'version': '0.155.1', 'format': 'tar',
        'entrypoint': 'package/vendor/x86_64-unknown-linux-musl/bin/codex',
        'url': 'https://registry.npmjs.org/@openai/codex/-/codex-0.155.1-linux-x64.tgz',
        'sha512_b64': 'atv3HF0mubqB0J/XkQ2JopqKzXJ+/7aQtTB2MkJ9MrraujMIz8zbCCLylLkN3PzpVGTJzzQFN/wD1oq8oJPJKg==',
    },
    'claude': {
        'version': '2.1.278', 'format': 'tar',
        'entrypoint': 'package/claude',
        'url': 'https://registry.npmjs.org/@anthropic-ai/claude-code-linux-x64/-/claude-code-linux-x64-2.1.278.tgz',
        'sha512_b64': 'q3r+5aLGAet1MGMkCH2xPsuIW9A40ws4zftURxhYwDenheCKvXc7Gr1jBwvEhYG8uQwgY3YsfNwnvIsh1Bjmeg==',
    },
}


def verify(path, spec):
    algorithm = 'sha256' if 'sha256' in spec else 'sha512'
    digest = hashlib.new(algorithm)
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    actual = digest.hexdigest() if algorithm == 'sha256' else base64.b64encode(digest.digest()).decode()
    expected = spec.get('sha256', spec.get('sha512_b64'))
    if actual != expected:
        raise ValueError(f'Integrity mismatch: {path.name}')


def download(item, root):
    name, spec = item
    archive = root / 'downloads' / (name + '-' + spec['version'] + '.gz')
    if not archive.exists():
        partial = archive.with_suffix('.partial')
        try:
            request = urllib.request.Request(spec['url'], headers={'User-Agent': 'feishu-agent-bootstrap'})
            with urllib.request.urlopen(request, timeout=45) as response, partial.open('wb') as out:
                shutil.copyfileobj(response, out)
            verify(partial, spec)
            partial.replace(archive)
        finally:
            partial.unlink(missing_ok=True)
    verify(archive, spec)
    print(f'VERIFIED {name} {spec["version"]}', flush=True)
    return name, archive


def extract(archive, destination, name, spec):
    if spec['format'] == 'gz':
        with gzip.open(archive, 'rb') as src, (destination / name).open('wb') as out:
            shutil.copyfileobj(src, out)
        (destination / name).chmod(0o700)
        return
    # Materialize only regular files/directories, never links or special nodes.
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            target = destination / member.name
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError('Archive path escapes installation directory')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, target.open('wb') as out:
                    shutil.copyfileobj(src, out)
                target.chmod(0o700 if member.mode & 0o111 else 0o600)
            else:
                raise ValueError('Unsupported archive member type')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.home() / '.local/opt/feishu-agent')
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        parser.error('This pin set is for Linux x86_64 only')
    os.umask(0o077)
    root = args.root.expanduser().resolve()
    for folder in ('downloads', 'versions', 'bin'):
        (root / folder).mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        downloaded = dict(executor.map(lambda x: download(x, root), ARTIFACTS.items()))
    receipt = {}
    for name, spec in ARTIFACTS.items():
        destination = root / 'versions' / (name + '-' + spec['version'])
        if not destination.exists():
            with tempfile.TemporaryDirectory(dir=root / 'versions') as tmp:
                staged = Path(tmp) / 'payload'
                staged.mkdir()
                extract(downloaded[name], staged, name, spec)
                staged.rename(destination)
        binary = destination / spec['entrypoint']
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError(f'Pinned executable is missing or not executable: {name}')
        launcher = root / 'bin' / name
        import shlex
        prefix = '#!/usr/bin/env bash\nset -e\n'
        if name == 'claude':
            prefix += 'export DISABLE_AUTOUPDATER=1\n'
        prefix += f'exec {shlex.quote(str(binary))} "$@"\n'
        launcher.write_text(prefix)
        launcher.chmod(0o700)
        if name == 'codex':
            rg = list(destination.rglob('rg'))
            if len(rg) == 1:
                link = root / 'bin/rg'
                if link.is_symlink():
                    link.unlink()
                if not link.exists():
                    link.symlink_to(rg[0])
        receipt[name] = dict(spec, binary=str(binary))
        print(f'INSTALLED {name} {spec["version"]}', flush=True)
    (root / 'installed.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
