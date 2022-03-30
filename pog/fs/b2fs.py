import re
import sys
from os import environ
from subprocess import check_output

from b2sdk.v2 import B2Api
from b2sdk.exception import FileNotPresent

from .pogfs import Pogfs


BUCKET_NAME = environ.get('B2_BUCKET_NAME')


class b2fs(Pogfs):
    def __init__(self, bucket_name=None, **kwargs):
        self.bucket_name = bucket_name or BUCKET_NAME

    def _get_bucket(self):
        api = B2Api()
        return api.get_bucket_by_name(self.bucket_name)

    def exists(self, remote_path):
        buck = self._get_bucket()
        try:
            info = buck.get_file_info_by_name(remote_path)  # it's a b2sdk.file_version.DownloadVersion, fwiw
        except FileNotPresent:
            return ''
        return info.id_

    def upload_file(self, local_path, remote_path):
        buck = self._get_bucket()
        buck.upload_local_file(local_path, remote_path)

    def download_file(self, local_path, remote_path):
        buck = self._get_bucket()
        dl = buck.download_file_by_name(remote_path)  #  b2sdk.v2.DownloadedFile
        dl.save_to(local_path)

    def remove_file(self, remote_path):
        file_id = self.exists(remote_path)
        if not file_id:
            return
        buck = self._get_bucket()
        buck.delete_file_version(file_id, remote_path)

    def list_files(self, remote_path='', pattern=None, recursive=False):
        # maybe handle wildcards too... e.g. "*.mfn"
        buck = self._get_bucket()

        res = []
        for entry in buck.ls(remote_path, recursive=recursive):
            res.append(entry[0].file_name)

        if pattern:
            res = [f for f in res if self._match(f, pattern)]
        return res
