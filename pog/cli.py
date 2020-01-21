from collections import defaultdict
from os import environ, path
from subprocess import check_output, call as subprocess_call, STDOUT

POG_ROOT = path.abspath(path.join(path.dirname(path.realpath(__file__)), '..'))


class PogCli():
    def __init__(self, config=None):
        self.config = config or {}

    def set_keyfiles(self, keyfiles):
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

    def _run_command(self, *args, **kwargs):
        args = list(args) + self._flatten_config()
        full_args = ['python', '-m', 'pog.pog'] + list(args)

        env = kwargs.get('env', dict(environ))
        env['PYTHONPATH'] = POG_ROOT
        kwargs['env'] = env

        if kwargs.get('stdout'):
            return subprocess_call(full_args, **kwargs)

        return check_output(full_args, stderr=STDOUT, **kwargs).strip().decode('utf-8').split('\n')

    def _flatten_config(self):
        return ['--{}={}'.format(k, v) for k,v in self.config.items()]

    def dumpManifest(self, mfn):
        info = defaultdict(list)
        current_file = ''
        for line in self._run_command('--dump-manifest', mfn):
            if line.startswith('***'):
                continue
            if line.startswith('*'):
                current_file = line[2:-1]
            else:
                info[current_file].append(line)
        return dict(info)

    def dumpManifestIndex(self, mfn):
        yield from self._run_command('--dump-manifest-index', mfn)
