from unittest import TestCase
from unittest.mock import patch, MagicMock

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


@patch('pog.fs.b2fs.check_output', autoSpec=True)
class b2fsTest(TestCase):
    def setUp(self):
        super().setUp()
        self.fs = get_cloud_fs('b2')('bucket')

    def test_exists(self, mock_run):
        mock_run.return_value = EX_LIST_FILE_NAMES

        self.assertFalse(self.fs.exists('foobar'))
        self.assertEqual(self.fs.exists('foobar'), '')
        self.assertTrue(self.fs.exists('pog.py'))
        self.assertEqual(self.fs.exists('pog.py'), '4_abcdef123456789_t099')

        mock_run.assert_any_call(['b2', 'list-file-names', 'bucket', 'foobar', '1'])
        mock_run.assert_any_call(['b2', 'list-file-names', 'bucket', 'pog.py', '1'])

    def test_upload_file(self, mock_run):
        self.fs.upload_file('local', 'remote')
        mock_run.assert_called_once_with(['b2', 'upload_file', 'bucket', 'local', 'remote'])

    def test_download_file(self, mock_run):
        self.fs.download_file('local', 'remote')
        mock_run.assert_called_once_with(['b2', 'download-file-by-name', 'bucket', 'remote', 'local'])

    def test_remove_file(self, mock_run):
        self.fs.exists = MagicMock()
        self.fs.exists.return_value = 'abc1234'

        self.fs.remove_file('foobar')
        mock_run.assert_called_once_with(['b2', 'delete-file-version', 'foobar', 'abc1234'])

    def test_remove_file_does_not_exist(self, mock_run):
        self.fs.exists = MagicMock()
        self.fs.exists.return_value = ''

        self.fs.remove_file('foobar')
        self.assertEqual(mock_run.call_count, 0)

    def test_list_files_defaults(self, mock_run):
        mock_run.return_value = EX_LS
        self.assertEqual(self.fs.list_files(), ['data/', 'file.txt', 'pog.py'])
        mock_run.assert_called_once_with(['b2', 'ls', 'bucket'])

    def test_list_files_subdir(self, mock_run):
        mock_run.return_value = EX_LS_RECURSIVE
        self.assertEqual(
            self.fs.list_files('path/to/dir', recursive=True),
            ['data/AA/AAaa0123456789=', 'data/BB/BBbb0123456789=', 'file.txt', 'pog.py']
        )
        mock_run.assert_called_once_with(['b2', 'ls', '--recursive', 'bucket', 'path/to/dir'])

    def test_list_files_empty(self, mock_run):
        mock_run.return_value = b''
        self.assertEqual(self.fs.list_files('path/to/nowhere', recursive=False), [])
        mock_run.assert_called_once_with(['b2', 'ls', 'bucket', 'path/to/nowhere'])

    def test_list_files_pattern(self, mock_run):
        mock_run.return_value = EX_LS
        self.assertEqual(self.fs.list_files(pattern='*.txt'), ['data/', 'file.txt'])
        mock_run.assert_called_once_with(['b2', 'ls', 'bucket'])
