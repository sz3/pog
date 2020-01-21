from os import path
from shutil import copyfile
from subprocess import check_output

from pog.fs.pogfs import get_cloud_fs


class BlobStore():
    def __init__(self, save_to=None):
        self.save_to = [t.strip() for t in save_to.split(',')] if save_to else None

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
        full_name = 'data/{}/{}'.format(blob_name[0:2], blob_name)
        self.save(full_name, temp_path)
