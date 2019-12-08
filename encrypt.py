#!/usr/bin/python3

"""Encryptor

Usage:
  encrypt.py <INPUTS>...
  encrypt.py [--keyfile=<filename> | --encryption-keyfile=<filename>] [--upload-script=<filename>] [--chunk-size=<bytes>] [--compresslevel=<1-22>]
             [--padding=<bytes>] [--small-files] <INPUTS>...
  encrypt.py [--keyfile=<filename> | --decryption-keyfile=<filename>] [--decrypt] [--consume] <INPUTS>...
  encrypt.py (-h | --help)

Examples:
  python ../encrypt.py /path/to/file1 /path/to/file2 ...
  python ../encrypt.py --chunk-size=50MB bigfile
  python ../encrypt.py --decrypt 2019-10-31T12:34:56.012345.mfn

  python ../encrypt.py /home/myfile.original > outputs.txt
  python ../encrypt.py --decrypt $(cat outputs.txt) > myfile.copy

Options:
  -h --help                        Show this help.
  --version                        Show version.
  --chunk-size=<bytes>             When encrypting, split large files into <chunkMB> size parts [default: 100MB].
  --compresslevel=<1-22>           Zstd compression level during encryption. [default: 3]
  --consume                        Used with decrypt -- after decrypting a blob, delete it from disk to conserve space.
  --decrypt                        Decrypt instead.
  --encryption-keyfile=<filename>  Use asymmetric encryption -- <filename> contains the (binary) public key.
  --keyfile=<filename>             Instead of prompting for a password, use file contents as the secret.
  --padding=<bytes>                Padding in megabytes [default: 1MB].
  --small-files                    Pad small files to <power of 2> bytes
  --upload-script=<filename>       During encryption, external script to run with (<encrypted file name>, <temp file path>).
"""
import sys
from base64 import urlsafe_b64encode
from datetime import datetime
from getpass import getpass
from hashlib import sha256
from json import dumps, loads
from os import fdopen, remove, utime
from os.path import basename, getatime, getmtime, exists as path_exists, join as path_join
from shutil import copyfile
from subprocess import check_output
from tempfile import TemporaryDirectory, gettempdir

from nacl.secret import SecretBox as nacl_SecretBox
from nacl.public import SealedBox as nacl_SealedBox
from docopt import docopt
from humanfriendly import parse_size
from zstd import compress, decompress


stdoutfd = None

def _stdout():
    global stdoutfd
    if not stdoutfd:
        stdoutfd = fdopen(sys.stdout.fileno(), 'wb')
    return stdoutfd


def _get_temp_dir():
    # use ramdisk if possible
    dirs = ['/dev/shm', gettempdir()]
    for d in dirs:
        if path_exists(d):
            return d


def _get_crypto_box(secret):
    return nacl_SecretBox(secret)


def blobname(bites, secret):
    bites_hash = sha256(bites).digest()
    return urlsafe_b64encode(sha256(secret + bites_hash).digest())


def get_secret(keyfile=None):
    if keyfile:
        with open(keyfile, 'rb') as f:
            h = sha256()
            buffer = f.read(16384)
            while buffer:
                h.update(buffer)
                buffer = f.read(16384)
            return h.digest()

    # if keyfile failed, prompt for password
    while True:
        password = getpass()
        pass2 = getpass()
        if password != pass2:
            print('passwords did not match! Please try again.', file=sys.stderr)
            continue
        break
    return sha256(password.encode('utf-8')).digest()


class BlobStore():
    def __init__(self, upload_script=None, exists_script=None):
        self.upload_script = upload_script
        self.exists_script = exists_script

    def exists(self, name):
        # allows us to skip work for already uploaded files
        return False

    def upload(self, name, local_path):
        if not self.upload_script:
            copyfile(local_path, name)
            return
        check_output([self.upload_script, name, local_path])


class Encryptor():
    def __init__(self, secret, chunk_size, compresslevel, blob_store=None):
        self.secret = secret
        self.box = _get_crypto_box(self.secret)
        self.chunk_size = chunk_size
        self.compresslevel = compresslevel
        self.blob_store = blob_store or BlobStore()

    def save_manifest(self, mfn, filename=None):
        if not filename:
            filename = '{}.mfn'.format(datetime.now().isoformat())

        with open(filename, 'wb') as f:
            json_bytes = dumps(mfn).encode('utf-8')
            f.write(self.box.encrypt(compress(json_bytes, self.compresslevel)))

    def encrypt_single_file(self, filename):
        with open(filename, 'rb') as f, TemporaryDirectory(dir=_get_temp_dir()) as tempdir:
            data = f.read(chunk_size)
            while data:
                blob_name = blobname(data, self.secret).decode('utf-8')
                if self.blob_store.exists(blob_name):
                    continue
                target = path_join(tempdir, blob_name)
                with open(target, 'wb') as out:
                    out.write(self.box.encrypt(compress(data, self.compresslevel)))
                yield target
                data = f.read(self.chunk_size)

    def encrypt(self, *inputs):
        mfn = dict()
        for filename in inputs:
            print('*** {}:'.format(filename), file=sys.stderr)
            outputs = []
            for blob_path in self.encrypt_single_file(filename):
                blob_name = basename(blob_path)
                self.blob_store.upload(blob_name, blob_path)
                outputs.append(blob_name)
                print(blob_name)
            if outputs:
                mfn[filename] = {
                    'blobs': outputs,
                    'atime': getatime(filename),
                    'mtime': getmtime(filename),
                }
        self.save_manifest(mfn)


class Decryptor():
    def __init__(self, secret, consume=False):
        self.secret = secret
        self.box = _get_crypto_box(self.secret)
        self.consume = consume

    def load_manifest(self, filename):
        with open(filename, 'rb') as f:
            data = f.read()
            json_bytes = decompress(self.box.decrypt(data))
            return loads(json_bytes.decode('utf-8'))

    def decrypt_single_file(self, filename, out=None):
        if not out:
            out = _stdout()
        with open(filename, 'rb') as f:
            data = f.read()
            out.write(decompress(self.box.decrypt(data)))
        if self.consume:
            remove(filename)

    def decrypt(self, *inputs):
        for filename in inputs:
            if filename.endswith('.mfn'):
                mfn = self.load_manifest(filename)
                for og_filename, info in mfn.items():
                    copy_filename = basename(og_filename)
                    with open(copy_filename, 'wb') as f:
                        for blob in info['blobs']:
                            self. decrypt_single_file(blob, out=f)
                    utime(copy_filename, times=(info['atime'], info['mtime']))
                if self.consume:
                    remove(filename)
            else:
                self.decrypt_single_file(filename)


if __name__ == '__main__':
    args = docopt(__doc__, version='Encryptor 0.0')
    # print(args)

    chunk_size = parse_size(args.get('--chunk-size', '100MB'))
    compresslevel = int(args.get('--compresslevel', '3'))
    secret = get_secret(args.get('--keyfile', None))

    if args['--decrypt']:
        consume = args['--consume']
        d = Decryptor(secret, consume)
        d.decrypt(*args['<INPUTS>'])
    else:
        bs = BlobStore(args.get('--upload-script', None))
        en = Encryptor(secret, chunk_size, compresslevel, bs)
        en.encrypt(*args['<INPUTS>'])
