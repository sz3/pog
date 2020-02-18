import hashlib
import random
from glob import glob
from os import environ, path, listdir
from shutil import copyfile
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

from .helpers import TestDirMixin, POG_ROOT, SAMPLE_TIME1, SAMPLE_TIME2
from pog.fs.localfs import localfs
from pog.lib.blob_store import _data_path


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

    tiny_sample_blobname = 'BvbQeMboxw1jFDXe_ed5QsDWay5kvtlZ_qx7buz_z2M='
    another_sample_blobname = 'vuWyVoUolWk2qRZ-48mvEoTuR5_SuzrN8uO6qusRZSE='

    consistency_mfn = 'keyfile-sample.mfn'
    consistency_blobname = 'US-1DnY1AVF1huiGj10G9SEGwCHa4GVxJcBnaCuAcXk='

    def test_round_trip(self):
        # encrypt our sample files
        enc = self.run_command(self.encryption_flag, self.tiny_sample, self.another_sample)
        # ordered lexicographically by filename
        self.assertEqual(enc, [
            f'*** 1/2: {self.another_sample}',
            self.another_sample_blobname,
            f'*** 2/2: {self.tiny_sample}',
            self.tiny_sample_blobname
        ])
        blobs = [l for l in enc if not l.startswith('***')]

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(self.decryption_flag, '--dump-manifest', manifest_name)
        self.assertEqual(
            show_mfn, ['* another_sample.txt:', blobs[0], '* tiny_sample.txt:', blobs[1]]
        )

        # check the index as well
        show_mfn_index = self.run_command(self.encryption_flag, '--dump-manifest-index', manifest_name)
        self.assertEqual(sorted(show_mfn_index), sorted(blobs))

        # check that we have what we want for decryption
        paths = listdir(self.working_dir.name)
        self.assertCountEqual(paths, [path.basename(manifest_name)] + blobs)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(self.decryption_flag, '--decrypt', '--consume', manifest_name)
        self.assertEqual(dec, ['*** 1/2: another_sample.txt', '*** 2/2: tiny_sample.txt'])

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
            dec = self.run_command(
                self.decryption_flag, '--decrypt', f'{POG_ROOT}/tests/samples/{self.consistency_blobname}', stdout=f
            )
            self.assertEqual(dec, [])

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
        self.assertEqual(dec, ['*** 1/1: 8.txt'])

        # read the decrypted file
        with open(path.join(self.working_dir.name, '8.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)

    def test_consistency_dump_manifest(self):
        # test for stdout formatting
        # relevant for correlating which blobs belong to which files
        # copy over relevant files first
        for filename in [self.consistency_mfn]:
            copyfile(f'{POG_ROOT}/tests/samples/{filename}', f'{self.working_dir.name}/{filename}')

        show_mfn = self.run_command(self.decryption_flag, '--dump-manifest', self.consistency_mfn)
        self.assertEqual(show_mfn, [
            '* {}:'.format('8.txt'),
            self.consistency_blobname,
        ])

    def test_consistency_fs_input(self):
        # flex the download_list() logic in various ways. First, we'll create a test pogfs data structure in our working_dir
        fs = localfs(root=self.working_dir.name)
        fs.upload_file(f'{POG_ROOT}/tests/samples/{self.consistency_mfn}', self.consistency_mfn)
        fs.upload_file(f'{POG_ROOT}/tests/samples/{self.consistency_blobname}', _data_path(self.consistency_blobname))

        # --dump-manifest
        show_mfn = self.run_command(self.decryption_flag, '--dump-manifest', f'local:///{self.consistency_mfn}')
        self.assertEqual(show_mfn, ['* 8.txt:', self.consistency_blobname])

        # --dump-manifest-index
        show_mfn_idx = self.run_command(self.decryption_flag, '--dump-manifest-index', f'local:///{self.consistency_mfn}')
        self.assertEqual(show_mfn_idx, [self.consistency_blobname])

        # --decrypt
        dec = self.run_command(self.decryption_flag, '--decrypt', f'local:///{self.consistency_mfn}')
        self.assertEqual(dec, ['*** 1/1: 8.txt'])

        # read the decrypted file
        with open(path.join(self.working_dir.name, '8.txt'), 'rb') as f:
            contents = f.read()
        self.assertEqual(contents, SAMPLE_TEXT)

    def test_absolute_paths(self):
        # encrypt our sample files, saving their absolute paths in the manifest
        enc = self.run_command(
            self.encryption_flag, self.tiny_sample, self.another_sample, '--store-absolute-paths'
        )
        self.assertEqual(enc, [
            f'*** 1/2: {self.another_sample}',
            self.another_sample_blobname,
            f'*** 2/2: {self.tiny_sample}',
            self.tiny_sample_blobname
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(self.decryption_flag, '--dump-manifest', manifest_name)
        self.assertEqual(
            show_mfn, [
                '* {}:'.format(self.another_sample), enc[1],
                '* {}:'.format(self.tiny_sample), enc[3],
            ]
        )

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(self.decryption_flag, '--decrypt', '--consume', manifest_name)
        self.assertEqual(dec, [
            '*** 1/2: {}'.format(self.another_sample),
            '*** 2/2: {}'.format(self.tiny_sample),
        ])

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

    def test_glob_input_directory(self):
        # encrypt our sample files, saving their absolute paths in the manifest
        enc = self.run_command(
            self.encryption_flag, self.input_dir.name, '--store-absolute-paths'
        )
        self.assertEqual(enc, [
            f'*** 1/2: {self.another_sample}',
            self.another_sample_blobname,
            f'*** 2/2: {self.tiny_sample}',
            self.tiny_sample_blobname
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(self.decryption_flag, '--dump-manifest', manifest_name)
        self.assertEqual(
            show_mfn, [
                '* {}:'.format(self.another_sample), enc[1],
                '* {}:'.format(self.tiny_sample), enc[3],
            ]
        )


class AsymmetricCryptoTest(KeyfileTest):
    encryption_flag = f'--encryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt'
    decryption_flag = f'--decryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.decrypt'

    tiny_sample_blobname = 'Fx1xB8L8L1cRPdBzkr-L8mzPusnzEBjhrQseB3DaCU4='
    another_sample_blobname = 'vyGFr38Y8A0xhonhxuiZXkjS8vIVjY6VDH0-BiLJuXo='

    consistency_mfn = 'asymmetric-sample.mfn'
    consistency_blobname = 'hq3mhX2mG_i_aVy2wv6jMGC5DjlerpvJ8O1Y_iayfPY='

    def test_manifest_index_ordering(self):
        '''
        We sort the blobs stored in the manifest index, to limit information about which blobs belong together.
        '''
        # encrypt our sample files
        enc = self.run_command(self.encryption_flag, self.tiny_sample, self.another_sample)
        self.assertEqual(enc, [
            f'*** 1/2: {self.another_sample}',
            self.another_sample_blobname,
            f'*** 2/2: {self.tiny_sample}',
            self.tiny_sample_blobname
        ])
        blobs = [l for l in enc if not l.startswith('***')]

        # check that the manifest index looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(self.decryption_flag, '--dump-manifest-index', manifest_name)
        # manifest index sorted by blobname
        self.assertEqual(show_mfn, sorted(blobs))


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
            'xyQWj-UXXZpwWXPF2c5_MsBm3cTfZFXayUVLLMlkt4Y=',
            'HXBJ_N4EM2rywLdOWT02hccp4c_oLk0QyD2lc3vUttw=',
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt', '--dump-manifest',
                                    manifest_name)
        self.assertEqual(show_mfn, ['* big_sample.bin:'] + enc)

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt', '--decrypt', '--consume',
                               manifest_name)
        self.assertEqual(dec, ['* 1/1: big_sample.bin'])

        # check that the directory looks good
        paths = listdir(self.working_dir.name)
        self.assertEqual(paths, ['big_sample.bin'])

        # check that the output file is what we expect
        filename = path.join(self.working_dir.name, 'big_sample.bin')
        actual_checksum = compute_checksum(filename)
        self.assertEqual(BigFileTest.big_sample_checksum, actual_checksum)

    def test_with_asymmetric(self):
        # encrypt our sample file
        enc = self.run_command(f'--encryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt',
                               BigFileTest.big_sample)
        self.assertEqual(enc, [
            'RiOpsEQbQpxrBvXL1s047hq54EhFXxWqwag-vMuiRfc=',
            'YdK86P4e2191CxVBhZwvvPtwOLU6Ve1NzMhwLjxVXqg=',
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--decryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.decrypt',
                                    '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, ['* big_sample.bin:'] + enc)

        # check the index as well -- make sure it's sorted
        show_mfn_index = self.run_command(f'--encryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt',
                                          '--dump-manifest-index', manifest_name)
        self.assertEqual(show_mfn_index, sorted(enc))

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--decryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.decrypt', '--consume',
                               manifest_name)
        self.assertEqual(dec, ['* 1/1: big_sample.bin'])

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
            f'--encryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.encrypt', BigFileTest.big_sample,
            '--chunk-size=50MB'
        )
        self.assertEqual(enc, [
            'PURfe1ei1aqpPRarpAfKkcKPRSHdo5hPH-bvfYND2KM=',
            'nnL4ta-BChpb36CIFeZUG4lJLiz8l0YVv94IaABcgyU=',
            'YdK86P4e2191CxVBhZwvvPtwOLU6Ve1NzMhwLjxVXqg=',
        ])

        # check that the manifest looks good
        manifest_name = glob(path.join(self.working_dir.name, '*.mfn'))[0]
        show_mfn = self.run_command(f'--decryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.decrypt',
                                    '--dump-manifest', manifest_name)
        self.assertEqual(show_mfn, ['* big_sample.bin:'] + enc)

        # check the

        # decrypt, consuming our encrypted inputs
        dec = self.run_command(f'--decryption-keyfile={POG_ROOT}/tests/samples/only_for_testing.decrypt', '--consume',
                               manifest_name)
        self.assertEqual(dec, ['* 1/1: big_sample.bin'])

        # check that the directory looks good
        paths = listdir(self.working_dir.name)
        self.assertEqual(paths, ['big_sample.bin'])

        # check that the output file is what we expect
        filename = path.join(self.working_dir.name, 'big_sample.bin')
        actual_checksum = compute_checksum(filename)
        self.assertEqual(BigFileTest.big_sample_checksum, actual_checksum)
