from os import path
from shutil import copyfile
from subprocess import check_output
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

from pog.fs.pogfs import get_cloud_fs


class FileList():
    def __init__(self, *args, **kwargs):
        self.bs = kwargs.get('bs')
        self.filenames = args

    def __iter__(self):
        self.it = iter(self.filenames)
        self.current_file = None
        return self

    def __next__(self):
        if self.current_file:
            with self.current_file:
                pass
        try:
            filename = next(self.it)
            if self.bs:
                filename, self.current_file = self.bs.download_if_necessary(filename)
            return filename
        except StopIteration:
            raise


class BlobStore():
    def __init__(self, save_to=None):
        self.save_to = [t.strip() for t in save_to.split(',')] if save_to else None
        self.target = None
        self.bucket = None

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
            return filename, None

        is_mfn = filename.endswith('.mfn')
        suffix = '.mfn' if is_mfn else ''

        remote_path = parsed.path.strip("/")
        if not is_mfn:
            remote_path = self.data_path(remote_path)

        f = NamedTemporaryFile(suffix=suffix)
        local_path = f.name
        fs = get_cloud_fs(self.target)(self.bucket)
        fs.download_file(local_path, remote_path)
        print('local: {}, remote: {}'.format(local_path, remote_path))
        return local_path, f
