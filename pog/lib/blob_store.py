from os import path
from shutil import copyfile
from subprocess import check_output
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

from collections import defaultdict
from pog.fs.pogfs import get_cloud_fs


def _data_path(blob_name):
    return 'data/{}/{}'.format(blob_name[0:2], blob_name)


def _flatten(*args):
    flatter = []
    for elem in args:
        if isinstance(elem, list) or isinstance(elem, tuple):
            flatter += elem
        else:
            flatter.append(elem)
    return flatter


class download_list():
    def __init__(self, *args, **kwargs):
        self.filenames = _flatten(*args)
        self.fs_info = kwargs.get('fs_info', [])
        self.partials = {}

        # `extract` mode does two things:
        # 1. iterator returns a tuple with fs_info in it
        # 2. consumes non-mfn arguments and returns them with the preceding mfn, if there is one
        self.extract = kwargs.get('extract', False)
        if self.extract:
            self.filenames, self.partials = self._determine_partials(self.filenames)

    def _determine_partials(self, filenames):
        if not self.extract:
            return

        partials = defaultdict(set)
        current_mfn = None
        for f in list(filenames):
            if f.endswith('.mfn'):
                current_mfn = f
                continue
            if not current_mfn:
                continue
            partials[current_mfn].add(f)
            filenames.remove(f)
        return filenames, dict(partials)

    def __iter__(self):
        self.it = iter(self.filenames)
        self.tempfile = None
        return self

    def __next__(self):
        if self.tempfile:
            with self.tempfile:
                pass
        try:
            filename = next(self.it)
            partials = self.partials.get(filename)

            filename, self.tempfile, fs_info = self._download_if_necessary(filename, *self.fs_info)
            return filename if not self.extract else (filename, fs_info, partials)
        except StopIteration:
            raise

    def _download_if_necessary(self, filename, target=None, bucket=None):
        parsed = urlparse(filename)
        target = target or parsed.scheme
        bucket = bucket or parsed.netloc
        if not target:  # just a filename
            return filename, None, []

        try:
            fs = get_cloud_fs(target)(bucket)
        except TypeError:  # not a real fs, treat it as a filename
            return filename, None, []

        is_mfn = filename.endswith('.mfn')
        suffix = '.mfn' if is_mfn else ''

        remote_path = parsed.path.strip('/')
        if not is_mfn:
            remote_path = _data_path(remote_path)

        f = NamedTemporaryFile(suffix=suffix)
        local_path = f.name
        fs.download_file(local_path, remote_path)
        return local_path, f, (target, bucket)


class BlobStore():
    def __init__(self, save_to=None):
        self.save_to = self._parse_save_to(save_to)

    def _parse_save_to(self, save_to=None):
        if not save_to:
            return None

        dests = []
        for line in save_to.split(','):
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
        full_name = _data_path(blob_name)
        self.save(full_name, temp_path)
