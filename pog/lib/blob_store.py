from os import path
from shutil import copyfile
from subprocess import check_output

from pog.fs.pogfs import get_cloud_fs


def data_path(blob_name):
    return 'data/{}/{}'.format(blob_name[0:2], blob_name)


def parse_storage_str(paths=None):
    if not paths:
        return None

    dests = []
    for line in paths.split(','):
        line = line.strip()
        if ':' not in line:  # scripts, etc
            d = (line, None)
        else:
            target, bucket = line.split(':', 1)
            if bucket.startswith('//'):
                bucket = bucket[2:]
            d = (target, bucket.rstrip('/'))
        dests.append(d)
    return dests


class BlobStore():
    def __init__(self, save_to=None):
        self.save_to = parse_storage_str(save_to)

    def save(self, name, temp_path):
        if not self.save_to:
            name = path.basename(name)
            copyfile(temp_path, name)
            return

        for target, bucket in self.save_to:
            fs = get_cloud_fs(target)
            if not fs:
                check_output([target, name, temp_path])
                continue

            fs = fs(bucket)
            if not fs.exists(name):
                fs.upload_file(temp_path, name)

    def save_blob(self, blob_name, temp_path):
        full_name = data_path(blob_name)
        self.save(full_name, temp_path)
