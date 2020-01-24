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
        mock_boto.Object.return_value = mock_boto

        self.assertTrue(self.fs.exists('foo'))

        mock_boto.resource.assert_called_once_with('s3')
        mock_boto.Object.assert_called_once_with('bucket', 'foo')
        mock_boto.load.assert_called_once_with()

    def test_exists_false(self, mock_boto):
        mock_boto.resource.return_value = mock_boto
        mock_boto.Object.return_value = mock_boto
        mock_boto.load.side_effect = ClientError({'Error': {'Code': '404', 'Message': 'Not Found'}}, 'HeadObject')

        self.assertFalse(self.fs.exists('foobar'))

        mock_boto.resource.assert_called_once_with('s3')
        mock_boto.Object.assert_called_once_with('bucket', 'foobar')
        mock_boto.load.assert_called_once_with()

    def test_exists_kaboom(self, mock_boto):
        mock_boto.resource.return_value = mock_boto
        mock_boto.Object.side_effect = Exception('onoes')
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
            [{'Contents': [{'Key': 'abc'}, {'Key': 'def'}]}],
        ]

        self.assertEqual(list(self.fs.list_files()), ['abc', 'def'])

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
