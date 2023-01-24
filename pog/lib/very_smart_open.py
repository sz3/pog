from os import path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

from pog.fs.pogfs import get_cloud_fs
from pog.lib.blob_store import data_path


def _find_local(filename):
    # check in a few places
    for fn in [filename, data_path(filename)]:
        if path.exists(fn):
            return fn
    # give up
    return None


def very_smart_open(filename, *args):
    # ok so it's not that smart. I'll likely write a wrapper for smart_open, but not yet
    parsed = urlparse(filename)
    target = parsed.scheme
    bucket = parsed.netloc

    # if it's already here, don't dl it
    local = _find_local(path.basename(filename))
    if local:
        return open(local, *args)

    try:
        fs = get_cloud_fs(target)(bucket)
    except TypeError:  # not a real fs, treat it as a local filename
        return open(filename, *args)

    is_mfn = filename.endswith('.mfn')
    suffix = '.mfn' if is_mfn else ''

    remote_path = parsed.path.strip('/')
    if not is_mfn:
        remote_path = data_path(remote_path)

    f = NamedTemporaryFile(suffix=suffix)
    local_path = f.name
    fs.download_file(local_path, remote_path)
    f.seek(0)
    return f
