#!/usr/bin/env python3
"""Validate and maintain source definitions. All workflow inputs are treated as data."""
import hashlib
import ipaddress
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    "catalogPath", "searchPath", "latestPath", "itemSelector", "linkSelector",
    "titleSelector", "posterSelector", "posterAttribute", "nextSelector",
    "detailTitleSelector", "descriptionSelector", "episodeSelector",
    "episodeLinkSelector", "episodeTitleSelector", "episodesReversed",
    "videoSelector", "videoAttribute", "iframeSelector", "iframeHosts",
    "maxIframeDepth", "sendReferer", "scanScriptUrls", "extraHeaders",
}

def public_url(raw):
    if not isinstance(raw, str) or len(raw) > 8192:
        raise ValueError("URL must be text shorter than 8192 characters.")
    u = urlsplit(raw.strip())
    if u.scheme != "https" or not u.hostname or u.username or u.password:
        raise ValueError("Use a public HTTPS URL without embedded credentials.")
    host = u.hostname.lower().rstrip('.')
    if '.' not in host or host.endswith(('.local', '.internal', '.localhost')):
        raise ValueError("Local network addresses are unsupported.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[a-z0-9.-]+", host):
            raise ValueError("Use an ASCII or punycode public hostname.")
    else:
        if not address.is_global:
            raise ValueError("Local network addresses are unsupported.")
    if u.port not in (None, 443):
        raise ValueError("Only HTTPS port 443 is supported.")
    return urlunsplit(('https', u.netloc.lower(), u.path or '/', u.query, ''))

def validate(data):
    if not isinstance(data, dict):
        raise ValueError("A source must be a JSON object.")
    extra = set(data) - {'id', 'name', 'url', 'language', 'revision', 'adult', 'rules'}
    if extra:
        raise ValueError('Unknown source fields: ' + ', '.join(sorted(extra)))
    sid = data.get('id', '')
    if not isinstance(sid, str) or not re.fullmatch(r'[a-z][a-z0-9-]{1,47}', sid):
        raise ValueError('Source ID must be 2–48 lowercase letters, numbers or hyphens, starting with a letter.')
    if not isinstance(data.get('name'), str) or not 1 <= len(data['name'].strip()) <= 80 or any(ord(c) < 32 for c in data['name']):
        raise ValueError('Source name must be 1–80 printable characters.')
    data = dict(data, name=data['name'].strip(), url=public_url(data.get('url')))
    if not isinstance(data.get('language'), str) or not re.fullmatch(r'(all|[a-z]{2}(?:-[a-zA-Z]{2})?)', data['language']):
        raise ValueError('Language must be all, en, ja, or another two-letter language code.')
    if type(data.get('revision')) is not int or not 1 <= data['revision'] <= 2_000_000_000:
        raise ValueError('Revision must be a positive integer.')
    if type(data.get('adult')) is not bool:
        raise ValueError('adult must be true or false.')
    rules = data.get('rules', {})
    if not isinstance(rules, dict) or set(rules) - RULES:
        raise ValueError('Unknown extraction rule fields: ' + str(set(rules) - RULES if isinstance(rules,dict) else rules))
    for key, value in rules.items():
        if key in {'episodesReversed', 'sendReferer', 'scanScriptUrls'}:
            if type(value) is not bool: raise ValueError(key + ' must be true or false.')
        elif key == 'maxIframeDepth':
            if type(value) is not int or not 0 <= value <= 3: raise ValueError('maxIframeDepth must be 0–3.')
        elif key == 'iframeHosts':
            if not isinstance(value, list) or len(value) > 12: raise ValueError('iframeHosts must be a list of at most 12 hostnames.')
            for host in value:
                if not isinstance(host, str) or public_url('https://' + host).split('/')[2] != host: raise ValueError('iframeHosts requires exact public hostnames.')
        elif key == 'extraHeaders':
            allowed = {'Accept', 'Accept-Language', 'User-Agent', 'Origin'}
            if not isinstance(value, dict) or set(value) - allowed: raise ValueError('Only Accept, Accept-Language, User-Agent and Origin headers are supported; never store login secrets here.')
            for h in value.values():
                if not isinstance(h, str) or len(h) > 512 or '\r' in h or '\n' in h: raise ValueError('Invalid header value.')
        elif not isinstance(value, str) or len(value) > 1200:
            raise ValueError(key + ' must be text of at most 1200 characters.')
    data['rules'] = rules
    if any(rules.get(k, '').strip() for k in ('catalogPath', 'searchPath', 'latestPath')) and not rules.get('itemSelector', '').strip():
        raise ValueError('Catalogue/search/latest paths require itemSelector to identify result cards.')
    return data

def load_sources(directory=ROOT/'sources'):
    sources = [validate(json.loads(p.read_text())) for p in sorted(directory.glob('*.json'))]
    if len(sources) > 60: raise ValueError('This builder supports at most 60 sources per repository.')
    if len({s['id'] for s in sources}) != len(sources): raise ValueError('Duplicate source IDs.')
    return sources

def identity(repository, sid):
    repo = repository.lower()
    package = 'eu.kanade.tachiyomi.animeextension.all.r' + hashlib.sha256(repo.encode()).hexdigest()[:12] + '.s_' + sid.replace('-', '_')
    source_id = int.from_bytes(hashlib.sha256((repo + '/' + sid).encode()).digest()[:8], 'big') & 0x7fffffffffffffff
    return package, str(source_id)

def apply_input():
    operation = os.getenv('SOURCE_OPERATION', 'rebuild')
    if operation == 'rebuild': return
    sid = os.getenv('SOURCE_ID', '').strip()
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,47}', sid): raise ValueError('Enter a stable source ID, for example my-video-site.')
    target = ROOT/'sources'/(sid+'.json')
    if operation == 'remove':
        if not target.exists(): raise ValueError('Source ID does not exist.')
        target.unlink(); return
    if operation != 'add-or-update': raise ValueError('Unknown operation.')
    old = validate(json.loads(target.read_text())) if target.exists() else None
    classification = os.getenv('SOURCE_ADULT', 'preserve')
    if classification not in {'preserve', 'true', 'false'}:
        raise ValueError('Adult classification must be preserve, true or false.')
    rules_input = os.getenv('SOURCE_RULES', '').strip()
    rules = json.loads(rules_input) if rules_input else (old['rules'] if old else {})
    data = validate({
        'id': sid, 'name': os.getenv('SOURCE_NAME', '').strip() or (old['name'] if old else ''),
        'url': os.getenv('SOURCE_URL', '').strip() or (old['url'] if old else ''),
        'language': os.getenv('SOURCE_LANGUAGE', '').strip() or (old['language'] if old else 'all'),
        'revision': old['revision'] + 1 if old else 1,
        'adult': (old['adult'] if old else False) if classification == 'preserve' else classification == 'true', 'rules': rules,
    })
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')
    load_sources()

if __name__ == '__main__':
    try:
        if '--apply' in sys.argv: apply_input()
        sources = load_sources()
        print('Validated ' + str(len(sources)) + ' source definitions.')
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        sys.exit(str(exc))
