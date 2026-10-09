import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from source import identity, load_sources, public_url, validate

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.source={'id':'sample','name':'Sample','url':'https://example.com/video','language':'all','revision':1,'adult':False,'rules':{}}
    def test_valid(self): self.assertEqual(validate(self.source)['id'],'sample')
    def test_unsafe_urls(self):
        for url in ['file:///etc/passwd','http://example.com','https://localhost','https://127.0.0.1','https://10.0.0.1','https://user:pass@example.com','https://example.com:8080']:
            with self.subTest(url=url),self.assertRaises(ValueError): public_url(url)
    def test_no_path_traversal(self):
        for sid in ['../x','a/b','a;rm','a\nb','bad.name']:
            with self.subTest(sid=sid),self.assertRaises(ValueError):validate(dict(self.source,id=sid))
    def test_stable_identity(self):
        self.assertEqual(identity('Owner/Repo','sample'),identity('owner/repo','sample'))
        self.assertNotEqual(identity('Owner/Other','sample'),identity('Owner/Repo','sample'))
        self.assertTrue(0<int(identity('Owner/Repo','sample')[1])<2**63)
    def test_no_auth_headers(self):
        with self.assertRaises(ValueError):validate(dict(self.source,rules={'extraHeaders':{'Authorization':'secret'}}))
    def test_reject_unknown_rule(self):
        with self.assertRaises(ValueError):validate(dict(self.source,rules={'executeJavaScript':True}))
    def test_bounded_iframes(self):
        with self.assertRaises(ValueError):validate(dict(self.source,rules={'maxIframeDepth':100}))
    def test_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in ['a','b']:Path(temp,name+'.json').write_text(json.dumps(self.source))
            with self.assertRaises(ValueError):load_sources(Path(temp))
    def test_revision_type(self):
        with self.assertRaises(ValueError):validate(dict(self.source,revision=True))
    def test_valid_rules(self):
        self.assertEqual(validate(dict(self.source,rules={'catalogPath':'/?page={page}','itemSelector':'.card','iframeHosts':['player.example.com'],'sendReferer':True}))['rules']['itemSelector'],'.card')

if __name__=='__main__':unittest.main()
