from os import remove
from pathlib import Path
from shutil import copyfile

from .pogfs import Pogfs


class localfs(Pogfs):
    def __init__(self, *args, **kwargs):
        self.root = kwargs.get('root', '')

    def exists(self, remote_path):
        return Path(self.root, remote_path).exists()

    def upload_file(self, local_path, remote_path):
        p = Path(self.root, remote_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        copyfile(local_path, p.resolve())

    def download_file(self, local_path, remote_path):
        p = Path(self.root, remote_path)
        copyfile(p.resolve(), local_path)

    def remove_file(self, remote_path):
        p = Path(self.root, remote_path)
        remove(p.resolve())

    def list_files(self, remote_path='', recursive=False):
        globstr = '**/*' if recursive else '*'
        p = Path(self.root, remote_path)
        files = [str(f) for f in p.glob(globstr)]
        return sorted(files)
