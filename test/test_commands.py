from glob import glob
from os import path, mkdir, listdir
from subprocess import check_output
from tempfile import TemporaryDirectory
from unittest import TestCase


CODE_DIR = path.abspath(path.join(path.dirname(path.realpath(__file__)), '..'))


class TestDirMixin():
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        mkdir(path.join(self.temp_dir.name, 'inputs'))
        self.sample = path.join(self.temp_dir.name, 'inputs', 'sample.txt')
        with open(self.sample, 'wb') as f:
            f.write(b'aaaabbbb')
        super().setUp()

    def tearDown(self):
        super().tearDown()
        with self.temp_dir:
            pass

    def run_command(self, *args):
        full_args = ['python', f'{CODE_DIR}/pog.py'] + list(args)
        return check_output(full_args, cwd=self.temp_dir.name).strip().decode('utf-8').split('\n')


class KeyfileTest(TestDirMixin, TestCase):
    def test_round_trip(self):
        # encrypt our sample file
        enc = self.run_command(f'--keyfile={CODE_DIR}/test/only_for_testing.encrypt', self.sample)
        self.assertEqual(enc, ['Fx1xB8L8L1cRPdBzkr-L8mzPusnzEBjhrQseB3DaCU4='])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.temp_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--keyfile={CODE_DIR}/test/only_for_testing.encrypt', '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # check the index as well
        show_mfn_index = self.run_command(f'--keyfile={CODE_DIR}/test/only_for_testing.encrypt', '--dump-manifest-index', manifest_name)
        self.assertEqual(show_mfn_index, enc)

        # check that we have what we want for decryption
        paths = sorted(listdir(self.temp_dir.name))
        self.assertEqual(paths, [path.basename(manifest_name)] + enc + ['inputs'])

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--keyfile={CODE_DIR}/test/only_for_testing.encrypt', '--decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

        # read the decrypted file
        with open(path.join(self.temp_dir.name, 'sample.txt')) as f:
            contents = f.read()
        self.assertEqual(contents, 'aaaabbbb')

        # validate the directory looks like we expect it to
        paths = sorted(listdir(self.temp_dir.name))
        self.assertEqual(paths, ['inputs', 'sample.txt'])


class AsymmetricCryptoTest(TestDirMixin, TestCase):
    def test_asymmetric_round_trip(self):
        # encrypt our sample file
        enc = self.run_command(f'--encryption-keyfile={CODE_DIR}/test/only_for_testing.encrypt', self.sample)
        self.assertEqual(enc, ['p6VsgAeMwIwCGbnuZ7lZqRPX-Ur0pT3nwsoKX2mp3Bo='])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.temp_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--decryption-keyfile={CODE_DIR}/test/only_for_testing.decrypt', '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # check the index as well
        show_mfn_index = self.run_command(f'--encryption-keyfile={CODE_DIR}/test/only_for_testing.encrypt', '--dump-manifest-index', manifest_name)
        self.assertEqual(show_mfn_index, enc)

        # check that we have what we want for decryption
        paths = sorted(listdir(self.temp_dir.name))
        self.assertEqual(paths, [path.basename(manifest_name), 'inputs'] + enc)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--decryption-keyfile={CODE_DIR}/test/only_for_testing.decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

        # read the decrypted file
        with open(path.join(self.temp_dir.name, 'sample.txt')) as f:
            contents = f.read()
        self.assertEqual(contents, 'aaaabbbb')

        # validate the directory looks like we expect it to
        paths = sorted(listdir(self.temp_dir.name))
        self.assertEqual(paths, ['inputs', 'sample.txt'])
