#!/usr/bin/env python3
"""Build real, signed Aniyomi API-17 extension APKs and a complete repository.

Uses checksum-pinned Android/Kotlin tools directly. Gradle, sdkmanager, and a
separate remote repository are not required. Runtime libraries are compile-only.
"""
import argparse
import base64
import hashlib
import html
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from source import ROOT, identity, load_sources

NS = 'http://schemas.android.com/apk/res/android'
ET.register_namespace('android', NS)

def run(args, env, **kwargs):
    result = subprocess.run([str(x) for x in args], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    if result.returncode:
        print(result.stdout[-14000:], file=sys.stderr)
        raise RuntimeError('Command failed: ' + str(args[0]))
    return result.stdout

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''): value.update(block)
    return value.hexdigest()

def prepare(cache):
    lock = json.loads((ROOT/'dependencies.lock.json').read_text())
    def fetch(item):
        name, spec = item; target = cache/spec['file']
        if target.exists() and digest(target) == spec['sha256']: return name, target
        request = urllib.request.Request(spec['url'], headers={'User-Agent':'Aniyomi-Repository-Builder/1.0'})
        print('Fetching ' + name, flush=True)
        with urllib.request.urlopen(request, timeout=120) as response, target.with_suffix('.part').open('wb') as output:
            shutil.copyfileobj(response, output)
        if digest(target.with_suffix('.part')) != spec['sha256']:
            target.with_suffix('.part').unlink(); raise RuntimeError('Checksum mismatch: ' + name)
        target.with_suffix('.part').replace(target)
        return name, target
    cache.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool: files = dict(pool.map(fetch, lock.items()))
    android = cache/'android.jar'
    if not android.exists():
        with zipfile.ZipFile(files['platform']) as archive:
            android.write_bytes(archive.read(next(n for n in archive.namelist() if n.endswith('/android.jar'))))
    api = cache/'extensions-lib.jar'
    with zipfile.ZipFile(files['aniyomi-api']) as archive: api.write_bytes(archive.read('classes.jar'))
    tools = cache/'android-tools'
    if not (tools/'aapt').exists():
        tools.mkdir(exist_ok=True)
        with zipfile.ZipFile(files['build-tools']) as archive:
            for entry in archive.infolist():
                parts = Path(entry.filename).parts[1:]
                if not parts or '..' in parts: continue
                target = tools.joinpath(*parts)
                if entry.is_dir(): target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(entry))
                    target.chmod(0o755 if target.name in {'aapt','aapt2','zipalign','d8','apksigner'} else 0o644)
    return files, android, api, tools

def java_environment():
    java_home = os.getenv('JAVA_HOME')
    if java_home: java = Path(java_home)/'bin/java'
    else:
        found = shutil.which('java')
        if not found: raise RuntimeError('JDK 17+ is required. The GitHub workflow installs it automatically.')
        java = Path(found).resolve(); java_home = str(java.parent.parent)
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(Path(java_home)/'lib') + ':' + str(Path(java_home)/'lib/server') + ':' + env.get('LD_LIBRARY_PATH','')
    return java, env

def icon(path):
    width = 96; rows = bytearray()
    for y in range(width):
        rows.append(0)
        for x in range(width):
            triangle = 30 <= x <= 70 and abs(y - 48) <= (70 - x) * .7
            rows.extend((137,237,208,255) if triangle else (11,15,25,255))
    def chunk(kind, data): return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,width,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))

def manifest(path, package, name, number, adult):
    root = ET.Element('manifest', {'package':package, f'{{{NS}}}versionCode':str(number), f'{{{NS}}}versionName':'17.'+str(number)})
    ET.SubElement(root, 'uses-sdk', {f'{{{NS}}}minSdkVersion':'24',f'{{{NS}}}targetSdkVersion':'35'})
    ET.SubElement(root, 'uses-feature', {f'{{{NS}}}name':'tachiyomi.animeextension', f'{{{NS}}}required':'false'})
    app = ET.SubElement(root, 'application', {f'{{{NS}}}label':'Aniyomi: '+name, f'{{{NS}}}icon':'@drawable/icon',f'{{{NS}}}allowBackup':'false',f'{{{NS}}}hasCode':'true'})
    for key, value in [('tachiyomi.animeextension.class',package+'.Source'),('tachiyomi.animeextension.nsfw',str(int(adult))),('aniyomix.name',name),('aniyomix.extensionLib','17')]:
        ET.SubElement(app,'meta-data',{f'{{{NS}}}name':key,f'{{{NS}}}value':value})
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)

def compiler(files, java):
    names=['compiler','compiler-api','stdlib','script-runtime','reflect','daemon','coroutines','annotations']
    return [java,'-Xmx1536m','-cp',os.pathsep.join(str(files[n]) for n in names),'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler']

def compile_apk(source, repository, number, work, out, prepared, java, env, key):
    files, android, api, tools = prepared
    package, source_id = identity(repository, source['id'])
    work.mkdir(parents=True, exist_ok=True)
    encoded = base64.b64encode(json.dumps(dict(source,sourceId=source_id)).encode()).decode()
    generated = work/'Source.kt'
    generated.write_text('package '+package+'\nclass Source : dev.reel.websource.WebSiteSource("'+encoded+'")\n')
    classpath = [android, api] + [p for n,p in files.items() if p.suffix == '.jar' and n not in {'compiler','compiler-api','reflect','script-runtime','daemon','json-tests'}]
    classes = work/'classes.jar'
    run(compiler(files,java)+['-no-stdlib','-no-reflect','-jvm-target','17','-classpath',os.pathsep.join(map(str,classpath)), '-d',classes,ROOT/'engine/Parser.kt',ROOT/'engine/WebSiteSource.kt',generated],env)
    dex = work/'dex'; dex.mkdir(exist_ok=True)
    command = [java,'-Xmx1024m','-cp',tools/'lib/d8.jar','com.android.tools.r8.D8','--release','--min-api','24','--lib',android,'--output',dex]
    for dependency in classpath[1:]: command.extend(['--classpath',dependency])
    run(command+[classes],env)
    icon(work/'res/drawable/icon.png')
    manifest(work/'AndroidManifest.xml',package,source['name'],number,source['adult'])
    unsigned=work/'unsigned.apk'; aligned=work/'aligned.apk'
    binary_env=dict(env,LD_LIBRARY_PATH=str(tools/'lib64')+':'+env.get('LD_LIBRARY_PATH',''))
    run([tools/'aapt','package','-f','-M',work/'AndroidManifest.xml','-S',work/'res','-I',android,'-F',unsigned],binary_env)
    with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as archive:
        for part in sorted(dex.glob('*.dex')): archive.write(part,part.name)
    run([tools/'zipalign','-p','-f','4',unsigned,aligned],binary_env)
    filename=source['id']+'-v17.'+str(number)+'.apk'; apk=out/'apk'/filename
    run([java,'-jar',tools/'lib/apksigner.jar','sign','--ks',key,'--ks-key-alias','repo','--ks-pass','env:REPO_SIGNING_PASSWORD','--key-pass','env:REPO_SIGNING_PASSWORD','--out',apk,aligned],env)
    verified=run([java,'-jar',tools/'lib/apksigner.jar','verify','--verbose','--print-certs',apk],env)
    fingerprint=re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-fA-F]+)',verified)
    if not fingerprint: raise RuntimeError('Could not verify APK signing fingerprint.')
    print('Built and verified: '+filename,flush=True)
    return {'name':source['name'],'pkg':package,'apk':filename,'lang':source['language'],'code':number,'version':'17.'+str(number),'nsfw':int(source['adult']),'sources':[{'id':source_id,'lang':source['language'],'name':source['name'],'baseUrl':source['url']}], 'sha256':digest(apk)}, fingerprint.group(1).lower()

def publish_index(repository, records, fingerprint, output):
    base='https://raw.githubusercontent.com/'+repository+'/repo'
    extension_list=[]
    for record in records:
        extension_list.append({'name':record['name'],'packageName':record['pkg'],'resources':{'apkUrl':base+'/apk/'+record['apk'],'iconUrl':base+'/icon.png'},'extensionLib':'17','versionCode':record['code'],'versionName':record['version'],'contentWarning':'NSFW' if record['nsfw'] else 'SAFE','isTorrent':False,'sources':[{'id':int(s['id']),'name':s['name'],'language':s['lang'],'homeUrl':s['baseUrl'],'mirrorUrls':[],'message':None} for s in record['sources']]})
    store={'name':repository+' video sources','badgeLabel':'WEB','signingKey':fingerprint,'contact':{'website':'https://github.com/'+repository,'discord':None},'extensionList':{'extensions':extension_list},'extensionListUrl':None}
    legacy_meta={'index_v2':base+'/store.json','meta':{'name':store['name'],'shortName':'WEB','website':store['contact']['website'],'signingKeyFingerprint':fingerprint}}
    for name,data in [('index.min.json',records),('repo.json',legacy_meta),('store.json',store)]:
        (output/name).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
    (output/'checksums.json').write_text(json.dumps({r['apk']:r['sha256'] for r in records},indent=2)+'\n')
    icon(output/'icon.png')
    links=''.join('<li><strong>'+html.escape(r['name'])+'</strong> · '+html.escape(r['version'])+' <a href="apk/'+html.escape(r['apk'])+'">Download APK</a></li>' for r in records)
    (output/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Video sources</title><style>body{background:#0b0f19;color:#f0f5fc;font:16px/1.7 system-ui;max-width:860px;margin:50px auto;padding:24px}a{color:#89edd0}code{overflow-wrap:anywhere}li{padding:12px 0}</style><h1>Aniyomi video sources</h1><p>Add this extension store in Aniyomi 0.18.2.1 or newer:</p><p><code>'+html.escape(base+'/store.json')+'</code></p><p>Signing fingerprint: <code>'+fingerprint+'</code></p><ul>'+links+'</ul><p>Each source is a native extension. It uses static extraction rules; support varies by website.</p></html>')
    (output/'README.md').write_text('# Aniyomi video sources\n\nAdd this URL in Aniyomi 0.18.2.1+:\n\n'+base+'/store.json\n\nLegacy-compatible entry URL: '+base+'/index.min.json\n\nSigning certificate SHA-256: `'+fingerprint+'`\n\nUse Actions in the main source repository to add or update websites.\n')
    return base+'/store.json'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repository',default=os.getenv('GITHUB_REPOSITORY'))
    parser.add_argument('--build-number',type=int,default=int(os.getenv('GITHUB_RUN_NUMBER','1')))
    parser.add_argument('--cache',type=Path,default=ROOT/'.cache')
    parser.add_argument('--key',type=Path,default=ROOT/'signing/repo.p12')
    args=parser.parse_args()
    if not args.repository or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.repository): raise ValueError('A GitHub owner/repository name is required.')
    if not 1 <= args.build_number <= 2_000_000_000: raise ValueError('Invalid build number.')
    if not args.key.is_file() or not os.getenv('REPO_SIGNING_PASSWORD'): raise ValueError('Set the signing key and REPO_SIGNING_PASSWORD first. See the setup guide.')
    sources=load_sources(); java,env=java_environment(); prepared=prepare(args.cache.resolve())
    output=ROOT/'repo-output'
    if output.exists(): shutil.rmtree(output)
    (output/'apk').mkdir(parents=True)
    records=[]; fingerprints=set()
    for source in sources:
        record,fingerprint=compile_apk(source,args.repository,args.build_number,ROOT/'build'/source['id'],output,prepared,java,env,args.key.resolve())
        records.append(record);fingerprints.add(fingerprint)
    if not sources:
        cert=run([java.parent/'keytool','-exportcert','-keystore',args.key,'-alias','repo','-storepass:env','REPO_SIGNING_PASSWORD','-rfc'],env)
        encoded=''.join(line for line in cert.splitlines() if not line.startswith('-----'))
        fingerprints.add(hashlib.sha256(base64.b64decode(encoded)).hexdigest())
    if len(fingerprints)!=1: raise RuntimeError('All APKs must use the same signing key.')
    url=publish_index(args.repository,records,next(iter(fingerprints)),output)
    print('Repository output verified: '+str(output))
    summary=os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as file:file.write('## Your Aniyomi repository\n\nAfter this run succeeds, add:\n\n`'+url+'`\n\nBuilt '+str(len(records))+' signed extensions.\n')

if __name__=='__main__':
    try: main()
    except Exception as exc: sys.exit(str(exc))
