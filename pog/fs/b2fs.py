import re
import sys
from os import environ
from subprocess import check_output

from .pogfs import Pogfs


BUCKET_NAME = environ.get('B2_BUCKET_NAME')


def _run_command(*args, **kwargs):
    full_args = ['b2'] + list(args)
    outputs = check_output(full_args, **kwargs).strip()
    return outputs.decode('utf-8')


class b2fs(Pogfs):
    '''
    That this class shells out to the command line utility is not great.
    However, it feels like the command line api is as just as likely to be stable as the underlying python code?
    It's also marginally easier to use.
    It would be nice if B2 had a better api.
    '''
    def __init__(self, bucket_name=None, **kwargs):
        self.bucket_name = bucket_name or BUCKET_NAME

    def exists(self, remote_path):
        res = _run_command('list-file-names', self.bucket_name, remote_path, '1').split('\n')

        test_str = '"fileName": "{}"'.format(remote_path)
        success = False
        fileId = ''

        for line in res:
            if '"fileId"' in line:
                matches = re.findall(r'\"(.+?)\"', line)
                fileId = matches[1]
            if test_str in line:
                success = True
        return fileId if success else ''

    def upload_file(self, local_path, remote_path):
        res = _run_command('upload_file', self.bucket_name, local_path, remote_path)
        print(res, file=sys.stderr)

    def download_file(self, local_path, remote_path):
        res = _run_command('download-file-by-name', self.bucket_name, remote_path, local_path)
        print(res, file=sys.stderr)

    def remove_file(self, remote_path):
        file_id = self.exists(remote_path)
        if not file_id:
            return True
        res = _run_command('delete-file-version', remote_path, file_id)
        print(res, file=sys.stderr)

    def list_files(self, remote_path='', pattern=None, recursive=False):
        # maybe handle wildcards too... e.g. "*.mfn"
        recursive_arg = ['--recursive'] if recursive else []
        path_arg = [remote_path] if remote_path else []

        args = ['ls'] + recursive_arg + [self.bucket_name] + path_arg
        res = _run_command(*args)
        if not res:
            return []

        res = res.split()
        if pattern:
            res = [f for f in res if self._match(f, pattern)]
        return res
