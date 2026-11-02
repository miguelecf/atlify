"""Static release checks. Standard library only; no network or application execution."""
import gzip
import json
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs'


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class Site(unittest.TestCase):
    def test_personal_brand_tokens(self):
        css = (DOCS / 'styles.css').read_text()
        for value in ('#183e32', '#f3f3f1', '#dedfdb', '#555b57', 'Archivo Black', '1180px'):
            self.assertIn(value, css)
        self.assertIn('prefers-reduced-motion', css)
        self.assertIn(':focus-visible', css)

    def test_local_links_assets_and_anchors_exist(self):
        for page in [DOCS / 'index.html', DOCS / 'social-card.html']:
            doc = Document(page.read_text())
            ids = [attrs['id'] for _, attrs in doc.elements if 'id' in attrs]
            self.assertEqual(len(ids), len(set(ids)), 'Duplicate IDs')
            for tag, attrs in doc.elements:
                for attr in ('src', 'href'):
                    value = attrs.get(attr, '')
                    if not value or urlsplit(value).scheme or value.startswith('//'):
                        continue
                    url = urlsplit(value)
                    if url.path:
                        target = (page.parent / unquote(url.path)).resolve()
                        self.assertTrue(target.is_relative_to(DOCS), value)
                        self.assertTrue(target.is_file(), f'{page.name}: {value}')
                    elif url.fragment:
                        self.assertIn(unquote(url.fragment), ids)

    def test_no_remote_runtime_dependencies(self):
        doc = Document((DOCS / 'index.html').read_text())
        for tag, attrs in doc.elements:
            resource = attrs.get('src', '') if tag in ('script', 'img', 'iframe') else ''
            if tag == 'link' and attrs.get('rel') in ('stylesheet', 'preload', 'preconnect'):
                resource = attrs.get('href', '')
            self.assertFalse(urlsplit(resource).netloc, resource)
        css = (DOCS / 'styles.css').read_text()
        for url in re.findall(r'url\([\'"]?(.*?)[\'"]?\)', css):
            self.assertFalse(urlsplit(url).netloc)
            self.assertTrue((DOCS / url).is_file(), url)

    def test_social_metadata_and_png_dimensions(self):
        doc = Document((DOCS / 'index.html').read_text())
        meta = {a.get('property', a.get('name')): a.get('content') for t, a in doc.elements if t == 'meta'}
        self.assertEqual(meta['og:image'], meta['twitter:image'])
        data = (DOCS / 'img/og-atlify.png').read_bytes()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II', data[16:24]), (1200, 630))
        self.assertEqual(meta['og:image:width'], '1200')
        self.assertEqual(meta['og:image:height'], '630')

    def test_public_demo_counts_match_fixture(self):
        fixture = json.loads((ROOT / 'evals/fixtures/pet-care-api/atlas.json').read_text())
        source = (DOCS / 'demo/atlas.html').read_text()
        data = json.loads(re.search(r'<script id="atlas-datos" type="application/json">(.*?)</script>', source, re.S)[1])
        self.assertEqual(len(fixture['hallazgos']), 11)
        self.assertEqual([h['id'] for h in data['hallazgos']], [h['id'] for h in fixture['hallazgos']])
        self.assertEqual([(e['metodo'], e['ruta']) for e in data['endpoints']],
                         [(e['metodo'], e['ruta']) for e in fixture['endpoints']])
        self.assertNotIn('__ATLAS_DATOS__', source)
        self.assertNotIn('/*__VENDOR__*/', source)
        self.assertNotIn('/*__FONTS__*/', source)

    def test_release_check_without_writes(self):
        before = {p: p.stat().st_mtime_ns for p in DOCS.rglob('*') if p.is_file()}
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/release.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})

    def test_release_comparison_ignores_gzip_header_not_source_changes(self):
        import base64
        sys.path.insert(0, str(ROOT / 'scripts'))
        from release import comparable
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / f'{i}.html' for i in range(3)]
            for path, content, mtime in zip(paths, (b'same', b'same', b'changed'), (0, 99, 0)):
                blob = base64.b64encode(gzip.compress(content, mtime=mtime)).decode()
                path.write_text('"fuentesGz": "' + blob + '"')
            self.assertEqual(comparable(paths[0]), comparable(paths[1]))
            self.assertNotEqual(comparable(paths[0]), comparable(paths[2]))

    def test_build_has_reproducible_gzip_timestamp(self):
        # Intercept the builder's compression call; no wall-clock sleeps required.
        sys.path.insert(0, str(ROOT / 'scripts'))
        import build
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'atlas.html'
            argv = ['build.py', str(ROOT / 'evals/fixtures/pet-care-api/repo'), '--atlas',
                    str(ROOT / 'evals/fixtures/pet-care-api/atlas.json'), '-o', str(output)]
            with patch.object(sys, 'argv', argv), patch.object(build.gzip, 'compress', wraps=gzip.compress) as compress:
                build.main()
                self.assertEqual(compress.call_args.kwargs.get('mtime'), 0)
                first = output.read_bytes()
                build.main()
                self.assertEqual(first, output.read_bytes())


if __name__ == '__main__':
    unittest.main()
