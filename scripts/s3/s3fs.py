import boto3

from ..pogfs import Pogfs


class s3fs(Pogfs):
    def exists(self, remote_path):
        raise NotImplementedError()

    def download_file(self, remote_path, local_path):
        raise NotImplementedError()

    def remove_file(self, remote_path):
        raise NotImplementedError()

    def list_files(self, remote_path, recursive=False):
        raise NotImplementedError()
