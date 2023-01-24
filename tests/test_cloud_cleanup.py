from os import environ
from unittest import TestCase, skipUnless

from .helpers import TestDirMixin, POG_ROOT
from pog.fs.localfs import localfs


class CloudCleanupTest(TestDirMixin, TestCase):
    script = 'pog.cloud_cleanup'
    keyfile_flag = f'--encrypt={POG_ROOT}/tests/samples/only_for_testing.encrypt'

    consistency_mfn = 'asymmetric-sample.mfn'
    consistency_blobname = 'iJLSTgfMViGx4QOmQ3-ZAho_6ZGyjhc76Y2gMRz9QQU='

    def setUp(self):
        super().setUp()

        # put some stuff in our working directory
        self.fs = localfs(root=self.working_dir.name)
        self.fs.upload_file(f'{POG_ROOT}/tests/samples/{self.consistency_blobname}', f'data/{self.consistency_blobname}')
        self.fs.upload_file(f'{POG_ROOT}/tests/samples/{self.consistency_blobname}', 'data/uselessblob')

    def test_cleanup_dryrun(self):
        # make a file:/// repo for us to blow up
        for i in range(4):
            self.fs.upload_file(f'{POG_ROOT}/tests/samples/{self.consistency_mfn}', f'aa-2021-01-1{i}T00:55.mfn')

        res = self.run_command(self.keyfile_flag, '--backup=local')
        self.assertIn('would remove aa-2021-01-11T00:55.mfn', res)

        self.assertEqual(self.fs.list_files(recursive=True), [
            f'{self.working_dir.name}/aa-2021-01-10T00:55.mfn',
            f'{self.working_dir.name}/aa-2021-01-11T00:55.mfn',
            f'{self.working_dir.name}/aa-2021-01-12T00:55.mfn',
            f'{self.working_dir.name}/aa-2021-01-13T00:55.mfn',
            f'{self.working_dir.name}/data/',
            f'{self.working_dir.name}/data/{self.consistency_blobname}',
            f'{self.working_dir.name}/data/uselessblob',
        ])

    @skipUnless(environ.get('DANGER'), 'dangerous test skipped unless DANGER=1')
    def test_cleanup_for_real(self):
        # make a file:/// repo for us to blow up
        for i in range(4):
            self.fs.upload_file(f'{POG_ROOT}/tests/samples/{self.consistency_mfn}', f'aa-2021-01-1{i}T00:55.mfn')

        res = self.run_command(self.keyfile_flag, '--backup=local', '--reckless-abandon')
        self.assertIn('would remove aa-2021-01-11T00:55.mfn', res)

        self.assertEqual(self.fs.list_files(recursive=True), [
            f'{self.working_dir.name}/aa-2021-01-13T00:55.mfn',
            f'{self.working_dir.name}/data/',
            f'{self.working_dir.name}/data/{self.consistency_blobname}',
        ])

    def test_cleanup_similarity_dryrun(self):
        # make a file:/// repo for us to blow up
        for i in range(4):
            self.fs.upload_file(f'{POG_ROOT}/tests/samples/{self.consistency_mfn}', f'{i}.mfn')

        res = self.run_command(self.keyfile_flag, '--backup=local', '--exp-similarity-check')
        self.assertIn('would remove 0.mfn (similarity)', res)

        self.assertEqual(self.fs.list_files(recursive=True), [
            f'{self.working_dir.name}/0.mfn',
            f'{self.working_dir.name}/1.mfn',
            f'{self.working_dir.name}/2.mfn',
            f'{self.working_dir.name}/3.mfn',
            f'{self.working_dir.name}/data/',
            f'{self.working_dir.name}/data/{self.consistency_blobname}',
            f'{self.working_dir.name}/data/uselessblob',
        ])

    @skipUnless(environ.get('DANGER'), 'dangerous test skipped unless DANGER=1')
    def test_cleanup_similarity_for_real(self):
        # make a file:/// repo for us to blow up
        for i in range(4):
            self.fs.upload_file(f'{POG_ROOT}/tests/samples/{self.consistency_mfn}', f'{i}.mfn')

        res = self.run_command(self.keyfile_flag, '--backup=local', '--exp-similarity-check', '--reckless-abandon')
        self.assertIn('would remove 0.mfn (similarity)', res)

        self.assertEqual(self.fs.list_files(recursive=True), [
            f'{self.working_dir.name}/3.mfn',
            f'{self.working_dir.name}/data/',
            f'{self.working_dir.name}/data/{self.consistency_blobname}',
        ])
