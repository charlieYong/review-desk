"""统一提供 HTML 方案目录、批注入口和原始静态资源。"""
import argparse
import hashlib
import json
import html
import re
from markdown_it import MarkdownIt
from markdown_it.token import Token
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlsplit, parse_qs

APP = Path(__file__).resolve().parent


def render_markdown(content, name):
    """以 README 风格渲染正文，保留原 URL 以支持相对图片和链接。"""
    md = MarkdownIt('js-default')
    tokens = md.parse(content)
    used_ids = set()
    for i, token in enumerate(tokens):
        if token.type == 'heading_open':
            heading = tokens[i + 1].content
            slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-') or 'section'
            unique = slug
            suffix = 1
            while unique in used_ids:
                unique = f'{slug}-{suffix}'
                suffix += 1
            used_ids.add(unique)
            token.attrSet('id', unique)
        if token.type == 'inline' and i >= 2 and tokens[i-2].type == 'list_item_open':
            children = token.children or []
            if children and children[0].type == 'text' and re.match(r'^\[[ xX]\] ', children[0].content):
                checked = children[0].content[1].lower() == 'x'
                children[0].content = children[0].content[4:]
                checkbox = Token('html_inline', '', 0)
                checkbox.content = '<input type="checkbox" disabled' + (' checked' if checked else '') + '> '
                children.insert(0, checkbox)
    body = md.renderer.render(tokens, md.options, {})
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + html.escape(name) + '</title>'
            '<link rel="stylesheet" href="/_preview/theme.css">'
            '<body class="markdown-page"><main class="readme"><div class="readme-bar">'
            '<span>▤ &nbsp; ' + html.escape(name) + '</span><span>Markdown</span></div>'
            '<article class="markdown-body">' + body + '</article></main></body></html>')


class Handler(SimpleHTTPRequestHandler):
    def send_content(self, body, content_type):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/_preview/files':
            root = Path(self.directory).resolve()
            files = []
            for p in root.rglob('*'):
                if p.suffix.lower() not in ('.html', '.htm', '.md', '.markdown'):
                    continue
                try:
                    if not p.is_file() or not p.resolve().is_relative_to(root):
                        continue
                    name = p.relative_to(root).as_posix()
                    files.append({'name': name, 'url': '/' + quote(name), 'modified': p.stat().st_mtime, 'kind': 'Markdown' if p.suffix.lower() in ('.md', '.markdown') else 'HTML'})
                except OSError:
                    continue
            files.sort(key=lambda f: (-f['modified'], f['name']))
            self.send_content(json.dumps(files, ensure_ascii=False).encode(), 'application/json; charset=utf-8')
        elif path == '/_preview/document':
            page = parse_qs(urlsplit(self.path).query).get('page', [''])[0]
            root = Path(self.directory).resolve()
            source = Path(self.translate_path(page)).resolve()
            if not source.is_relative_to(root) or not source.is_file() or source.suffix.lower() not in ('.html', '.htm', '.md', '.markdown'):
                self.send_error(404, 'Document not found')
                return
            try:
                raw = source.read_bytes()
                content = raw.decode('utf-8-sig')
            except (OSError, UnicodeError):
                self.send_error(400, 'Cannot read document as UTF-8')
                return
            if source.suffix.lower() in ('.md', '.markdown'):
                content = render_markdown(content, source.name)
            self.send_content(json.dumps({'revision': hashlib.sha256(raw).hexdigest(), 'html': content}, ensure_ascii=False).encode(), 'application/json; charset=utf-8')
        elif path == '/_preview/theme.css':
            self.send_content((APP / 'theme.css').read_bytes(), 'text/css; charset=utf-8')
        elif Path(path).suffix.lower() in ('.md', '.markdown') and 'raw' not in parse_qs(urlsplit(self.path).query):
            root = Path(self.directory).resolve()
            source = Path(self.translate_path(self.path)).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                self.send_error(404, 'Markdown file not found')
                return
            try:
                content = source.read_text(encoding='utf-8-sig')
            except (OSError, UnicodeError):
                self.send_error(400, 'Cannot read Markdown as UTF-8')
                return
            self.send_content(render_markdown(content, source.name).encode(), 'text/html; charset=utf-8')
        elif path in ('/', '/_review'):
            name = 'index.html' if path == '/' else 'review.html'
            self.send_content((APP / name).read_bytes(), 'text/html; charset=utf-8')
        else:
            super().do_GET()

    def do_HEAD(self):
        self.do_GET()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8088)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.bind, args.port), partial(Handler, directory=args.directory))
    print(f'Review Desk: http://{args.bind}:{server.server_port}', flush=True)
    server.serve_forever()
