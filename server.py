"""统一提供 HTML 方案目录、批注入口和原始静态资源。"""
import argparse
import hashlib
import json
import html
import os
import re
import stat
from markdown_it import MarkdownIt
from markdown_it.token import Token
from functools import partial
from html.parser import HTMLParser
from review_store import ReviewStore, Conflict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from urllib.parse import quote, unquote, urlsplit, parse_qs, urlencode
from urllib.request import url2pathname

APP = Path(__file__).resolve().parent
DOC_SUFFIXES = {'.html', '.htm', '.md', '.markdown'}
FS_PREFIX = '/_fs'
RESOURCE_PREFIX = '/_d/'
BROWSE_PREFIX = '/_browse/'
REVIEW_PREFIX = '/_review/'
REVIEW_ID = re.compile(r'/_review/(?:[^/]+/)?([A-Za-z0-9_-]{16})')
MERMAID_VERSION = '11.16.1'
MERMAID_JS = APP / 'vendor' / 'mermaid.min.js'
MERMAID_BOOT = (
    f'<script src="/_preview/mermaid.min.js?v={MERMAID_VERSION}"></script>'
    '<script>(function(){'
    'function fit(){'
    'var cap=Math.min(window.innerHeight*0.88,800);'
    'document.querySelectorAll("pre.mermaid svg").forEach(function(svg){'
    'var box=svg.closest("pre.mermaid");if(!box)return;'
    'var vb=svg.viewBox&&svg.viewBox.baseVal,w,h;'
    'try{w=vb&&vb.width||svg.getBBox().width;h=vb&&vb.height||svg.getBBox().height}catch(e){return}'
    'if(!w||!h)return;'
    'var s=Math.min((Math.max(120,box.clientWidth-8))/w,cap/h,1);'
    'svg.style.width=(w*s)+"px";svg.style.height=(h*s)+"px";'
    'svg.removeAttribute("width");svg.removeAttribute("height");'
    '});}'
    'mermaid.initialize({startOnLoad:false,securityLevel:"strict",theme:"neutral",'
    'fontFamily:"-apple-system,BlinkMacSystemFont,sans-serif",fontSize:14,'
    'flowchart:{useMaxWidth:false,htmlLabels:true,padding:4,nodeSpacing:16,rankSpacing:16,wrappingWidth:200}});'
    'Promise.resolve(mermaid.run()).then(fit).catch(function(){});'
    'window.addEventListener("resize",fit);'
    '})();</script>'
)


def is_doc_file(source):
    try:
        return source.is_file() and source.suffix.lower() in DOC_SUFFIXES
    except OSError:
        return False


def filesystem_page(source):
    posix = source.as_posix()
    if re.match(r'^[A-Za-z]:/', posix):
        return '/_fs/' + quote(posix, safe=':/')
    return '/_fs' + quote(posix, safe='/')


def path_from_fs_url(url_path):
    if url_path != FS_PREFIX and not url_path.startswith(FS_PREFIX + '/'):
        return None
    rest = unquote(url_path[len(FS_PREFIX):])
    if re.match(r'^/[A-Za-z]:/', rest):
        rest = rest[1:]
    if not rest or rest == '/':
        return None
    try:
        return Path(rest).expanduser().resolve()
    except (OSError, ValueError, RuntimeError):
        return None


def page_url(route, **params):
    return route + '?' + urlencode(params) if params else route


def project_directory(source):
    return next((folder for folder in source.parents if (folder / '.git').exists()), source.parent)


def project_label(scope):
    return scope.name if (scope / '.git').exists() else None


def title_slug(text, limit=96):
    slug = re.sub(r'[^\w]+', '-', text).strip('-')[:limit]
    while len(quote(slug, safe='')) > limit:
        slug = slug[:-1]
    return slug.rstrip('-')


class DocumentTitle(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reading = False
        self.found = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'title' and not self.found:
            self.found = self.reading = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.reading = False

    def handle_data(self, data):
        if self.reading:
            self.parts.append(data)


def document_slug(source):
    title = ''
    try:
        content = source.read_text(encoding='utf-8-sig')
        if source.suffix.lower() in ('.md', '.markdown'):
            tokens = MarkdownIt('js-default').parse(content)
            heading = next((tokens[i + 1] for i, token in enumerate(tokens)
                            if token.type == 'heading_open' and token.tag == 'h1'), None)
            if heading is not None:
                title = ''.join(' ' if t.type in ('softbreak', 'hardbreak') else t.content
                                for t in heading.children or [] if t.type != 'image')
        else:
            parser = DocumentTitle()
            parser.feed(content)
            title = ''.join(parser.parts)
    except (OSError, UnicodeError):
        pass
    if re.search(r'(?i)(?:^|\s)(?:file:|[a-z]:[\\/]|~?[\\/])', title):
        title = ''
    return title_slug(title) or title_slug(source.stem) or 'document'


def name_context(source):
    scope = project_directory(source)
    project = [scope.name] if project_label(scope) else []
    return [title_slug(name, 32) for name in (*project, *reversed(source.parent.relative_to(scope).parts))]


def review_slug(source, documents):
    slug = documents[str(source)]['slug'] or title_slug(source.stem) or 'document'
    peers = [Path(path) for path, item in documents.items()
             if path != str(source) and item['slug'] == slug]
    if not peers:
        return slug
    used = {name for peer in peers for name in name_context(peer)}
    context = min((name for name in name_context(source) if name and name not in used), key=len, default='')
    if not context:
        filename = title_slug(source.stem, 32)
        if filename != slug and filename not in {title_slug(peer.stem, 32) for peer in peers}:
            context = filename
    return f'{title_slug(slug, 95 - len(quote(context, safe="")))}-{context}' if context else slug


def fence_language(info):
    info = (info or '').strip()
    return info.split(None, 1)[0].lower() if info else ''


def render_markdown(content, name, *, directory=None):
    """以 README 风格渲染正文，保留原 URL 以支持相对图片和链接。"""
    md = MarkdownIt('js-default')
    original_fence = md.renderer.rules['fence']

    def render_fence(tokens, idx, options, env):
        token = tokens[idx]
        if fence_language(token.info) == 'mermaid':
            return '<pre class="mermaid">' + html.escape(token.content) + '</pre>\n'
        return original_fence(tokens, idx, options, env)

    md.renderer.rules['fence'] = render_fence
    tokens = md.parse(content)
    used_ids = set()
    has_mermaid = False
    for i, token in enumerate(tokens):
        if token.type == 'fence' and fence_language(token.info) == 'mermaid':
            has_mermaid = True
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
    mermaid = MERMAID_BOOT if has_mermaid and MERMAID_JS.is_file() else ''
    directory_link = (f'<a class="markdown-directory-link" href="{directory}">返回上层目录</a>'
                      if directory else '<span>Markdown</span>')
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + html.escape(name) + '</title>'
            '<link rel="stylesheet" href="/_preview/theme.css">'
            '<body class="markdown-page"><main class="readme"><div class="readme-bar">'
            '<span>▤ &nbsp; ' + html.escape(name) + '</span>' + directory_link + '</div>'
            '<article class="markdown-body">' + body + '</article></main>'
            + mermaid + '</body></html>')


class Handler(SimpleHTTPRequestHandler):
    def send_content(self, body, content_type, cache='no-store', status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', cache)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def redirect(self, target):
        self.send_response(302)
        self.send_header('Location', target)
        self.send_header('Content-Length', '0')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    @property
    def content_root(self):
        return Path(self.directory).resolve()

    def send_local_file(self, source, directory=None):
        if source.suffix.lower() in ('.md', '.markdown') and 'raw' not in parse_qs(urlsplit(self.path).query):
            self.send_markdown(source, directory)
            return
        try:
            data = source.read_bytes()
        except OSError:
            self.send_error(404, 'File not found')
            return
        self.send_content(data, self.guess_type(str(source)))

    def send_markdown(self, source, directory=None):
        try:
            content = source.read_text(encoding='utf-8-sig')
        except (OSError, UnicodeError):
            self.send_error(400, 'Cannot read Markdown as UTF-8')
            return
        if directory is None:
            if source.is_relative_to(self.content_root):
                directory = page_url('/_browse', page=self.content_page(source))
            else:
                scope = project_directory(source)
                try:
                    catalog = self.server.reviews.catalog(scopes=(scope,))
                    directory = self.folder_url(source.parent, scope, catalog)
                except OSError:
                    directory = page_url('/_browse', page=filesystem_page(source))
        body = render_markdown(content, source.name, directory=html.escape(directory, quote=True))
        self.send_content(body.encode(), 'text/html; charset=utf-8')

    def content_page(self, source):
        return '/' + quote(source.relative_to(self.content_root).as_posix())

    @staticmethod
    def scope_path(catalog, key):
        return next((Path(path) for path, value in catalog['scopes'].items() if value == key), None)

    @staticmethod
    def scope_target(scope, relative):
        if scope is not None:
            try:
                target = (scope / relative).resolve()
                if target.is_relative_to(scope):
                    return target
            except (OSError, ValueError, RuntimeError):
                pass
        return None

    def scoped_source(self, url_path, catalog):
        key, _, relative = url_path[len(RESOURCE_PREFIX):].partition('/')
        scope = self.scope_path(catalog, key)
        return self.scope_target(scope, unquote(relative)), scope

    def locate_source(self, raw):
        raw = (raw or '').strip()
        if not raw:
            return None
        if raw.lower().startswith('file:'):
            raw = url2pathname(unquote(urlsplit(raw).path))
        elif raw.startswith((FS_PREFIX + '/', RESOURCE_PREFIX, REVIEW_PREFIX)):
            return self.resolve_document(raw)
        try:
            candidate = Path(raw).expanduser()
            if candidate.is_absolute():
                source = candidate.resolve()
                if is_doc_file(source):
                    return source
        except (OSError, ValueError, RuntimeError):
            pass
        return self.resolve_document('/' + raw.replace('\\', '/').lstrip('/'))

    def resolve_document(self, page):
        if not isinstance(page, str) or not page:
            return None
        try:
            url_path = urlsplit(page).path
        except ValueError:
            return None
        match = REVIEW_ID.fullmatch(url_path)
        if match or url_path.startswith(RESOURCE_PREFIX):
            catalog = self.server.reviews.catalog()
        if match:
            source = next((Path(path) for path, record in catalog['documents'].items()
                           if record['id'] == match[1]), None)
            try:
                if source is not None and source.resolve() != source:
                    return None
            except (OSError, ValueError, RuntimeError):
                return None
        elif url_path.startswith(REVIEW_PREFIX):
            return None
        elif url_path.startswith(RESOURCE_PREFIX):
            source, _ = self.scoped_source(url_path, catalog)
        elif url_path == FS_PREFIX or url_path.startswith(FS_PREFIX + '/'):
            source = path_from_fs_url(url_path)
        else:
            try:
                source = Path(self.translate_path(url_path)).resolve()
                if not source.is_relative_to(self.content_root):
                    return None
            except (OSError, ValueError, RuntimeError):
                return None
        if source is not None and is_doc_file(source):
            return source
        return None

    def document_scope(self, source, page='', query=None):
        root = self.content_root
        if source.is_relative_to(root):
            return root
        query = query or {}
        key = query.get('scope', [''])[0]
        if not key and page.startswith(RESOURCE_PREFIX):
            key = page[len(RESOURCE_PREFIX):].split('/', 1)[0]
        if key:
            scope = self.scope_path(self.server.reviews.catalog(), key)
            if scope is not None and source.is_relative_to(scope):
                return scope
        previous = self.resolve_document(query.get('from', [''])[0])
        if previous is not None and not previous.is_relative_to(root):
            scope = project_directory(previous)
            if source.is_relative_to(scope):
                return scope
        return project_directory(source)

    def folder_url(self, folder, scope, catalog):
        relative = folder.relative_to(scope)
        if scope == self.content_root:
            return page_url('/_browse', dir=relative.as_posix())
        key = catalog['scopes'][str(scope)]
        label = quote(title_slug(project_label(scope) or 'standalone') or 'project', safe='')
        suffix = '' if folder == scope else quote(relative.as_posix())
        return f'{BROWSE_PREFIX}{label}/{key}/{suffix}'

    def document_info(self, source, catalog=None, scope=None):
        root = self.content_root
        public_id = None
        if source.is_relative_to(root):
            page = self.content_page(source)
            public_id = page
            directory = page_url('/_browse', page=page)
            name = source.relative_to(root).as_posix()
        else:
            scope = scope or project_directory(source)
            label = project_label(scope)
            relative = source.relative_to(scope).as_posix()
            name = label + '/' + relative if label else relative
            if catalog is None:
                page = filesystem_page(source)
                directory = page_url('/_browse', page=page)
            else:
                key = catalog['scopes'][str(scope)]
                page = f'{RESOURCE_PREFIX}{key}/{quote(relative)}'
                directory = self.folder_url(source.parent, scope, catalog)
        review = page_url('/_review', page=page)
        contextual = review
        if catalog is not None and not source.is_relative_to(root):
            documents = catalog['documents']
            record = documents.get(str(source))
            if record and record['id']:
                public_id = record['id']
                slug = quote(review_slug(source, documents), safe='')
                review = f'{REVIEW_PREFIX}{slug}/{public_id}'
                contextual = (review if scope == project_directory(source)
                              else page_url(review, scope=key))
        return {'id': public_id, 'page': page, 'review': review, 'reviewContext': contextual, 'name': name,
                'fileName': source.name, 'directory': directory, 'preview': page_url('/_preview/view', page=page)}

    def register_document(self, source, page='', query=None, *, warn=False):
        scope = None
        try:
            scope = self.document_scope(source, page, query)
            slug = None if source.is_relative_to(self.content_root) else document_slug(source)
            scopes = () if scope == self.content_root else (scope, project_directory(source))
            catalog = self.server.reviews.catalog({source: slug}, scopes)
            return self.document_info(source, catalog, scope)
        except OSError:
            if not warn:
                raise
            catalog = None
            if scope is not None and scope != self.content_root:
                try:
                    existing = self.server.reviews.catalog()
                    if (str(scope) in existing['scopes'] and
                            existing['documents'].get(str(source), {}).get('id')):
                        catalog = existing
                except OSError:
                    pass
            info = self.document_info(source, catalog, scope)
            info['catalogWarning'] = '方案列表登记未完成；批注仍可使用，请稍后重新打开重试'
            return info

    def show_review(self, request):
        query = parse_qs(request.query)
        short = request.path.startswith(REVIEW_PREFIX)
        page = request.path if short else query.get('page', [''])[0]
        source = self.resolve_document(page)
        if short and source is None:
            self.send_error(404, 'Document not found')
            return
        if source is not None and not source.is_relative_to(self.content_root):
            info = self.register_document(source, page, query, warn=True)
            target = info['reviewContext']
            if 'catalogWarning' not in info and target != request.geturl():
                self.redirect(target)
                return
        self.send_content((APP / 'review.html').read_bytes(), 'text/html; charset=utf-8')

    def preview_document(self, query):
        page = query.get('page', [''])[0]
        source = self.resolve_document(page)
        if source is None:
            self.send_error(404, 'Document not found')
            return
        scope = self.document_scope(source, page, query)
        catalog = None if scope == self.content_root else self.server.reviews.catalog(scopes=(scope,))
        info = self.document_info(source, catalog, scope)
        if catalog is not None and page != info['page']:
            self.redirect(info['preview'])
            return
        template = Template((APP / 'preview.html').read_text(encoding='utf-8'))
        body = template.substitute(title=html.escape(source.name), source=html.escape(info['page']),
                                   directory=html.escape(info['directory'], quote=True))
        self.send_content(body.encode(), 'text/html; charset=utf-8')

    def browse_directory(self, url_path, query):
        root = self.content_root
        catalog = None
        if url_path.startswith(BROWSE_PREFIX):
            _, _, rest = url_path[len(BROWSE_PREFIX):].partition('/')
            key, _, relative = rest.partition('/')
            catalog = self.server.reviews.catalog()
            scope = self.scope_path(catalog, key)
            folder = self.scope_target(scope, unquote(relative))
        else:
            page = query.get('page', [''])[0]
            source = self.resolve_document(page)
            if page and source is None:
                self.send_error(404, 'Document not found')
                return
            scope = self.document_scope(source, page, query) if source is not None else root
            folder = (self.scope_target(scope, query['dir'][0]) if 'dir' in query
                      else source.parent if source is not None else scope)
            if folder is not None and folder.is_dir() and scope != root:
                catalog = self.server.reviews.catalog(scopes=(scope,))
                self.redirect(self.folder_url(folder, scope, catalog))
                return
        try:
            if folder is None or not folder.is_relative_to(scope):
                self.send_error(404, 'Directory not found')
                return
            children = list(folder.iterdir())
        except (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError):
            self.send_error(404, 'Directory not found')
            return
        except OSError:
            self.send_error(403, 'Cannot read directory')
            return

        if catalog is not None and url_path != self.folder_url(folder, scope, catalog):
            self.redirect(self.folder_url(folder, scope, catalog))
            return

        rows = []
        for child in children:
            if child.name.startswith('.'):
                continue
            try:
                target = child.resolve()
                if not target.is_relative_to(scope):
                    continue
                is_directory = target.is_dir()
                if not is_directory and (child.suffix.lower() not in DOC_SUFFIXES or not is_doc_file(target)):
                    continue
            except (OSError, ValueError, RuntimeError):
                continue
            name = html.escape(child.name)
            actions = ''
            if is_directory:
                label = '目录'
                link = html.escape(self.folder_url(target, scope, catalog), quote=True)
            else:
                label = 'MD' if target.suffix.lower() in ('.md', '.markdown') else 'HTML'
                info = self.document_info(target, catalog, scope)
                link = html.escape(info['preview'], quote=True)
                review_link = html.escape(info['reviewContext'], quote=True)
                actions = f'<a class="raw" href="{review_link}" aria-label="审查 {name}">审查</a>'
            row = (f'<li class="file-row"><span class="file-icon" aria-hidden="true">{label}</span>'
                   f'<div class="file-info"><a href="{link}">{name}</a></div>{actions}</li>')
            rows.append((not is_directory, child.name.casefold(), child.name, row))

        listing = ''.join(row for _, _, _, row in sorted(rows))
        parent = ''
        if folder != scope:
            href = html.escape(self.folder_url(folder.parent, scope, catalog), quote=True)
            parent = f'<a href="{href}">返回上层目录</a>'
        relative = '' if folder == scope else folder.relative_to(scope).as_posix()
        display_path = '/' + relative if scope == root else (project_label(scope) or 'standalone') + '/' + relative
        body = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>目录浏览 · Review Desk</title><link rel="stylesheet" href="/_preview/theme.css">'
                f'<nav class="topbar"><a href="/">所有方案</a>{parent}</nav>'
                f'<main class="library directory"><h1>目录浏览</h1><p class="muted">{html.escape(display_path)}</p>'
                f'<ul class="directory-list">{listing}</ul>'
                + ('' if rows else '<p class="empty">此目录没有子目录、Markdown 或 HTML 文件。</p>')
                + '</main></html>')
        self.send_content(body.encode(), 'text/html; charset=utf-8')

    def send_json(self, body, status=200):
        self.send_content(json.dumps(body, ensure_ascii=False).encode(), 'application/json; charset=utf-8', status=status)

    def review_request(self, action=None):
        query = parse_qs(urlsplit(self.path).query)
        page = action.get('page', '') if action else query.get('page', [''])[0]
        try:
            source = self.resolve_document(page)
            if source is None:
                self.send_error(404, 'Document not found')
                return
            result = self.server.reviews.transact(source, action)
            result.update(self.register_document(source, page, query, warn=True))
            self.send_json(result)
        except Conflict as exc:
            self.send_json({'error': str(exc)}, 409)
        except (ValueError, KeyError, TypeError) as exc:
            self.send_json({'error': '批注数据格式错误：' + str(exc)}, 400)
        except OSError:
            self.send_json({'error': '共享批注读写失败；草稿已保留'}, 500)

    def document_files(self):
        root = self.content_root
        sources = set()
        for candidate in root.rglob('*'):
            if candidate.suffix.lower() not in DOC_SUFFIXES:
                continue
            try:
                source = candidate.resolve()
                if source.is_relative_to(root) and is_doc_file(source):
                    sources.add(source)
            except (OSError, ValueError, RuntimeError):
                continue
        catalog = self.server.reviews.catalog(recover=True)
        sources.update(Path(path) for path in catalog['documents'] if Path(path).suffix.lower() in DOC_SUFFIXES)
        external = {source: project_directory(source) for source in sources if not source.is_relative_to(root)}
        catalog = self.server.reviews.catalog({source: document_slug(source) for source in external}, external.values())
        files = []
        for source in sources:
            available, modified = False, 0
            try:
                info = source.stat()
                available = stat.S_ISREG(info.st_mode) and os.access(source, os.R_OK)
                if available:
                    modified = info.st_mtime
            except OSError:
                pass
            details = self.document_info(source, catalog, external.get(source))
            files.append({'id': details['id'], 'name': details['name'], 'fileName': details['fileName'], 'url': details['page'],
                          'review': details['review'], 'preview': details['preview'],
                          'modified': modified, 'available': available,
                          'kind': 'Markdown' if source.suffix.lower() in ('.md', '.markdown') else 'HTML'})
        files.sort(key=lambda f: (not f['available'], -f['modified'], f['name']))
        return files

    def do_POST(self):
        if urlsplit(self.path).path != '/_preview/review':
            self.send_error(404)
            return
        try:
            action = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            if not isinstance(action, dict):
                raise ValueError()
        except (ValueError, TypeError):
            self.send_error(400, 'Invalid JSON')
            return
        self.review_request(action)

    def do_GET(self):
        request = urlsplit(self.path)
        try:
            self.get_route(request)
        except OSError:
            self.send_error(500, 'Cannot read or register document links')

    def get_route(self, request):
        path = request.path
        if path == '/_preview/review':
            self.review_request()
        elif path == '/_preview/view':
            self.preview_document(parse_qs(request.query))
        elif path == '/_browse' or path.startswith(BROWSE_PREFIX):
            self.browse_directory(path, parse_qs(request.query))
        elif path == '/_preview/files':
            try:
                files = self.document_files()
            except OSError:
                self.send_json({'error': '方案目录读写失败，请稍后刷新重试'}, 500)
                return
            self.send_json(files)
        elif path == '/_preview/document':
            page = parse_qs(urlsplit(self.path).query).get('page', [''])[0]
            source = self.resolve_document(page)
            if source is None:
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
            self.send_json({'revision': hashlib.sha256(raw).hexdigest(), 'html': content})
        elif path == '/_preview/locate':
            try:
                source = self.locate_source(parse_qs(request.query).get('path', [''])[0])
                if source is None:
                    self.send_error(404, 'Document not found')
                    return
                info = self.register_document(source)
            except OSError:
                self.send_json({'error': '方案列表登记失败，请稍后重试'}, 500)
                return
            self.send_json({key: info[key] for key in ('id', 'page', 'review')})
        elif path == '/_preview/theme.css':
            self.send_content((APP / 'theme.css').read_bytes(), 'text/css; charset=utf-8')
        elif path == '/_preview/mermaid.min.js':
            if not MERMAID_JS.is_file():
                self.send_error(404, 'Mermaid runtime not found')
                return
            self.send_content(MERMAID_JS.read_bytes(), 'text/javascript; charset=utf-8', cache='public, max-age=31536000, immutable')
        elif path.startswith(RESOURCE_PREFIX):
            catalog = self.server.reviews.catalog()
            source, scope = self.scoped_source(path, catalog)
            if source is None or not source.is_file():
                self.send_error(404, 'File not found')
                return
            self.send_local_file(source, self.folder_url(source.parent, scope, catalog))
        elif path == FS_PREFIX or path.startswith(FS_PREFIX + '/'):
            source = path_from_fs_url(path)
            try:
                exists = source is not None and source.is_file()
            except OSError:
                exists = False
            if not exists:
                self.send_error(404, 'File not found')
                return
            self.send_local_file(source)
        elif path == '/_review' or path.startswith(REVIEW_PREFIX):
            self.show_review(request)
        elif Path(path).suffix.lower() in ('.md', '.markdown') and 'raw' not in parse_qs(request.query):
            root = Path(self.directory).resolve()
            source = Path(self.translate_path(self.path)).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                self.send_error(404, 'Markdown file not found')
                return
            self.send_markdown(source)
        elif path == '/':
            self.send_content((APP / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        else:
            super().do_GET()

    def do_HEAD(self):
        self.do_GET()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8088)
    parser.add_argument('--state-directory', default=str(APP / 'data'), help='共享批注持久化目录（默认安装目录下 data）')
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.bind, args.port), partial(Handler, directory=args.directory))
    server.reviews = ReviewStore(args.state_directory)
    print(f'Review Desk: http://{args.bind}:{server.server_port}', flush=True)
    server.serve_forever()
