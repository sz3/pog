from os import environ, path, utime
from tempfile import TemporaryDirectory

from pog.cli import PogCli

POG_ROOT = path.abspath(path.join(path.dirname(path.realpath(__file__)), '..'))
SAMPLE_TIME1 = 1552604385.2789645
SAMPLE_TIME2 = 1358637058.0


def _program_args():
    if 'coverage' in environ.get('_', ''):
        return ['coverage', 'run', '--rcfile', f'{POG_ROOT}/.coveragerc2', '-a', '-m', 'pog.pog']
    else:
        return ['python', '-m', 'pog.pog']


class TestDirMixin():
    def setUp(self):
        self.input_dir = TemporaryDirectory()

        self.tiny_sample = path.join(self.input_dir.name, 'tiny_sample.txt')
        with open(self.tiny_sample, 'wb') as f:
            f.write(b'aaaabbbb')
        utime(self.tiny_sample, times=(SAMPLE_TIME1, SAMPLE_TIME1))

        self.another_sample = path.join(self.input_dir.name, 'another_sample.txt')
        with open(self.another_sample, 'wb') as f:
            f.write(b'0123456789')
        utime(self.another_sample, times=(SAMPLE_TIME2, SAMPLE_TIME2))

        self.working_dir = TemporaryDirectory()
        self.cli = PogCli(_program_args())
        super().setUp()

    def tearDown(self):
        super().tearDown()
        with self.input_dir, self.working_dir:
            pass

    def run_command(self, *args, **kwargs):
        kwargs['cwd'] = self.working_dir.name
        return self.cli.run_command(*args, **kwargs)
