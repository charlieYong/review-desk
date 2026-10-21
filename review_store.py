"""单服务的共享批注：按真实文件路径存储，用锁与原子替换提交操作。"""
import copy
import hashlib
import json
import os
import threading
import time
from pathlib import Path


class Conflict(Exception):
    pass


class ReviewStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.lock = threading.Lock()

    def transact(self, source, action=None):
        document_id = str(source.resolve())
        filename = self.directory / (hashlib.sha256(document_id.encode()).hexdigest() + '.json')
        with self.lock:
            created = not filename.exists()
            if not created:
                try:
                    data = json.loads(filename.read_text(encoding='utf-8'))
                except (ValueError, UnicodeError) as exc:
                    raise OSError('共享批注文件无法读取') from exc
            else:
                revision = hashlib.sha256(source.read_bytes()).hexdigest()
                data = {'documentId': document_id, 'version': 0, 'imports': [],
                        'state': {'round': 1, 'revision': revision, 'entries': [], 'archives': []}}
            changed = created
            if action is not None:
                previous = copy.deepcopy(data)
                self.apply(data, action, source)
                if data != previous:
                    data['version'] += 1
                    changed = True
            if changed:
                self.directory.mkdir(parents=True, exist_ok=True)
                temporary = filename.with_suffix('.tmp')
                try:
                    with temporary.open('w', encoding='utf-8') as stream:
                        json.dump(data, stream, ensure_ascii=False)
                        stream.flush()
                        os.fsync(stream.fileno())
                    temporary.replace(filename)
                finally:
                    temporary.unlink(missing_ok=True)
            return {k: copy.deepcopy(data[k]) for k in ('documentId', 'version', 'state')}

    def apply(self, data, action, source):
        state = data['state']
        kind = action['action']
        if kind == 'import':
            self.import_local(data, action['legacy'])
            return
        if action.get('round') != state['round'] or action.get('revision') != state['revision']:
            raise Conflict('审查轮次已变化，请核对共享状态后重试；草稿已保留')
        entries = state['entries']
        if kind == 'add':
            entry = action['entry']
            self.validate_entry(entry)
            previous = next((e for e in entries if e['id'] == entry['id']), None)
            if previous is not None:
                if previous != entry:
                    raise Conflict('批注已变化，请刷新核对')
            else:
                entries.append(entry)
        elif kind in ('edit', 'delete', 'resolve'):
            if kind == 'resolve':
                archive = next((a for a in state['archives'] if a['round'] == action['archiveRound']
                                and a['revision'] == action['archiveRevision']), None)
                entries = archive['entries'] if archive else []
            previous = action['expected']
            index = next((i for i, e in enumerate(entries) if e['id'] == previous['id']), None)
            if index is None or entries[index] != previous:
                raise Conflict('该批注已被其他客户端修改或删除，请核对后重试；草稿已保留')
            if kind == 'delete':
                entries.pop(index)
            elif kind == 'resolve':
                entries[index]['resolved'] = not previous.get('resolved', False)
            else:
                self.validate_entry(action['entry'])
                if action['entry']['id'] != previous['id']:
                    raise ValueError('批注 ID 不一致')
                entries[index] = action['entry']
        elif kind == 'next':
            revision = hashlib.sha256(source.read_bytes()).hexdigest()
            if revision == state['revision']:
                raise Conflict('文档内容未变化')
            state['archives'].append({'round': state['round'], 'revision': state['revision'],
                                      'archivedAt': int(time.time() * 1000), 'entries': entries})
            state.update(round=state['round'] + 1, revision=revision, entries=[])
        else:
            raise ValueError('未知批注操作')

    @staticmethod
    def validate_entry(entry):
        if not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) for k in ('id', 'quote', 'note')):
            raise ValueError('批注格式错误')
        if not entry['id'] or not entry['note'].strip():
            raise ValueError('批注内容不能为空')

    def import_local(self, data, legacy):
        """保留旧快照；相同快照仅导入一次，异版意见归档而不覆盖共享轮次。"""
        signature = hashlib.sha256(json.dumps(legacy, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if signature in data['imports']:
            return
        state = data['state']
        if isinstance(legacy, list):
            legacy = {'round': 1, 'revision': state['revision'], 'entries': legacy, 'archives': []}
        legacy = copy.deepcopy(legacy)
        legacy.setdefault('round', 1)
        legacy['revision'] = legacy.get('revision') or state['revision']
        legacy.setdefault('entries', [])
        legacy.setdefault('archives', [])
        for group in [legacy, *legacy['archives']]:
            for entry in group['entries']:
                self.validate_entry(entry)
                # 同一意见跨旧入口重复出现时去重，内容不同的旧意见分别保留。
                entry['id'] = 'local-' + hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if data['version'] == 0:
            state.update(round=legacy['round'], revision=legacy['revision'])
        for group in [*legacy['archives'], legacy]:
            if (group['round'], group['revision']) == (state['round'], state['revision']):
                target = state
            else:
                target = next((a for a in state['archives'] if (a['round'], a['revision']) ==
                               (group['round'], group['revision'])), None)
                if target is None:
                    target = {**group, 'entries': [], 'archivedAt': group.get('archivedAt', int(time.time() * 1000))}
                    state['archives'].append(target)
            ids = {e['id'] for e in target['entries']}
            target['entries'].extend(e for e in group['entries'] if e['id'] not in ids)
        data['imports'].append(signature)
