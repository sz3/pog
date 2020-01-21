from os import path
from shutil import copyfile
from subprocess import check_output
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

from pog.fs.pogfs import get_cloud_fs


class BlobStore():
    def __init__(self, save_to=None):
        self.save_to = [t.strip() for t in save_to.split(',')] if save_to else None
        self.target = None
        self.bucket = None

    def __enter__(self):
        self._tempdir = TemporaryDirectory()
        return self

    def __exit__(self, type, value, traceback):
        with self._tempdir:
            pass

    @property
    def tempdir(self):
        return self._tempdir.name if hasattr(self, '_tempdir') else None

    def data_path(self, blob_name):
        return 'data/{}/{}'.format(blob_name[0:2], blob_name)

    def save(self, name, temp_path):
        if not self.save_to:
            name = path.basename(name)
            copyfile(temp_path, name)
            return

        for target in self.save_to:
            fs = get_cloud_fs(target)
            if not fs:
                check_output([target, name, temp_path])
                continue

            fs = fs()
            if not fs.exists(name):
                fs.upload_file(temp_path, name)

    def save_blob(self, blob_name, temp_path):
        full_name = self.data_path(blob_name)
        self.save(full_name, temp_path)

    def download_if_necessary(self, filename):
        parsed = urlparse(filename)
        self.target = self.target or parsed.scheme
        self.bucket = self.bucket or parsed.netloc
        if not self.target:  # just a filename
            return filename

        local_path = path.join(self.tempdir, path.basename(parsed.path))
        remote_path = parsed.path.strip("/")
        if not filename.endswith('.mfn'):
            remote_path = self.data_path(remote_path)

        fs = get_cloud_fs(self.target)(self.bucket)
        print('local: {}, remote: {}'.format(local_path, remote_path))
        fs.download_file(local_path, remote_path)
        return local_path
