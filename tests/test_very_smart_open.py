from os import remove as os_remove, path
from unittest import TestCase
from unittest.mock import patch, MagicMock

from .helpers import TestDirMixin
from pog.lib.very_smart_open import very_smart_open



class VerySmartOpenTest(TestDirMixin, TestCase):
    @patch('pog.lib.very_smart_open.open', autoSpec=True)
    @patch('pog.lib.very_smart_open.get_cloud_fs', autoSpec=True)
    def test_local(self, mock_cloud_fs, mock_open):
        with open('foo.txt', 'wt') as f:
            f.write('hello')

        self.assertEqual(mock_open.return_value, very_smart_open('foo.txt', 'rb'))
        mock_open.assert_called_once_with('foo.txt', 'rb')
        self.assertEqual(mock_cloud_fs.call_count, 0)

    @patch('pog.lib.very_smart_open.open', autoSpec=True)
    @patch('pog.lib.very_smart_open.get_cloud_fs', autoSpec=True)
    def test_dl(self, mock_cloud_fs, mock_open):
        mock_cloud_fs.return_value = MagicMock()
        fs_instance = MagicMock()
        mock_cloud_fs.return_value.return_value = fs_instance

        with very_smart_open('s3://mybucket/foo.mfn', 'rb') as f:
            self.assertIn('.mfn', f.name)
            fs_instance.download_file.assert_called_once_with(f.name, 'foo.mfn')
        mock_cloud_fs.assert_called_once_with('s3')
        mock_cloud_fs.return_value.assert_called_once_with('mybucket')

    @patch('pog.lib.very_smart_open.open', autoSpec=True)
    def test_fs_fallback(self, mock_open):
        self.assertEqual(mock_open.return_value, very_smart_open(self.tiny_sample, 'rb'))
        mock_open.assert_called_once_with(self.tiny_sample, 'rb')
