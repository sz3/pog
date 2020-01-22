import hashlib
import random
from glob import glob
from os import environ, path, listdir
from shutil import copyfile
from subprocess import STDOUT
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

from .helpers import TestDirMixin, POG_ROOT, SAMPLE_TIME1, SAMPLE_TIME2


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
    random.seed(1234)
    hash_md5 = hashlib.md5()

    with open(filename, 'wb') as f:
        chunk_size = 100000
        for _ in range(110000000 // chunk_size):  # ~110 MB ... default chunk size is 100MB
            chunk = bytearray(random.getrandbits(8) for _ in range(chunk_size))
            f.write(chunk)
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


class KeyfileTest(TestDirMixin, TestCase):
    encryption_flag = f'--keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt'
    decryption_flag = encryption_flag

    tiny_sample_blobname = 'Fx1xB8L8L1cRPdBzkr-L8mzPusnzEBjhrQseB3DaCU4='
    another_sample_blobname = 'vyGFr38Y8A0xhonhxuiZXkjS8vIVjY6VDH0-BiLJuXo='

    consistency_mfn = 'keyfile-sample.mfn'
    consistency_blobname = 'US-1DnY1AVF1huiGj10G9SEGwCHa4GVxJcBnaCuAcXk='

    def test_round_trip(self):
        # encrypt our sample files
        enc = self.run_command(self.encryption_flag, self.tiny_sample, self.another_sample)
        self.assertEqual(enc, [self.tiny_sample_blobname, self.another_sample_blobname])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(self.decryption_flag, '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # check the index as well
        show_mfn_index = self.run_command(self.encryption_flag, '--dump-manifest-index', manifest_name)
        self.assertEqual(sorted(show_mfn_index), sorted(enc))

        # check that we have what we want for decryption
        paths = listdir(self.working_dir.name)
        self.assertCountEqual(paths, [path.basename(manifest_name)] + enc)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(self.decryption_flag, '--decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

        # validate the directory looks like we expect it to
        paths = listdir(self.working_dir.name)
        self.assertCountEqual(paths, ['another_sample.txt', 'tiny_sample.txt'])

        # read the decrypted files
        tiny_sample = path.join(self.working_dir.name, 'tiny_sample.txt')
        with open(tiny_sample) as f:
            contents = f.read()
        self.assertEqual(contents, 'aaaabbbb')

        another_sample = path.join(self.working_dir.name, 'another_sample.txt')
        with open(another_sample) as f:
            contents = f.read()
        self.assertEqual(contents, '0123456789')

        # check file metadata
        self.assertEqual(path.getmtime(tiny_sample), SAMPLE_TIME1)
        self.assertEqual(path.getmtime(another_sample), SAMPLE_TIME2)

    def test_consistency(self):
        # regression test for our header/encryption format -- try to decrypt a known file
        with open(path.join(self.working_dir.name, 'out.txt'), 'wb') as f:
            dec = self.run_command(self.decryption_flag, '--decrypt',
                f'{POG_ROOT}/tests/samples/{self.consistency_blobname}', stdout=f
            )
            self.assertEqual(dec, 0)

        # read the decrypted file
        with open(path.join(self.working_dir.name, 'out.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)

    def test_consistency_with_manifest(self):
        # regression test with manifest as well
        # copy over relevant files first
        for filename in [self.consistency_blobname, self.consistency_mfn]:
            copyfile(f'{POG_ROOT}/tests/samples/{filename}', f'{self.working_dir.name}/{filename}')

        dec = self.run_command(self.decryption_flag, '--decrypt', '--consume', self.consistency_mfn)
        self.assertEqual(dec, [''])

        # read the decrypted file
        with open(path.join(self.working_dir.name, '8.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)

    def test_consistency_stderr(self):
        # test for stdout/stderr formatting
        # relevant for correlating which blobs belong to which files
        # copy over relevant files first
        for filename in [self.consistency_mfn]:
            copyfile(f'{POG_ROOT}/tests/samples/{filename}', f'{self.working_dir.name}/{filename}')

        show_mfn = self.run_command(self.decryption_flag, '--dump-manifest', self.consistency_mfn, stderr=STDOUT)
        self.assertEqual(show_mfn, [
            '*** {}:'.format(self.consistency_mfn),
            '* {}:'.format('8.txt'),
            self.consistency_blobname,
        ])

    def test_absolute_paths(self):
        # encrypt our sample files, saving their absolute paths in the manifest
        enc = self.run_command(
            self.encryption_flag, self.tiny_sample, self.another_sample, '--store-absolute-paths'
        )
        self.assertEqual(enc, [self.tiny_sample_blobname, self.another_sample_blobname])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(self.decryption_flag, '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(self.decryption_flag, '--decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

        # validate the directory looks like we expect it to
        # since we saved the absolute paths, our expected full path will be... interesting
        full_exploded_path = path.abspath(self.working_dir.name + self.input_dir.name)
        paths = listdir(full_exploded_path)
        self.assertCountEqual(paths, ['another_sample.txt', 'tiny_sample.txt'])

        # read the decrypted files
        with open(path.join(full_exploded_path, 'tiny_sample.txt')) as f:
            contents = f.read()
        self.assertEqual(contents, 'aaaabbbb')

        with open(path.join(full_exploded_path, 'another_sample.txt')) as f:
            contents = f.read()
        self.assertEqual(contents, '0123456789')


class AsymmetricCryptoTest(KeyfileTest):
    encryption_flag = f'--encryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt'
    decryption_flag = f'--decryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.decrypt'

    tiny_sample_blobname = 'p6VsgAeMwIwCGbnuZ7lZqRPX-Ur0pT3nwsoKX2mp3Bo='
    another_sample_blobname = '1k05nlUe9UNx1-MDASPQgwAX0jKZwY4aaQvowhgUv1Q='

    consistency_mfn = 'asymmetric-sample.mfn'
    consistency_blobname = 'hq3mhX2mG_i_aVy2wv6jMGC5DjlerpvJ8O1Y_iayfPY='

    def test_manifest_index_ordering(self):
        '''
        We sort the blobs stored in the manifest index, to limit information about which blobs belong together.
        '''
        # encrypt our sample files
        enc = self.run_command(self.encryption_flag, self.tiny_sample, self.another_sample)
        self.assertEqual(enc, [self.tiny_sample_blobname, self.another_sample_blobname])

        # check that the manifest index looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(self.decryption_flag, '--dump-manifest-index', manifest_name)
        self.assertEqual(show_mfn, sorted(enc))


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
        enc = self.run_command(f'--keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt', BigFileTest.big_sample)
        self.assertEqual(enc, [
            'RiOpsEQbQpxrBvXL1s047hq54EhFXxWqwag-vMuiRfc=',
            'YdK86P4e2191CxVBhZwvvPtwOLU6Ve1NzMhwLjxVXqg=',
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt', '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt', '--decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

         # check that the directory looks good
        paths = listdir(self.working_dir.name)
        self.assertEqual(paths, ['big_sample.bin'])

        # check that the output file is what we expect
        filename = path.join(self.working_dir.name, 'big_sample.bin')
        actual_checksum = compute_checksum(filename)
        self.assertEqual(BigFileTest.big_sample_checksum, actual_checksum)

    def test_with_asymmetric(self):
        # encrypt our sample file
        enc = self.run_command(f'--encryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt', BigFileTest.big_sample)
        self.assertEqual(enc, [
            'Yb5MnLUD6aV9EOd2F7WEYzil6ephYyVeantK0uzcSPo=',
            'Ry2498AqCRLDQQj506moBXRiBLPd3ecTl-y5vvnGO0s=',
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--decryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.decrypt', '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # check the index as well -- make sure it's sorted
        show_mfn_index = self.run_command(f'--encryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt', '--dump-manifest-index', manifest_name)
        self.assertEqual(show_mfn_index, sorted(enc))

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--decryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

         # check that the directory looks good
        paths = listdir(self.working_dir.name)
        self.assertEqual(paths, ['big_sample.bin'])

        # check that the output file is what we expect
        filename = path.join(self.working_dir.name, 'big_sample.bin')
        actual_checksum = compute_checksum(filename)
        self.assertEqual(BigFileTest.big_sample_checksum, actual_checksum)

    def test_smaller_chunk_size(self):
        # encrypt our sample file
        enc = self.run_command(
            f'--encryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt', BigFileTest.big_sample, '--chunk-size=50MB'
        )
        self.assertEqual(enc, [
            'vC5TqoeAz94lQ2Lnaiq55XdfMWQGPI4TZ1XeykVFXkI=',
            '_eqO1xjkc1mvww7iLkF_AAlZUAWw3yojKMD4EqQhU7Q=',
            'Ry2498AqCRLDQQj506moBXRiBLPd3ecTl-y5vvnGO0s=',
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--decryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.decrypt', '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, enc)

        # check the

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--decryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [''])

         # check that the directory looks good
        paths = listdir(self.working_dir.name)
        self.assertEqual(paths, ['big_sample.bin'])

        # check that the output file is what we expect
        filename = path.join(self.working_dir.name, 'big_sample.bin')
        actual_checksum = compute_checksum(filename)
        self.assertEqual(BigFileTest.big_sample_checksum, actual_checksum)