from os import remove as os_remove, path
from unittest import TestCase
from unittest.mock import patch

from .helpers import TestDirMixin
from pog.lib.blob_store import BlobStore, download_list, _data_path, parse_storage_str


class DownloadListTest(TestDirMixin, TestCase):
    def test_pass_through(self):
        '''
        if all paths are local,
        for filename in download_list(files)
        ==
        for filename in files
        '''
        files = ['a', 'b', 'c', 'd']
        self.assertEqual(list(download_list(files)), files)

        # can pass as *args too
        self.assertEqual(list(download_list(*files)), files)

    def test_pass_through_tricky(self):
        '''
        some paths kinda look like urls, but aren't
        '''
        files = ['2020-01-23T18:02:16.482212.mfn']
        self.assertEqual(list(download_list(files)), files)

    @patch('pog.fs.pogfs.b2fs', autoSpec=True)
    @patch('pog.fs.pogfs.s3fs', autoSpec=True)
    def test_download_mfns(self, mock_s3, mock_b2):
        mock_b2.return_value = mock_b2
        mock_s3.return_value = mock_s3

        local_paths = []
        for f in download_list('s3://bucket1/file.mfn', 'b2://bucket2/another.mfn'):
            local_paths.append(f)
            self.assertTrue(path.exists(f))

        mock_s3.assert_called_once_with('bucket1')
        mock_s3.download_file.assert_any_call(local_paths[0], 'file.mfn')

        mock_b2.assert_called_once_with('bucket2')
        mock_b2.download_file.assert_any_call(local_paths[1], 'another.mfn')

        # should clean up
        for f in local_paths:
            self.assertFalse(path.exists(f))

    @patch('pog.fs.pogfs.b2fs', autoSpec=True)
    @patch('pog.fs.pogfs.s3fs', autoSpec=True)
    def test_download_extract(self, mock_s3, mock_b2):
        mock_b2.return_value = mock_b2
        mock_s3.return_value = mock_s3

        local_paths = []
        fs_infos = []
        partials = []
        for f, fs_info, prtl in download_list('boring.mfn', 's3://bucket1/file.mfn', 'b2://bucket2/another.mfn',
                                              extract=True):
            local_paths.append(f)
            fs_infos.append(fs_info)
            partials.append(prtl)
            if f != 'boring.mfn':  # no tempfile download for local file
                self.assertTrue(path.exists(f))

        self.assertEqual(local_paths[0], 'boring.mfn')
        self.assertEqual(fs_infos[0], [])
        self.assertEqual(partials[0], None)

        mock_s3.assert_called_once_with('bucket1')
        mock_s3.download_file.assert_any_call(local_paths[1], 'file.mfn')
        self.assertEqual(fs_infos[1], ('s3', 'bucket1'))
        self.assertEqual(partials[1], None)

        mock_b2.assert_called_once_with('bucket2')
        mock_b2.download_file.assert_any_call(local_paths[2], 'another.mfn')
        self.assertEqual(fs_infos[2], ('b2', 'bucket2'))
        self.assertEqual(partials[2], None)

        # should clean up
        for f in local_paths:
            self.assertFalse(path.exists(f))

    @patch('pog.fs.pogfs.b2fs', autoSpec=True)
    @patch('pog.fs.pogfs.s3fs', autoSpec=True)
    def test_download_extract_with_partials(self, mock_s3, mock_b2):
        mock_b2.return_value = mock_b2
        mock_s3.return_value = mock_s3

        local_paths = []
        fs_infos = []
        partials = []
        for f, fs_info, prtl in download_list('boring.mfn', 'file1', 'file2', 's3://bucket1/file.mfn', 'dir/file',
                                              'b2://bucket2/another.mfn', extract=True):
            local_paths.append(f)
            fs_infos.append(fs_info)
            partials.append(prtl)
            if f != 'boring.mfn':  # no tempfile download for local file
                self.assertTrue(path.exists(f))

        self.assertEqual(local_paths[0], 'boring.mfn')
        self.assertEqual(fs_infos[0], [])
        self.assertEqual(partials[0], {'file1', 'file2'})

        mock_s3.assert_called_once_with('bucket1')
        mock_s3.download_file.assert_any_call(local_paths[1], 'file.mfn')
        self.assertEqual(fs_infos[1], ('s3', 'bucket1'))
        self.assertEqual(partials[1], {'dir/file'})

        mock_b2.assert_called_once_with('bucket2')
        mock_b2.download_file.assert_any_call(local_paths[2], 'another.mfn')
        self.assertEqual(fs_infos[2], ('b2', 'bucket2'))
        self.assertEqual(partials[2], None)

        # should clean up
        for f in local_paths:
            self.assertFalse(path.exists(f))

    @patch('pog.fs.pogfs.b2fs', autoSpec=True)
    @patch('pog.fs.pogfs.s3fs', autoSpec=True)
    def test_download_blobs(self, mock_s3, mock_b2):
        mock_b2.return_value = mock_b2
        mock_s3.return_value = mock_s3

        local_paths = []
        for f in download_list('s3://bucket1/abcdef1234', 'b2://bucket2/fedcba1234'):
            local_paths.append(f)
            self.assertTrue(path.exists(f))

        mock_s3.assert_called_once_with('bucket1')
        mock_s3.download_file.assert_any_call(local_paths[0], 'data/ab/abcdef1234')

        mock_b2.assert_called_once_with('bucket2')
        mock_b2.download_file.assert_any_call(local_paths[1], 'data/fe/fedcba1234')

        # should clean up
        for f in local_paths:
            self.assertFalse(path.exists(f))

    @patch('pog.fs.pogfs.s3fs', autoSpec=True)
    def test_download_blobs_with_fs_info(self, mock_s3):
        # this is the common use case -- get the fs_info from the mfn download, pass it in with `fs_info`
        mock_s3.return_value = mock_s3

        remote_paths = ['abcdef1234', 'fedcba1234']
        local_paths = []
        for f in download_list(remote_paths, fs_info=('s3', 'mybucket')):
            local_paths.append(f)
            self.assertTrue(path.exists(f))

        mock_s3.assert_any_call('mybucket')
        for local, remote in zip(local_paths, remote_paths):
            mock_s3.download_file.assert_any_call(local, _data_path(remote))

        # should clean up
        for f in local_paths:
            self.assertFalse(path.exists(f))


class BlobStoreTest(TestDirMixin, TestCase):
    def tearDown(self):
        try:
            os_remove('BlobStoreTest.test_default.txt')
        except OSError:
            pass
        super().tearDown()

    def test_parse_storage_str(self):
        self.assertEqual(parse_storage_str('b2'), [('b2', None)])
        self.assertEqual(parse_storage_str('b2:bucket2'), [('b2', 'bucket2')])
        self.assertEqual(parse_storage_str('b2://bucket2'), [('b2', 'bucket2')])
        self.assertEqual(parse_storage_str('b2://bucket2/'), [('b2', 'bucket2')])
        self.assertEqual(parse_storage_str('local:/home/user/'), [('local', '/home/user')])
        self.assertEqual(parse_storage_str('./local-save.sh'), [('./local-save.sh', None)])
        self.assertEqual(parse_storage_str('b2,s3'), [('b2', None), ('s3', None)])
        self.assertEqual(parse_storage_str(
            'b2,s3,./local-save.sh'),
            [('b2', None), ('s3', None), ('./local-save.sh', None)],
        )
        self.assertEqual(parse_storage_str(
            'b2,b2:onebuck/,b2://twobucks,s3://fitty,local:/home/user/'),
            [('b2', None), ('b2', 'onebuck'), ('b2', 'twobucks'), ('s3', 'fitty'), ('local', '/home/user')],
        )

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
