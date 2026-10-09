#!/usr/bin/env python3
"""Create a private signing kit locally. Never commit its output to GitHub."""
import base64
import hashlib
import html
import os
import secrets
import sys
from pathlib import Path
from build import java_environment, run

def create(destination):
    destination.mkdir(parents=True,exist_ok=True)
    key=destination/'repo.p12'
    if key.exists(): raise ValueError('Refusing to replace an existing signing key.')
    password=secrets.token_urlsafe(32)
    java,env=java_environment();env['REPO_SIGNING_PASSWORD']=password
    run([java.parent/'keytool','-genkeypair','-alias','repo','-keyalg','RSA','-keysize','3072','-validity','10000','-storetype','PKCS12','-keystore',key,'-storepass:env','REPO_SIGNING_PASSWORD','-keypass:env','REPO_SIGNING_PASSWORD','-dname','CN=Personal Aniyomi Repository','-noprompt'],env)
    key.chmod(0o600)
    certificate=destination/'certificate.der'
    run([java.parent/'keytool','-exportcert','-alias','repo','-keystore',key,'-storepass:env','REPO_SIGNING_PASSWORD','-file',certificate],env)
    fingerprint=hashlib.sha256(certificate.read_bytes()).hexdigest()
    (destination/'password.txt').write_text(password+'\n');(destination/'password.txt').chmod(0o600)
    encoded=base64.b64encode(key.read_bytes()).decode()
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"><title>Private Aniyomi signing setup</title><style>body{background:#0b0f19;color:#eef4ff;font:16px/1.6 system-ui;max-width:840px;margin:32px auto;padding:20px}textarea{width:100%;height:120px;background:#151e2d;color:white;border:1px solid #3b4960;border-radius:10px;padding:12px}button{background:#89edd0;color:#08271d;border:0;border-radius:8px;padding:12px 20px;margin:8px 0;font-weight:700}code{overflow-wrap:anywhere}aside{border:1px solid #c59246;padding:14px;border-radius:10px}</style><h1>Private repository signing kit</h1><aside>This file contains your private signing key. Keep it offline or in private storage. Never upload it to a public repository, issue, or chat. Publish only the separate source-project ZIP.</aside><p>In GitHub, open your repository → Settings → Secrets and variables → Actions → New repository secret. Add both secrets below.</p><h2>REPO_SIGNING_KEY</h2><textarea id="key" readonly>KEY_DATA</textarea><button onclick="copy('key',this)">Copy key</button><h2>REPO_SIGNING_PASSWORD</h2><textarea id="password" readonly>PASSWORD_DATA</textarea><button onclick="copy('password',this)">Copy password</button><h2>Public fingerprint</h2><code>FINGERPRINT_DATA</code><p>Back up this kit. The same key must sign future updates. The page makes no network requests.</p><script>async function copy(id,b){const t=document.getElementById(id);try{await navigator.clipboard.writeText(t.value);b.textContent='Copied';}catch{t.focus();t.select();b.textContent='Selected — use Copy';}}</script></html>'''
    page=page.replace('KEY_DATA',encoded).replace('PASSWORD_DATA',html.escape(password)).replace('FINGERPRINT_DATA',fingerprint)
    (destination/'Aniyomi-Signing-Setup.html').write_text(page)
    print('Private signing kit created. Public fingerprint: '+fingerprint)
    return key

if __name__=='__main__':create(Path(sys.argv[1] if len(sys.argv)>1 else 'signing').resolve())
