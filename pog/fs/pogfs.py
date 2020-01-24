'''
Implemented per cloud storage service
'''


class Pogfs:
    def exists(self, remote_path):
        raise NotImplementedError()

    def upload_file(self, local_path, remote_path):
        raise NotImplementedError()

    def download_file(self, local_path, remote_path):
        raise NotImplementedError()

    def remove_file(self, remote_path):
        raise NotImplementedError()

    def list_files(self, remote_path='', recursive=False):
        raise NotImplementedError()


def get_cloud_fs(fs):
    FS = {
        'b2': b2fs,
        's3': s3fs,
        'test': localfs,
    }
    return FS.get(fs)


# these helper functions allow us to throw on failed dependencies iff it's appropriate
# for example, we might have the b2 package installed, but not boto3 -- and that's fine,
# until we ask for a file to go to s3 -- in which case we should get an error
def s3fs(*args, **kwargs):
    from .s3fs import s3fs as fs
    return fs(*args, **kwargs)


def b2fs(*args, **kwargs):
    from .b2fs import b2fs as fs
    return fs(*args, **kwargs)


def localfs(*args, **kwargs):
    from .localfs import localfs as fs
    return fs(*args, **kwargs)
