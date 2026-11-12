"""Promote frozen RC bytes. This standalone file is replicated in each demo repo."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import quote


def gh(*args, binary=False):
    return subprocess.check_output(['gh', *args], text=not binary)


def api(path):
    return json.loads(gh('api', path))


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode('ascii')


def basename(name):
    if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name)
            or name.endswith('.') or '..' in name or name.split('.')[0].upper() in
            {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}):
        raise ValueError('Unsafe asset basename')
    return name


def unique_json(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key')
        value[key] = item
    return value


def promote(context, tag, repository, read_api=api, command=gh):
    """Validate all source bytes before creating or modifying a final draft."""
    if context['tag'] != tag or context['repository'] != repository:
        raise ValueError('Final context tag/repository mismatch')
    source = context['sourceRc']
    if not re.fullmatch(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-rc\.(0|[1-9][0-9]*)', source):
        raise ValueError('Expected exact RC source')
    if tag != source.split('-rc.')[0] or not re.fullmatch('[0-9a-f]{64}', context['catalogSha256']):
        raise ValueError('Invalid final/catalog binding')
    prefix = f'repos/{repository}'
    ref = read_api(prefix + '/git/ref/tags/' + quote(source, safe=''))
    if ref['object']['sha'] != context['sourceSha'] or ref['object']['type'] != 'commit':
        raise ValueError('Source RC moved')
    release = read_api(prefix + '/releases/tags/' + quote(source, safe=''))
    if release['tag_name'] != source or release['draft'] or not release['prerelease']:
        raise ValueError('Source is not a published RC')
    payloads = context['payloads']
    if not payloads:
        raise ValueError('No payload mapping')
    reserved = {'SHA256SUMS', 'promotion-manifest.json', 'signing-manifest.json', 'signing-manifest.json.asc'}
    for key in ('sourceName', 'name', 'payloadId'):
        names = [basename(item[key]) for item in payloads]
        if len(names) != len(set(name.casefold() for name in names)):
            raise ValueError('Duplicate payload mapping')
        if key != 'payloadId' and {name.casefold() for name in names} & {name.casefold() for name in reserved}:
            raise ValueError('Reserved payload name')
    for item in payloads:
        if set(item) != {'payloadId', 'sourceName', 'name', 'sha256', 'size', 'signing'}:
            raise ValueError('Invalid payload mapping fields')
        if (not re.fullmatch('[0-9a-f]{64}', item['sha256']) or type(item['size']) is not int
                or item['size'] < 0 or item['signing'] not in ('none', 'gpg')):
            raise ValueError('Invalid payload digest/size/policy')
    assets = release['assets']
    names = [basename(asset['name']) for asset in assets]
    if len(names) != len(set(name.casefold() for name in names)):
        raise ValueError('Duplicate source assets')
    pair = {'signing-manifest.json', 'signing-manifest.json.asc'}
    present = pair & set(names)
    if present and present != pair or any(item['signing'] == 'gpg' for item in payloads) and present != pair:
        raise ValueError('Missing original signing pair')
    expected = {item['sourceName'] for item in payloads} | {'SHA256SUMS'} | present
    if set(names) != expected:
        raise ValueError('Missing/extra source payloads')
    downloaded = {asset['name']: command('api', prefix + '/releases/assets/' + str(asset['id']),
                                        '-H', 'Accept: application/octet-stream', binary=True)
                  for asset in assets}
    checksums = {}
    for line in downloaded['SHA256SUMS'].decode('ascii').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)', line)
        if not match or match[2] in checksums:
            raise ValueError('Invalid source SHA256SUMS')
        checksums[match[2]] = match[1]
    if set(checksums) != expected - {'SHA256SUMS'}:
        raise ValueError('Incomplete source SHA256SUMS')
    for name, digest in checksums.items():
        if hashlib.sha256(downloaded[name]).hexdigest() != digest:
            raise ValueError('Source checksum mismatch')
    outputs = {name: downloaded[name] for name in present}
    promoted = []
    for item in payloads:
        data = downloaded[item['sourceName']]
        if len(data) != item['size'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Approved payload bytes differ')
        outputs[item['name']] = data
        promoted.append({key: value for key, value in item.items() if key != 'signing'})
    outputs['promotion-manifest.json'] = canonical({
        'schema': 'dg-release-promotion-v1', 'catalogSha256': context['catalogSha256'],
        'projectId': context['projectId'], 'repository': repository, 'sourceRc': source,
        'tag': tag, 'payloads': promoted})
    outputs['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
                                  for name, data in sorted(outputs.items())).encode('ascii')
    return outputs


def main():
    context = json.loads(Path('.release/context.json').read_text(), object_pairs_hook=unique_json)
    tag, repository = os.environ['GITHUB_REF_NAME'], os.environ['GITHUB_REPOSITORY']
    outputs = promote(context, tag, repository)
    # gh view includes drafts, unlike the releases/tags endpoint.
    existing = json.loads(gh('release', 'list', '--repo', repository, '--limit', '1000',
                             '--json', 'tagName,isDraft,isPrerelease'))
    found = [release for release in existing if release['tagName'] == tag]
    if not found:
        gh('release', 'create', tag, '--repo', repository, '--verify-tag', '--draft',
           '--latest=false', '--title', tag, '--notes-file', '.release/notes.md')
    release = json.loads(gh('release', 'view', tag, '--repo', repository, '--json', 'assets,isDraft,isPrerelease'))
    if release['isPrerelease']:
        raise ValueError('Final cannot be prerelease')
    names = [asset['name'] for asset in release['assets']]
    if len(names) != len(set(names)) or set(names) - set(outputs):
        raise ValueError('Unexpected final assets')
    for asset in release['assets']:
        data = gh('api', asset['apiUrl'],
                  '-H', 'Accept: application/octet-stream', binary=True)
        if data != outputs[asset['name']]:
            raise ValueError('Refusing divergent final asset')
    if set(outputs) - set(names) and not release['isDraft']:
        raise ValueError('Cannot modify published final')
    Path('dist').mkdir(exist_ok=True)
    for name, data in outputs.items():
        if name not in names:
            path = Path('dist') / name
            path.write_bytes(data)
            gh('release', 'upload', tag, str(path), '--repo', repository)


if __name__ == '__main__':
    main()
