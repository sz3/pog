from os import remove as os_remove
from unittest import TestCase
from unittest.mock import patch

from .helpers import TestDirMixin
from pog.lib.blob_store import BlobStore


class BlobStoreTest(TestDirMixin, TestCase):
    def tearDown(self):
        try:
            os_remove('BlobStoreTest.test_default.txt')
        except OSError:
            pass
        super().tearDown()

    def test_default(self):
        dst = '/path/will/be/ignored/BlobStoreTest.test_default.txt'
        bs = BlobStore()
        bs.save(dst, self.tiny_sample)

        # outputs to cwd
        with open('BlobStoreTest.test_default.txt', 'rt') as f:
            contents = f.read()
            self.assertEqual(contents, 'aaaabbbb')

    @patch('pog.fs.pogfs.s3fs', autoSpec=True)
    def test_s3(self, mock_s3):
        mock_s3.return_value = mock_s3
        mock_s3.exists.return_value = False

        dst = 'full/path/coolfile.txt'

        bs = BlobStore('s3')
        bs.save(dst, self.tiny_sample)

        mock_s3.exists.assert_called_once_with('full/path/coolfile.txt')
        mock_s3.upload_file.assert_called_once_with(self.tiny_sample, 'full/path/coolfile.txt')

    @patch('pog.fs.pogfs.s3fs', autoSpec=True)
    def test_s3_file_exists(self, mock_s3):
        mock_s3.return_value = mock_s3
        mock_s3.exists.return_value = True

        dst = 'full/path/coolfile.txt'

        bs = BlobStore('s3')
        bs.save(dst, self.tiny_sample)

        mock_s3.exists.assert_called_once_with('full/path/coolfile.txt')
        self.assertEqual(mock_s3.upload_file.call_count, 0)

    @patch('pog.fs.pogfs.b2fs', autoSpec=True)
    @patch('pog.fs.pogfs.s3fs', autoSpec=True)
    def test_s3_and_b2(self, mock_s3, mock_b2):
        mock_b2.return_value = mock_b2
        mock_b2.exists.return_value = False
        mock_s3.return_value = mock_s3
        mock_s3.exists.return_value = True

        dst = 'full/path/coolfile.txt'

        bs = BlobStore('s3, b2')
        bs.save(dst, self.tiny_sample)

        mock_b2.exists.assert_called_once_with('full/path/coolfile.txt')
        mock_b2.upload_file.assert_called_once_with(self.tiny_sample, 'full/path/coolfile.txt')

        mock_s3.exists.assert_called_once_with('full/path/coolfile.txt')
        self.assertEqual(mock_s3.upload_file.call_count, 0)

    @patch('pog.fs.pogfs.s3fs', autoSpec=True)
    def test_save_blob(self, mock_s3):
        mock_s3.return_value = mock_s3
        mock_s3.exists.return_value = False

        blob_name = 'argh12456789'

        bs = BlobStore('s3')
        bs.save_blob(blob_name, self.tiny_sample)

        mock_s3.exists.assert_called_once_with('data/ar/argh12456789')
        mock_s3.upload_file.assert_called_once_with(self.tiny_sample, 'data/ar/argh12456789')
