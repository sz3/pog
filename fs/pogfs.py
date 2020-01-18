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

    def list_files(self, remote_path='', recursive=True):
        raise NotImplementedError()


# these helper functions allow us to throw on failed dependencies iff it's appropriate
# for example, we might have the b2 package installed, but not boto3 -- and that's fine,
# until we ask for a file to go to s3 -- in which case we should get an error
def s3fs():
    from .s3fs import s3fs as fs
    return fs()


def b2fs():
    from .b2fs import b2fs as fs
    return fs()
