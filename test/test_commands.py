import hashlib
import random
from glob import glob
from os import environ, path, listdir
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


def make_big_file(filename):
    # idea is to deterministically generate a poorly-compressable stream.
    # we'll rely on a constant random.seed() until python decides to change the impl
    hash_md5 = hashlib.md5()

    with open(filename, 'wb') as f:
        random.seed(1234)
        remaining_size = 110000000  # ~110 MB ... default chunk size is 100MB
        chunk_size = 100000
        while remaining_size > 0:
            chunk = bytearray(random.getrandbits(8) for _ in range(chunk_size))
            f.write(chunk)
            hash_md5.update(chunk)
            remaining_size -= chunk_size

    return hash_md5.hexdigest()


class TestDirMixin():
    def setUp(self):
        self.input_dir = TemporaryDirectory()
        self.tiny_sample = path.join(self.input_dir.name, 'tiny_sample.txt')
        with open(self.tiny_sample, 'wb') as f:
            f.write(b'aaaabbbb')

        self.another_sample = path.join(self.input_dir.name, 'another_sample.txt')
        with open(self.another_sample, 'wb') as f:
            f.write(b'0123456789')

        self.working_dir = TemporaryDirectory()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        with self.input_dir, self.working_dir:
            pass

    def run_command(self, *args, **kwargs):
        full_args = ['python', f'{CODE_DIR}/pog.py'] + list(args)

        if kwargs.get('stdout'):
            return subprocess_call(full_args, cwd=self.working_dir.name, **kwargs)

        return check_output(full_args, cwd=self.working_dir.name, **kwargs).strip().decode('utf-8').split('\n')


class KeyfileTest(TestDirMixin, TestCase):
    def test_round_trip(self):
        # encrypt our sample file
        enc = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', self.tiny_sample, self.another_sample)
        self.assertEqual(enc, [
            'Fx1xB8L8L1cRPdBzkr-L8mzPusnzEBjhrQseB3DaCU4=',
            'vyGFr38Y8A0xhonhxuiZXkjS8vIVjY6VDH0-BiLJuXo=',
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # check the index as well
        show_mfn_index = self.run_command(
            f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--dump-manifest-index', manifest_name
        )
        self.assertEqual(show_mfn_index, enc)

        # check that we have what we want for decryption
        paths = sorted(listdir(self.working_dir.name))
        self.assertEqual(paths, [path.basename(manifest_name)] + enc)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

        # validate the directory looks like we expect it to
        paths = sorted(listdir(self.working_dir.name))
        self.assertEqual(paths, ['another_sample.txt', 'tiny_sample.txt'])

        # read the decrypted file
        with open(path.join(self.working_dir.name, 'tiny_sample.txt')) as f:
            contents = f.read()
        self.assertEqual(contents, 'aaaabbbb')

    def test_consistency(self):
        # regression test for our header/encryption format -- try to decrypt a known file
        with open(path.join(self.working_dir.name, 'out.txt'), 'wb') as f:
            dec = self.run_command(
                f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--decrypt',
                f'{CODE_DIR}/test/samples/US-1DnY1AVF1huiGj10G9SEGwCHa4GVxJcBnaCuAcXk=', stdout=f
            )
            self.assertEqual(dec, 0)

        # read the decrypted file
        with open(path.join(self.working_dir.name, 'out.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)

    def test_consistency_with_manifest(self):
        # regression test with manifest as well
        # copy over relevant files first
        for filename in ['US-1DnY1AVF1huiGj10G9SEGwCHa4GVxJcBnaCuAcXk=', 'keyfile-sample.mfn']:
            copyfile(f'{CODE_DIR}/test/samples/{filename}', f'{self.working_dir.name}/{filename}')

        dec = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--decrypt', '--consume',
                               'keyfile-sample.mfn')
        self.assertEqual(dec, [''])

        # read the decrypted file
        with open(path.join(self.working_dir.name, '8.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)


class AsymmetricCryptoTest(TestDirMixin, TestCase):
    def test_asymmetric_round_trip(self):
        # encrypt our sample file
        enc = self.run_command(f'--encryption-keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', self.tiny_sample, self.another_sample)
        self.assertEqual(enc, [
            'p6VsgAeMwIwCGbnuZ7lZqRPX-Ur0pT3nwsoKX2mp3Bo=',
            '1k05nlUe9UNx1-MDASPQgwAX0jKZwY4aaQvowhgUv1Q=',
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
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
        paths = sorted(listdir(self.working_dir.name))
        self.assertEqual(paths, sorted([path.basename(manifest_name)] + enc))

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--decryption-keyfile={CODE_DIR}/test/samples/only_for_testing.decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

        # validate the directory looks like we expect it to
        paths = sorted(listdir(self.working_dir.name))
        self.assertEqual(paths, ['another_sample.txt', 'tiny_sample.txt'])

        # read the decrypted file
        with open(path.join(self.working_dir.name, 'tiny_sample.txt')) as f:
            contents = f.read()
        self.assertEqual(contents, 'aaaabbbb')


    def test_consistency(self):
        # regression test for our header/encryption format -- try to decrypt a known file
        with open(path.join(self.working_dir.name, 'out.txt'), 'wb') as f:
            dec = self.run_command(
                f'--decryption-keyfile={CODE_DIR}/test/samples/only_for_testing.decrypt',
                f'{CODE_DIR}/test/samples/hq3mhX2mG_i_aVy2wv6jMGC5DjlerpvJ8O1Y_iayfPY=', stdout=f)
            self.assertEqual(dec, 0)

        # read the decrypted file
        with open(path.join(self.working_dir.name, 'out.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)

    def test_consistency_with_manifest(self):
        # regression test with manifest as well
        # copy over relevant files first
        for filename in ['hq3mhX2mG_i_aVy2wv6jMGC5DjlerpvJ8O1Y_iayfPY=', 'asymmetric-sample.mfn']:
            copyfile(f'{CODE_DIR}/test/samples/{filename}', f'{self.working_dir.name}/{filename}')

        dec = self.run_command(
            f'--decryption-keyfile={CODE_DIR}/test/samples/only_for_testing.decrypt', '--consume', 'asymmetric-sample.mfn'
        )
        self.assertEqual(dec, [''])

        # read the decrypted file
        with open(path.join(self.working_dir.name, '8.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)


@skipUnless(environ.get('CI'), 'long test skipped unless CI=1')
class BigFileTest(TestDirMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input_dir = TemporaryDirectory()
        cls.big_sample = path.join(cls.input_dir.name, 'big_sample.bin')
        cls.big_sample_checksum = make_big_file(cls.big_sample)

    @classmethod
    def tearDownClass(cls):
        with cls.input_dir:
            pass

    def test_with_keyfile(self):
        # encrypt our sample file
        enc = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', BigFileTest.big_sample)
        self.assertEqual(enc, [
            'RiOpsEQbQpxrBvXL1s047hq54EhFXxWqwag-vMuiRfc=',
            'YdK86P4e2191CxVBhZwvvPtwOLU6Ve1NzMhwLjxVXqg=',
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', '--decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

         # check that the directory looks good
        paths = sorted(listdir(self.working_dir.name))
        self.assertEqual(paths, ['big_sample.bin'])

        # check that the output file is what we expect
        filename = path.join(self.working_dir.name, 'big_sample.bin')
        actual_checksum = compute_checksum(filename)
        self.assertEqual(BigFileTest.big_sample_checksum, actual_checksum)

    def test_with_asymmetric(self):
        # encrypt our sample file
        enc = self.run_command(f'--encryption-keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', BigFileTest.big_sample)
        self.assertEqual(enc, [
            'Yb5MnLUD6aV9EOd2F7WEYzil6ephYyVeantK0uzcSPo=',
            'Ry2498AqCRLDQQj506moBXRiBLPd3ecTl-y5vvnGO0s=',
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--decryption-keyfile={CODE_DIR}/test/samples/only_for_testing.decrypt', '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--decryption-keyfile={CODE_DIR}/test/samples/only_for_testing.decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

         # check that the directory looks good
        paths = sorted(listdir(self.working_dir.name))
        self.assertEqual(paths, ['big_sample.bin'])

        # check that the output file is what we expect
        filename = path.join(self.working_dir.name, 'big_sample.bin')
        actual_checksum = compute_checksum(filename)
        self.assertEqual(BigFileTest.big_sample_checksum, actual_checksum)

    def test_smaller_chunk_size(self):
        # encrypt our sample file
        enc = self.run_command(
            f'--encryption-keyfile={CODE_DIR}/test/samples/only_for_testing.encrypt', BigFileTest.big_sample, '--chunk-size=50MB'
        )
        self.assertEqual(enc, [
            'vC5TqoeAz94lQ2Lnaiq55XdfMWQGPI4TZ1XeykVFXkI=',
            '_eqO1xjkc1mvww7iLkF_AAlZUAWw3yojKMD4EqQhU7Q=',
            'Ry2498AqCRLDQQj506moBXRiBLPd3ecTl-y5vvnGO0s=',
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--decryption-keyfile={CODE_DIR}/test/samples/only_for_testing.decrypt', '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--decryption-keyfile={CODE_DIR}/test/samples/only_for_testing.decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

         # check that the directory looks good
        paths = sorted(listdir(self.working_dir.name))
        self.assertEqual(paths, ['big_sample.bin'])

        # check that the output file is what we expect
        filename = path.join(self.working_dir.name, 'big_sample.bin')
        actual_checksum = compute_checksum(filename)
        self.assertEqual(BigFileTest.big_sample_checksum, actual_checksum)
