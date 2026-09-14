"""Small per-window cache; immutable FAC results, invalidated by file version."""
from collections import OrderedDict
from dataclasses import replace


class FACAnalysisCache:
    def __init__(self):
        self.entries = OrderedDict()

    @staticmethod
    def _read(path, reader):
        result = reader([path])
        return replace(result, issues=tuple(replace(issue, source_path=str(path)) for issue in result.issues))

    def read(self, paths, reader):
        parts = []
        for path in paths:
            try:
                stat = path.stat()
                key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
            except OSError:
                parts.append(self._read(path, reader))
                continue
            part = self.entries.get(key)
            if part is None:
                part = self._read(path, reader)
                after = path.stat()
                if (after.st_size, after.st_mtime_ns) != key[1:]:
                    raise ValueError(f'El archivo cambió durante su lectura: {path.name}')
                if len(part.records) <= 5000:
                    self.entries[key] = part
                    while len(self.entries) > 8:
                        self.entries.popitem(last=False)
            else:
                self.entries.move_to_end(key)
            parts.append(part)
        if not parts:
            return reader([])
        records = tuple(record for part in parts for record in part.records)
        issues = tuple(issue for part in parts for issue in part.issues if issue.code != 'FAC_NO_SELECTED_RECORDS')
        if not records and not issues:
            issues = reader([]).issues
        return type(parts[0])(records, sum(part.ignored_empty_rows for part in parts),
                              sum(part.excluded_no_rows for part in parts), issues)
