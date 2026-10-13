import json
import os
from pathlib import Path


class Preferences:
    def __init__(self, directory=None):
        root = Path(directory) if directory else Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'complexweeper'
        self.path = root/'preferences.json'
        self.data = {'sound': True, 'zoom': 2, 'scores': {}}
        self.error = None
        try:
            loaded = json.loads(self.path.read_text())
            if isinstance(loaded, dict):
                if type(loaded.get('sound')) is bool:
                    self.data['sound'] = loaded['sound']
                if type(loaded.get('zoom')) is int and loaded['zoom'] in (1, 2, 3):
                    self.data['zoom'] = loaded['zoom']
                if isinstance(loaded.get('scores'), dict):
                    self.data['scores'] = {k: v for k, v in loaded['scores'].items()
                                           if k in [f'{m}:{p}' for m in (0, 1) for p in range(3)]
                                           and type(v) is int and 0 <= v <= 9999}
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_name(f'.preferences.{os.getpid()}.tmp')
            temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2)+'\n')
            temp.replace(self.path)
            self.error = None
            return True
        except OSError as e:
            self.error = str(e)
            return False

    def best(self, mode, preset):
        return self.data['scores'].get(f'{mode}:{preset}')

    def record(self, mode, preset, seconds):
        key = f'{mode}:{preset}'
        old = self.data['scores'].get(key)
        if old is None or seconds < old:
            self.data['scores'][key] = seconds
            self.save()
            return True
        return False
