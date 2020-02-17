import glob
import os

'''
normalizes a list of files, dirs, and patterns into a list of files
'''
def local_file_list(*args, **kwargs):
    all_files = set()  # avoid dups
    for path in args:
        if os.path.isfile(path):
            all_files.add(path)
            continue

        if os.path.isdir(path):
            pattern = '{}/**/*'.format(path)
        else:
            pattern = path

        for filename in glob.iglob(pattern, recursive=True):
            if os.path.isfile(filename):
                all_files.add(filename)
    return sorted(all_files)
