from os import environ, path, utime
from subprocess import check_output, call as subprocess_call
from tempfile import TemporaryDirectory

POG_ROOT = path.abspath(path.join(path.dirname(path.realpath(__file__)), '..'))
SAMPLE_TIME1 = 1552604385.2789645
SAMPLE_TIME2 = 1358637058.0


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
        super().setUp()

    def tearDown(self):
        super().tearDown()
        with self.input_dir, self.working_dir:
            pass

    def run_command(self, *args, **kwargs):
        full_args = ['python', '-m', 'pog.pog'] + list(args)

        env = kwargs.get('env', dict(environ))
        env['PYTHONPATH'] = POG_ROOT
        kwargs['env'] = env

        if kwargs.get('stdout'):
            return subprocess_call(full_args, cwd=self.working_dir.name, **kwargs)

        return check_output(full_args, cwd=self.working_dir.name, **kwargs).strip().decode('utf-8').split('\n')