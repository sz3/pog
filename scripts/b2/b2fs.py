from os import environ
from subprocess import check_output

from ..pogfs import Pogfs


BUCKET_NAME = environ.get('B2_BUCKET_NAME')


def _run_command(self, *args, **kwargs):
    full_args = ['echo', 'b2'] + list(args)
    return check_output(full_args, **kwargs).strip().decode('utf-8')


'''
That this class shells out to the command line utility is not great.
However, it feels like the command line api is as just as likely to be stable as the underlying python code?
It's also marginally easier to use.
It would be nice if B2 had a better api.
'''
class b2fs(Pogfs):
    def exists(self, remote_path):
        res = _run_command('list-file-names', BUCKET_NAME, remote_path, 1)
        print(res)

    def download_file(self, remote_path, local_path):
        res = _run_command('download-file-by-name', BUCKET_NAME, remote_path, local_path)
        print(res)

    def remove_file(self, remote_path):
        file_id = self.exists(remote_path)
        if not file_id:
            return True
        res = _run_command('delete-file-version', remote_path, file_id)
        print(res)

    def list_files(self, remote_path, recursive=False):
        # maybe handle wildcards too... e.g. "*.mfn"
        recursive_flag = '--recursive' if recursive else ''
        res = _run_command('ls', recursive_flag, BUCKET_NAME, remote_path)
        print(res)
