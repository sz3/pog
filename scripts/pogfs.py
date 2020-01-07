'''
Implemented per cloud storage service
'''

class Pogfs:
    def exists(self, remote_path):
        raise NotImplementedError()

    def download_file(self, remote_path, local_path):
        raise NotImplementedError()

    def remove_file(self, remote_path):
        raise NotImplementedError()

    def list_files(self, remote_path, recursive=False):
        raise NotImplementedError()
