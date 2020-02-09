from os import environ
from unittest import TestCase, skipUnless

from .helpers import TestDirMixin, POG_ROOT
from pog.fs.localfs import localfs


class CloudCleanupTest(TestDirMixin, TestCase):
    script = 'pog.cloud_cleanup'
    keyfile_flag = f'--keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt'

    consistency_mfn = 'keyfile-sample.mfn'
    consistency_blobname = 'US-1DnY1AVF1huiGj10G9SEGwCHa4GVxJcBnaCuAcXk='

    def setUp(self):
        super().setUp()

        # put some stuff in our working directory
        self.fs = localfs(root=self.working_dir.name)
        for i in range(4):
            self.fs.upload_file(f'{POG_ROOT}/tests/samples/{self.consistency_mfn}', f'{i}.mfn')

        self.fs.upload_file(f'{POG_ROOT}/tests/samples/{self.consistency_blobname}', f'data/{self.consistency_blobname}')
        self.fs.upload_file(f'{POG_ROOT}/tests/samples/{self.consistency_blobname}', 'data/uselessblob')

    def test_cleanup_dryrun(self):
        # make a file:/// repo for us to blow up
        res = self.run_command(self.keyfile_flag, '--backup=local')
        self.assertIn('would remove 0.mfn', res)

        self.assertEqual(self.fs.list_files(recursive=True), [
            f'{self.working_dir.name}/0.mfn',
            f'{self.working_dir.name}/1.mfn',
            f'{self.working_dir.name}/2.mfn',
            f'{self.working_dir.name}/3.mfn',
            f'{self.working_dir.name}/data/',
            f'{self.working_dir.name}/data/US-1DnY1AVF1huiGj10G9SEGwCHa4GVxJcBnaCuAcXk=',
            f'{self.working_dir.name}/data/uselessblob',
        ])

    @skipUnless(environ.get('DANGER'), 'dangerous test skipped unless DANGER=1')
    def test_cleanup_for_real(self):
        # make a file:/// repo for us to blow up
        res = self.run_command(self.keyfile_flag, '--backup=local', '--reckless-abandon')
        self.assertIn('would remove 0.mfn', res)

        self.assertEqual(self.fs.list_files(recursive=True), [
            f'{self.working_dir.name}/3.mfn',
            f'{self.working_dir.name}/data/',
            f'{self.working_dir.name}/data/US-1DnY1AVF1huiGj10G9SEGwCHa4GVxJcBnaCuAcXk=',
        ])
