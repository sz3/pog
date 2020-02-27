from collections import defaultdict
from os import environ, path
from subprocess import PIPE, Popen

POG_ROOT = path.abspath(path.join(path.dirname(path.realpath(__file__)), '..'))


class PogCli():
    def __init__(self, config=None, kwargs=None, pog_cmd=None):
        self.cmd = pog_cmd or ['python', '-u', '-m', 'pog.pog']
        self.config = config or {}
        self.kwargs = kwargs or {}
        self._abort = False

    def abort(self):
        self._abort = True

    def set_keyfiles(self, *keyfiles):
        for k in ('keyfile', 'decryption-keyfile', 'encryption-keyfile'):
            self.config.pop(k, None)

        for f in keyfiles:
            if f.endswith('.decrypt'):
                self.config['decryption-keyfile'] = f

        for f in keyfiles:
            if f.endswith('.encrypt'):
                self.config['encryption-keyfile'] = f

        for k in ('decryption-keyfile', 'encryption-keyfile'):
            if k in self.config:
                return

        for f in keyfiles:
            self.config['keyfile'] = f
            return

    def run(self, *args, **kwargs):
        self._abort = False
        restrict_config = kwargs.pop('restrict_config', ['encryption-keyfile'])
        full_args = list(self.cmd) + list(args) + self._flatten_config(restrict_config)
        kwargs = {**self.kwargs, **kwargs}

        env = kwargs.get('env', dict(environ))
        env['PYTHONPATH'] = POG_ROOT
        kwargs['env'] = env

        if 'stdout' not in kwargs:
            kwargs['stdout'] = PIPE

        with Popen(full_args, **kwargs) as proc:
            if kwargs['stdout'] == PIPE:
                for line in proc.stdout:
                    yield line.decode('utf-8').strip()
                    if self._abort:
                        proc.terminate()
                        break

    def run_command(self, *args, **kwargs):
        return list(self.run(*args, **kwargs))

    def _flatten_config(self, restrict_config=None):
        restrict_config = restrict_config or []
        config = self.config.copy()
        for key in restrict_config:
            config.pop(key, None)
        return ['--{}={}'.format(k, v) for k, v in config.items()]

    def dumpManifest(self, mfn):
        info = defaultdict(list)
        current_file = ''
        for line in self.run_command('--dump-manifest', mfn):
            if line.startswith('*** '):
                continue
            if line.startswith('* '):
                current_file = line[2:-1]
            else:
                info[current_file].append(line)
        return dict(info)

    def dumpManifestIndex(self, mfn):
        kwargs = {}
        if 'decryption-keyfile' not in self.config and 'encryption-keyfile' in self.config:
            kwargs['restrict_config'] = []
        yield from self.run('--dump-manifest-index', mfn, **kwargs)

    def _progress_from_line(self, line):
        if not line.startswith('*** '):
            return None
        progress, filename = line[4:].split(':', 1)
        current, total = progress.split('/')
        return {'current': int(current), 'total': int(total), 'filename': filename.strip()}

    def decrypt(self, mfn, **kwargs):
        for line in self.run('--decrypt', mfn, **kwargs):
            progress = self._progress_from_line(line)
            if progress:
                yield progress

    def encrypt(self, inputs, destinations, **kwargs):
        kwargs['restrict_config'] = ['decryption-keyfile']
        save_to = '--save-to=' + ','.join(destinations)
        for line in self.run(save_to, *inputs, **kwargs):
            progress = self._progress_from_line(line)
            if progress:
                yield progress
