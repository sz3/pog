from os import environ
from subprocess import check_output

from ..pogfs import Pogfs


BUCKET_NAME = environ.get('B2_BUCKET_NAME')


def _run_command(*args, **kwargs):
    full_args = ['b2'] + list(args)
    outputs = check_output(full_args, **kwargs).strip()
    return outputs.decode('utf-8')


'''
That this class shells out to the command line utility is not great.
However, it feels like the command line api is as just as likely to be stable as the underlying python code?
It's also marginally easier to use.
It would be nice if B2 had a better api.
'''
class b2fs(Pogfs):
    def __init__(self, bucket_name=None):
        self.bucket_name = bucket_name or BUCKET_NAME

    def exists(self, remote_path):
        res = _run_command('list-file-names', self.bucket_name, remote_path, '1')
        test_str = '"fileName": "{}"'.format(remote_path)
        return test_str in res

    def download_file(self, remote_path, local_path):
        res = _run_command('download-file-by-name', self.bucket_name, remote_path, local_path)
        print(res)

    def remove_file(self, remote_path):
        file_id = self.exists(remote_path)
        if not file_id:
            return True
        res = _run_command('delete-file-version', remote_path, file_id)
        print(res)

    def list_files(self, remote_path='', recursive=True):
        # maybe handle wildcards too... e.g. "*.mfn"
        recursive_flag = '--recursive' if recursive else ''
        path_args = [remote_path] if remote_path else []
        res = _run_command('ls', recursive_flag, self.bucket_name, *path_args)
        if not res:
            return []
        return res.split()
