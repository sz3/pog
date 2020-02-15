from collections import defaultdict
from os import environ, path
from subprocess import PIPE, Popen

POG_ROOT = path.abspath(path.join(path.dirname(path.realpath(__file__)), '..'))


class PogCli():
    def __init__(self, config=None, kwargs=None, pog_cmd=None):
        self.cmd = pog_cmd or ['python', '-m', 'pog.pog']
        self.config = config or {}
        self.kwargs = kwargs or {}

    def set_keyfiles(self, keyfiles):
        for k in ('keyfile', 'decryption-keyfile', 'encryption-keyfile'):
            self.config.pop(k, None)

        if not keyfiles:
            return

        for f in keyfiles:
            if f.endswith('.decrypt'):
                self.config['decryption-keyfile'] = f
                return

        for f in keyfiles:
            if f.endswith('.encrypt'):
                self.config['encryption-keyfile'] = f
                return

        for f in keyfiles:
            self.config['keyfile'] = f
            return

    def run(self, *args, **kwargs):
        full_args = list(self.cmd) + list(args) + self._flatten_config()
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

    def run_command(self, *args, **kwargs):
        return list(self.run(*args, **kwargs))

    def _flatten_config(self):
        return ['--{}={}'.format(k, v) for k, v in self.config.items()]

    def dumpManifest(self, mfn):
        info = defaultdict(list)
        current_file = ''
        for line in self.run_command('--dump-manifest', mfn):
            if line.startswith('***'):
                continue
            if line.startswith('*'):
                current_file = line[2:-1]
            else:
                info[current_file].append(line)
        return dict(info)

    def dumpManifestIndex(self, mfn):
        yield from self.run('--dump-manifest-index', mfn)

    def decrypt(self, mfn, **kwargs):
        yield from self.run('--decrypt', mfn, **kwargs)
