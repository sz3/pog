from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from botocore.exceptions import ClientError

from pog.fs.pogfs import get_cloud_fs


@patch('pog.fs.s3fs.boto3', autoSpec=True)
class s3fsTest(TestCase):
    def setUp(self):
        super().setUp()
        self.fs = get_cloud_fs('s3')('bucket')

    def test_exists(self, mock_boto):
        mock_boto.resource.return_value = mock_boto
        mock_boto.ObjectSummary.return_value = SimpleNamespace(last_modified=12345)

        self.assertTrue(self.fs.exists('foo'))

        mock_boto.resource.assert_called_once_with('s3')
        mock_boto.ObjectSummary.assert_called_once_with('bucket', 'foo')

    def test_exists__false(self, mock_boto):
        mock_boto.resource.return_value = mock_boto
        mock_boto.ObjectSummary.side_effect = ClientError({'Error': {'Code': '404', 'Message': 'Not Found'}}, 'HeadObject')

        self.assertFalse(self.fs.exists('foobar'))

        mock_boto.resource.assert_called_once_with('s3')
        mock_boto.ObjectSummary.assert_called_once_with('bucket', 'foobar')

    def test_exists__kaboom(self, mock_boto):
        mock_boto.resource.return_value = mock_boto
        mock_boto.ObjectSummary.side_effect = Exception('onoes')
        with self.assertRaises(Exception) as e:
            self.fs.exists('uhoh')

        self.assertEqual(str(e.exception), 'onoes')

    def test_upload_file(self, mock_boto):
        mock_boto.client.return_value = mock_boto

        self.fs.upload_file('local', 'remote')

        mock_boto.client.assert_called_once_with('s3')
        mock_boto.upload_file.assert_called_once_with('local', 'bucket', 'remote')

    def test_download_file(self, mock_boto):
        mock_boto.client.return_value = mock_boto

        self.fs.download_file('local', 'remote')

        mock_boto.client.assert_called_once_with('s3')
        mock_boto.download_file.assert_called_once_with('bucket', 'remote', 'local')

    def test_remove_file(self, mock_boto):
        mock_boto.client.return_value = mock_boto

        self.fs.remove_file('remote')

        mock_boto.client.assert_called_once_with('s3')
        mock_boto.delete_object.assert_called_once_with(Bucket='bucket', Key='remote')

    def test_list_files_defaults(self, mock_boto):
        mock_boto.client.return_value = mock_boto
        mock_boto.get_paginator.return_value = mock_boto
        mock_boto.paginate.side_effect = [
            [{
                'CommonPrefixes': [{'Prefix': 'dir/'}],
                'Contents': [{'Key': 'abc'}, {'Key': 'def'}],
            }],
        ]

        self.assertEqual(list(self.fs.list_files()), ['dir/', 'abc', 'def'])

        mock_boto.client.assert_called_once_with('s3')
        mock_boto.get_paginator.assert_called_once_with('list_objects_v2')
        mock_boto.paginate.assert_called_once_with(Bucket='bucket', Prefix='', Delimiter='/')

    def test_list_files_subdir(self, mock_boto):
        mock_boto.client.return_value = mock_boto
        mock_boto.get_paginator.return_value = mock_boto
        mock_boto.paginate.side_effect = [
            [{'Contents': [{'Key': 'abc'}, {'Key': 'def'}]}],
        ]

        self.assertEqual(list(self.fs.list_files('path/to/files', recursive=True)), ['abc', 'def'])

        mock_boto.client.assert_called_once_with('s3')
        mock_boto.get_paginator.assert_called_once_with('list_objects_v2')
        mock_boto.paginate.assert_called_once_with(Bucket='bucket', Prefix='path/to/files')

    def test_list_files_pattern(self, mock_boto):
        mock_boto.client.return_value = mock_boto
        mock_boto.get_paginator.return_value = mock_boto
        mock_boto.paginate.side_effect = [
            [{
                'CommonPrefixes': [{'Prefix': 'dir/'}],
                'Contents': [{'Key': 'file.txt'}, {'Key': 'other.jpg'}],
            }],
        ]

        self.assertEqual(list(self.fs.list_files(pattern='*.txt')), ['dir/', 'file.txt'])

        mock_boto.client.assert_called_once_with('s3')
        mock_boto.get_paginator.assert_called_once_with('list_objects_v2')
        mock_boto.paginate.assert_called_once_with(Bucket='bucket', Prefix='', Delimiter='/')
