from os import remove
from pathlib import Path
from shutil import copyfile

from .pogfs import Pogfs


class localfs(Pogfs):
    def exists(self, remote_path):
        return Path(remote_path).exists()

    def upload_file(self, local_path, remote_path):
        copyfile(local_path, remote_path)

    def download_file(self, local_path, remote_path):
        copyfile(remote_path, local_path)

    def remove_file(self, remote_path):
        remove(remote_path)

    def list_files(self, remote_path='', recursive=False):
        globstr = '**/*' if recursive else '*'
        files = [str(f) for f in Path(remote_path).glob(globstr)]
        return sorted(files)
