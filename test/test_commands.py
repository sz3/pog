import hashlib
import random
from glob import glob
from os import environ, path, mkdir, listdir
from shutil import copyfile
from subprocess import check_output, call as subprocess_call
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless


CODE_DIR = path.abspath(path.join(path.dirname(path.realpath(__file__)), '..'))

SAMPLE_TEXT = b'''069:15:22 Lovell (onboard): Hey, I don't see a thing. Where are we?
069:15:24 Anders (onboard): It looks like a big - looks like a big beach down there.
'''


def compute_checksum(filename):
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


class TestDirMixin():
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        mkdir(path.join(self.temp_dir.name, 'inputs'))
        self.tiny_sample = path.join(self.temp_dir.name, 'inputs', 'tiny_sample.txt')
        with open(self.tiny_sample, 'wb') as f:
            f.write(b'aaaabbbb')
        super().setUp()

    def tearDown(self):
        super().tearDown()
        with self.temp_dir:
            pass

    def _write_big_sample(self):
        # idea is to deterministically generate a poorly-compressable stream.
        # we'll rely on a constant random.seed() until python decides to change the impl
        self.big_sample = path.join(self.temp_dir.name, 'inputs', 'big_sample.bin')
        hash_md5 = hashlib.md5()

        with open(self.big_sample, 'wb') as f:
            random.seed(1234)
            remaining_size = 110000000  # ~110 MB ... default chunk size is 100MB
            chunk_size = 100000
            while remaining_size > 0:
                chunk = bytearray(random.getrandbits(8) for _ in range(chunk_size))
                f.write(chunk)
                hash_md5.update(chunk)
                remaining_size -= chunk_size

        return hash_md5.hexdigest()

    def run_command(self, *args, **kwargs):
        full_args = ['python', f'{CODE_DIR}/pog.py'] + list(args)

        if kwargs.get('stdout'):
            return subprocess_call(full_args, cwd=self.temp_dir.name, **kwargs)

        return check_output(full_args, cwd=self.temp_dir.name, **kwargs).strip().decode('utf-8').split('\n')


class KeyfileTest(TestDirMixin, TestCase):
    def test_round_trip(self):
        # encrypt our sample file
        enc = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', self.tiny_sample)
        self.assertEqual(enc, ['Fx1xB8L8L1cRPdBzkr-L8mzPusnzEBjhrQseB3DaCU4='])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.temp_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # check the index as well
        show_mfn_index = self.run_command(
            f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--dump-manifest-index', manifest_name
        )
        self.assertEqual(show_mfn_index, enc)

        # check that we have what we want for decryption
        paths = sorted(listdir(self.temp_dir.name))
        self.assertEqual(paths, [path.basename(manifest_name)] + enc + ['inputs'])

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

        # check that the directory looks good
        paths = sorted(listdir(self.temp_dir.name))
        self.assertEqual(paths, ['inputs', 'tiny_sample.txt'])

        # read the decrypted file
        with open(path.join(self.temp_dir.name, 'tiny_sample.txt')) as f:
            contents = f.read()
        self.assertEqual(contents, 'aaaabbbb')

        # validate the directory looks like we expect it to
        paths = sorted(listdir(self.temp_dir.name))
        self.assertEqual(paths, ['inputs', 'tiny_sample.txt'])

    @skipUnless(environ.get('CI'), 'long test skipped unless CI=1')
    def test_multiple_chunks(self):
        expected_checksum = self._write_big_sample()

        # encrypt our sample file
        enc = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', self.big_sample)
        self.assertEqual(
            enc, [
                'RiOpsEQbQpxrBvXL1s047hq54EhFXxWqwag-vMuiRfc=',
                'YdK86P4e2191CxVBhZwvvPtwOLU6Ve1NzMhwLjxVXqg=',
            ]
        )

        # check that the manifest looks good
        manifest_name = glob(path.join(self.temp_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

         # check that the directory looks good
        paths = sorted(listdir(self.temp_dir.name))
        self.assertEqual(paths, ['big_sample.bin', 'inputs'])

        # check that the output file is what we expect
        filename = path.join(self.temp_dir.name, 'big_sample.bin')
        actual_checksum = compute_checksum(filename)
        self.assertEqual(expected_checksum, actual_checksum)

    def test_consistency(self):
        # regression test for our header/encryption format -- try to decrypt a known file
        with open(path.join(self.temp_dir.name, 'out.txt'), 'wb') as f:
            dec = self.run_command(
                f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--decrypt',
                f'{CODE_DIR}/test/samples/US-1DnY1AVF1huiGj10G9SEGwCHa4GVxJcBnaCuAcXk=', stdout=f
            )
            self.assertEqual(dec, 0)

        # read the decrypted file
        with open(path.join(self.temp_dir.name, 'out.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)

    def test_consistency_with_manifest(self):
        # regression test with manifest as well
        # copy over relevant files first
        for filename in ['US-1DnY1AVF1huiGj10G9SEGwCHa4GVxJcBnaCuAcXk=', 'keyfile-sample.mfn']:
            copyfile(f'{CODE_DIR}/test/samples/{filename}', f'{self.temp_dir.name}/{filename}')

        dec = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--decrypt', '--consume',
                               'keyfile-sample.mfn')
        self.assertEqual(dec, [''])

        # read the decrypted file
        with open(path.join(self.temp_dir.name, '8.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)


class AsymmetricCryptoTest(TestDirMixin, TestCase):
    def test_asymmetric_round_trip(self):
        # encrypt our sample file
        enc = self.run_command(f'--encryption-keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', self.tiny_sample)
        self.assertEqual(enc, ['p6VsgAeMwIwCGbnuZ7lZqRPX-Ur0pT3nwsoKX2mp3Bo='])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.temp_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(
            f'--decryption-keyfile={CODE_DIR}/test/samples/only_for_testing.decrypt', '--dump-manifest', manifest_name
        )
        self.assertEqual(show_mfn, enc)

        # check the index as well
        show_mfn_index = self.run_command(
            f'--encryption-keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--dump-manifest-index', manifest_name
        )
        self.assertEqual(show_mfn_index, enc)

        # check that we have what we want for decryption
        paths = sorted(listdir(self.temp_dir.name))
        self.assertEqual(paths, [path.basename(manifest_name), 'inputs'] + enc)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--decryption-keyfile={CODE_DIR}/test/samples/only_for_testing.decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

        # check that the directory looks good
        paths = sorted(listdir(self.temp_dir.name))
        self.assertEqual(paths, ['inputs', 'tiny_sample.txt'])

        # read the decrypted file
        with open(path.join(self.temp_dir.name, 'tiny_sample.txt')) as f:
            contents = f.read()
        self.assertEqual(contents, 'aaaabbbb')

        # validate the directory looks like we expect it to
        paths = sorted(listdir(self.temp_dir.name))
        self.assertEqual(paths, ['inputs', 'tiny_sample.txt'])

    def test_consistency(self):
        # regression test for our header/encryption format -- try to decrypt a known file
        with open(path.join(self.temp_dir.name, 'out.txt'), 'wb') as f:
            dec = self.run_command(
                f'--decryption-keyfile={CODE_DIR}/test/samples/only_for_testing.decrypt',
                f'{CODE_DIR}/test/samples/hq3mhX2mG_i_aVy2wv6jMGC5DjlerpvJ8O1Y_iayfPY=', stdout=f)
            self.assertEqual(dec, 0)

        # read the decrypted file
        with open(path.join(self.temp_dir.name, 'out.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)

    def test_consistency_with_manifest(self):
        # regression test with manifest as well
        # copy over relevant files first
        for filename in ['hq3mhX2mG_i_aVy2wv6jMGC5DjlerpvJ8O1Y_iayfPY=', 'asymmetric-sample.mfn']:
            copyfile(f'{CODE_DIR}/test/samples/{filename}', f'{self.temp_dir.name}/{filename}')

        dec = self.run_command(
            f'--decryption-keyfile={CODE_DIR}/test/samples/only_for_testing.decrypt', '--consume', 'asymmetric-sample.mfn'
        )
        self.assertEqual(dec, [''])

        # read the decrypted file
        with open(path.join(self.temp_dir.name, '8.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)
