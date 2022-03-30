from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch, MagicMock

from b2sdk.exception import FileNotPresent

from pog.fs.pogfs import get_cloud_fs


EX_LIST_FILE_NAMES = b'''
{
  "files": [
    {
      "accountId": "aaabbbccc",
      "action": "upload",
      "bucketId": "aaabbbcccdddeeefff",
      "contentLength": 1234,
      "contentMd5": null,
      "contentSha1": "0101020304",
      "contentType": "application/octet-stream",
      "fileId": "4_abcdef123456789_t099",
      "fileInfo": {
        "src_last_modified_millis": "1576098384516"
      },
      "fileName": "pog.py",
      "uploadTimestamp": 1577746433000
    }
  ],
  "nextFileName": "pog.py "
}
'''

EX_LS = b'''
data/
file.txt
pog.py
'''

EX_LS_RECURSIVE = b'''
data/AA/AAaa0123456789=
data/BB/BBbb0123456789=
file.txt
pog.py
'''


@patch('pog.fs.b2fs.B2Api.get_bucket_by_name', autoSpec=True)
class b2fsTest(TestCase):
    def setUp(self):
        super().setUp()
        self.fs = get_cloud_fs('b2')('bucket')

    def test_exists(self, mock_bucket):
        mock_bucket.return_value = mock_bucket
        mock_bucket.get_file_info_by_name.return_value = SimpleNamespace(id_='4_abcdef123456789_t099')

        self.assertEqual(self.fs.exists('pog.py'), '4_abcdef123456789_t099')

        mock_bucket.assert_called_once_with('bucket')
        mock_bucket.get_file_info_by_name.assert_called_once_with('pog.py')

    def test_not_exists(self, mock_bucket):
        mock_bucket.return_value = mock_bucket
        mock_bucket.get_file_info_by_name.side_effect = FileNotPresent()

        self.assertFalse(self.fs.exists('foobar'))

        mock_bucket.assert_called_once_with('bucket')
        mock_bucket.get_file_info_by_name.assert_called_once_with('foobar')

    def test_upload_file(self, mock_bucket):
        mock_bucket.return_value = mock_bucket

        self.fs.upload_file('local', 'remote')

        mock_bucket.upload_local_file.assert_called_once_with('local', 'remote')

    def test_download_file(self, mock_bucket):
        mock_bucket.return_value = mock_bucket
        mock_dl = MagicMock()
        mock_bucket.download_file_by_name.return_value = SimpleNamespace(save_to=mock_dl)

        self.fs.download_file('local', 'remote')

        mock_bucket.download_file_by_name.assert_called_once_with('remote')
        mock_dl.assert_called_once_with('local')

    def test_remove_file(self, mock_bucket):
        mock_bucket.return_value = mock_bucket

        self.fs.exists = MagicMock()
        self.fs.exists.return_value = 'abc1234'

        self.fs.remove_file('foobar')
        mock_bucket.delete_file_version.assert_called_once_with('abc1234', 'foobar')

    def test_remove_file_does_not_exist(self, mock_bucket):
        mock_bucket.return_value = mock_bucket

        self.fs.exists = MagicMock()
        self.fs.exists.return_value = ''

        self.fs.remove_file('foobar')
        self.assertEqual(mock_bucket.delete_file_version.call_count, 0)

    def test_list_files(self, mock_bucket):
        mock_bucket.return_value = mock_bucket
        mock_bucket.ls.return_value = [
            (SimpleNamespace(file_name='data/'), '/'),
            (SimpleNamespace(file_name='file.txt'), '/'),
            (SimpleNamespace(file_name='pog.py'), '/'),
        ]

        self.assertEqual(self.fs.list_files(), ['data/', 'file.txt', 'pog.py'])
        mock_bucket.ls.assert_called_once_with('', recursive=False)

    def test_list_files__subdir(self, mock_bucket):
        mock_bucket.return_value = mock_bucket
        mock_bucket.ls.return_value = [
            (SimpleNamespace(file_name='data/AA/AAaa0123456789='), '/'),
            (SimpleNamespace(file_name='data/BB/BBbb0123456789='), '/'),
            (SimpleNamespace(file_name='file.txt'), '/'),
            (SimpleNamespace(file_name='pog.py'), '/'),
        ]

        self.assertEqual(
            self.fs.list_files('path/to/dir', recursive=True),
            ['data/AA/AAaa0123456789=', 'data/BB/BBbb0123456789=', 'file.txt', 'pog.py']
        )
        mock_bucket.ls.assert_called_once_with('path/to/dir', recursive=True)

    def test_list_files__empty(self, mock_bucket):
        mock_bucket.return_value = mock_bucket
        mock_bucket.ls.return_value = []

        self.assertEqual(self.fs.list_files('path/to/nowhere', recursive=False), [])

        mock_bucket.ls.assert_called_once_with('path/to/nowhere', recursive=False)

    def test_list_files__pattern(self, mock_bucket):
        mock_bucket.return_value = mock_bucket
        mock_bucket.ls.return_value = [
            (SimpleNamespace(file_name='data/'), '/'),
            (SimpleNamespace(file_name='file.txt'), '/'),
            (SimpleNamespace(file_name='pog.py'), '/'),
        ]

        self.assertEqual(self.fs.list_files(pattern='*.txt'), ['data/', 'file.txt'])

        mock_bucket.ls.assert_called_once_with('', recursive=False)
