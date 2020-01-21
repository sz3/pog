#!/usr/bin/python3

"""Pretty Ok Gncryption
(the G is silent)

Usage:
  pog.py <INPUTS>...
  pog.py [--keyfile=<filename> | --encryption-keyfile=<filename>] [--save-to=<b2|s3|filename|...>] [--chunk-size=<bytes>]
         [--compresslevel=<1-22>] [--store-absolute-paths] <INPUTS>...
  pog.py [--keyfile=<filename> | --decryption-keyfile=<filename>] [--decrypt | --dump-manifest] [--consume] <INPUTS>...
  pog.py [--keyfile=<filename> | --decryption-keyfile=<filename> | --encryption-keyfile=<filename>] [--dump-manifest-index] <INPUTS>...
  pog.py (-h | --help)

Examples:
  python -m pog.pog /path/to/file1 /path/to/file2 ...
  python -m pog.pog --chunk-size=50MB bigfile
  python -m pog.pog --decrypt 2019-10-31T12:34:56.012345.mfn

  python -m pog.pog /home/myfile.original > outputs.txt
  python -m pog.pog --decrypt $(cat outputs.txt) > myfile.copy

  python -m pog.pog --encryption-keyfile=pki.encrypt /path/to/file*
  python -m pog.pog --decryption-keyfile=pki.decrypt --consume 2019-10-31T12:34:56.012345.mfn
  python -m pog.pog --encryption-keyfile=pki.encrypt --dump-manifest-index 2019-*

Options:
  -h --help                        Show this help.
  --version                        Show version.
  --chunk-size=<bytes>             When encrypting, split large files into <chunkMB> size parts [default: 100MB].
  --compresslevel=<1-22>           Zstd compression level during encryption. [default: 3]
  --consume                        Used with decrypt -- after decrypting a blob, delete it from disk to conserve space.
  --decrypt                        Decrypt instead.
  --decryption-keyfile=<filename>  Use asymmetric decryption -- <filename> contains the (binary) private key.
  --encryption-keyfile=<filename>  Use asymmetric encryption -- <filename> contains the (binary) public key.
  --keyfile=<filename>             Instead of prompting for a password, use file contents as the secret.
  --store-absolute-paths           Store files under their absolute paths (i.e. for backups)
  --save-to=<b2|s3|filename|...>   During encryption, where to save encrypted data. Can be a cloud service (s3, b2), or the path
                                   to a script to run with (<encrypted file name>, <temp file path>).
"""
import sys
from base64 import urlsafe_b64encode
from datetime import datetime
from getpass import getpass
from hashlib import sha256
from json import dumps, loads
from os import fdopen, makedirs, remove, utime, path
from tempfile import TemporaryDirectory, gettempdir

import zstandard as zstd
from nacl.secret import SecretBox as nacl_SecretBox
from nacl.public import PrivateKey, PublicKey, SealedBox as nacl_SealedBox
from nacl.utils import random as nacl_random
from docopt import docopt
from humanfriendly import parse_size

from pog.lib.blob_store import BlobStore


KEY_SIZE = 32  # 256 bits
MANIFEST_INDEX_BYTES = 4  # up to 4GB -- only enforced for asymmetric encryption


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
        if path.exists(d):
            return d


def _compress(bites, compresslevel):
    params = zstd.ZstdCompressionParameters.from_level(compresslevel)
    cctx = zstd.ZstdCompressor(compression_params=params)
    return cctx.compress(bites)


def _decompress(bites):
    cctx = zstd.ZstdDecompressor()
    return cctx.decompress(bites)


def _box_overhead(box):
    if isinstance(box, nacl_SecretBox):
        overhead = box.NONCE_SIZE + box.MACBYTES
    else:  # nacl_SealedBox
        overhead = 48
    return overhead


def _header_size(box):
    return KEY_SIZE + _box_overhead(box)


def get_asymmetric_encryption(decryption_keyfile=None, encryption_keyfile=None):
    secret = None
    box = None

    if encryption_keyfile:
        with open(encryption_keyfile, 'rb') as f:
            secret = f.read()
        box = nacl_SealedBox(PublicKey(secret))

    if decryption_keyfile:
        with open(decryption_keyfile, 'rb') as f:
            dont_share_this_secret = f.read()
        private_key = PrivateKey(dont_share_this_secret)
        secret = bytes(private_key.public_key)
        box = nacl_SealedBox(private_key)

    return secret, box


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


class Encryptor():
    def __init__(self, secret, crypto_box=None, chunk_size=100000000, compresslevel=3, store_absolute_paths=False, blob_store=None):
        self.secret = secret
        self.index_box = nacl_SecretBox(secret)
        self.box = crypto_box or self.index_box
        self.chunk_size = chunk_size
        self.compresslevel = compresslevel
        self.store_absolute_paths = store_absolute_paths
        self.blob_store = blob_store or BlobStore()

    def _pad_data(self, data):
        '''
        We use zstd skippable frames to pad the data to a round number.
        Only applicable for data that is < chunk_size, since
        (1) chunk_size is already a nice round number,
        (2) we don't really want to pad the middle of the stream anyway

        ex:
        data = data + b'\x50\x2A\x4D\x18\x02\x00\x00\x00ab'
        '''
        l = len(data)
        if l < self.chunk_size:
            pad_length = l % 256
            # 8 bytes for frame header, then pad
            # (pad_length).to_bytes(4, byteorder='little')
            padding = b'\x50\x2A\x4D\x18' + bytes([pad_length, 0, 0, 0]) + nacl_random(pad_length)
            return data + padding
        return data

    def archived_filename(self, filename):
        '''
        for the moment we're doing some slightly weird stuff
        a more straightforward approach for filenaming might be useful later
        '''
        if self.store_absolute_paths:
            return path.abspath(filename)

        if path.isabs(filename) or '../' in filename:
            return path.basename(filename)

        # otherwise, relative path
        return filename

    def _write_header(self, f):
        file_key = nacl_random(KEY_SIZE)
        header = self.box.encrypt(file_key)
        assert len(header) == _header_size(self.box)
        f.write(header)

        file_box = nacl_SecretBox(file_key)
        return file_box

    def _write_index_header(self, f, data_length):
        payload_length = (data_length + _box_overhead(self.index_box)).to_bytes(MANIFEST_INDEX_BYTES, byteorder='big')

        file_key = nacl_random(KEY_SIZE)
        header = self.index_box.encrypt(payload_length + file_key)
        assert len(header) == _header_size(self.index_box) + MANIFEST_INDEX_BYTES
        f.write(header)

        file_box = nacl_SecretBox(file_key)
        return file_box

    def _write(self, f, data, manifest_index=False):
        data = self._pad_data(data)
        if manifest_index:
            file_box = self._write_index_header(f, len(data))
        else:
            file_box = self._write_header(f)
        f.write(file_box.encrypt(data))

    def _mfn_get_all_blobs(self, mfn):
        for og_filename, info in mfn.items():
            yield from info['blobs']

    def save_manifest(self, mfn, filename=None):
        if not filename:
            filename = '{}.mfn'.format(datetime.now().isoformat())

        with TemporaryDirectory(dir=_get_temp_dir()) as tempdir:
            temp_path = path.join(tempdir, filename)
            with open(temp_path, 'wb') as f:
                # store mfn index if needed
                if self.box != self.index_box:
                    all_blobs = sorted(list(self._mfn_get_all_blobs(mfn)))
                    index_bytes = dumps(all_blobs).encode('utf-8')
                    self._write(f, _compress(index_bytes, self.compresslevel), manifest_index=True)

                full_manifest_bytes = dumps(mfn).encode('utf-8')
                self._write(f, _compress(full_manifest_bytes, self.compresslevel))
            self.blob_store.save(filename, temp_path)

    def encrypt_single_file(self, filename):
        cctx = zstd.ZstdCompressor(level=self.compresslevel)
        with open(filename, 'rb') as f, cctx.stream_reader(f) as compressed_stream, TemporaryDirectory(dir=_get_temp_dir()) as tempdir:
            while True:
                data = compressed_stream.read(self.chunk_size)
                if not data:
                    break

                blob_name = blobname(data, self.secret).decode('utf-8')
                temp_path = path.join(tempdir, blob_name)
                with open(temp_path, 'wb') as f:
                    self._write(f, data)
                yield temp_path

    def encrypt(self, *inputs):
        mfn = dict()
        for filename in inputs:
            print('*** {}:'.format(filename), file=sys.stderr)
            outputs = []
            for temp_path in self.encrypt_single_file(filename):
                blob_name = path.basename(temp_path)
                self.blob_store.save_blob(blob_name, temp_path)
                outputs.append(blob_name)
                print(blob_name)
            if outputs:
                mfn[self.archived_filename(filename)] = {
                    'blobs': outputs,
                    'atime': path.getatime(filename),
                    'mtime': path.getmtime(filename),
                }
        self.save_manifest(mfn)


class Decryptor():
    def __init__(self, secret=None, crypto_box=None, consume=False, bs=None):
        self.index_box = nacl_SecretBox(secret)
        self.box = crypto_box or self.index_box
        self.consume = consume
        self.bs = bs

    def _read_index_header(self, f):
        header_ciphertext = f.read(_header_size(self.index_box) + MANIFEST_INDEX_BYTES)
        header_bytes = self.index_box.decrypt(header_ciphertext)
        assert len(header_bytes) == KEY_SIZE + MANIFEST_INDEX_BYTES
        payload_length = int.from_bytes(header_bytes[:MANIFEST_INDEX_BYTES], 'big')
        file_key = header_bytes[MANIFEST_INDEX_BYTES:]
        return payload_length, nacl_SecretBox(file_key)

    def load_manifest_index(self, filename):
        with open(filename, 'rb') as f:
            payload_len, file_box = self._read_index_header(f)
            data = f.read(payload_len)
            json_bytes = _decompress(file_box.decrypt(data))
            return loads(json_bytes.decode('utf-8'))

    def _read_header(self, f):
        header_bytes = f.read(_header_size(self.box))
        file_key = self.box.decrypt(header_bytes)
        assert len(file_key) == KEY_SIZE
        return nacl_SecretBox(file_key)

    def load_manifest(self, filename):
        with open(filename, 'rb') as f:
            if self.box != self.index_box:
                # toss the manifest index -- we don't need it
                index_header_len, _ = self._read_index_header(f)
                f.read(index_header_len)

            # read the full manifest
            file_box = self._read_header(f)
            data = f.read()
            json_bytes = _decompress(file_box.decrypt(data))
            return loads(json_bytes.decode('utf-8'))

    def decrypt_single_blob(self, filename, out):
        with open(filename, 'rb') as f:
            blob_box = self._read_header(f)
            data = f.read()
            out.write(blob_box.decrypt(data))  # `out` handles decompression
        if self.consume:
            remove(filename)

    def dump_manifest_index(self, *inputs):
        if self.box == self.index_box:
            self.dump_manifest(*inputs)
            return

        for filename in inputs:
            if self.bs:
                filename = self.bs.download_if_necessary(filename)
            print('*** {}:'.format(filename), file=sys.stderr)
            mfn_index = self.load_manifest_index(filename)
            for blob in mfn_index:
                print(blob)

    def dump_manifest(self, *inputs):
        for filename in inputs:
            if self.bs:
                filename = self.bs.download_if_necessary(filename)
            print('*** {}:'.format(filename), file=sys.stderr)
            mfn = self.load_manifest(filename)
            for og_filename, info in mfn.items():
                print('* {}:'.format(og_filename), file=sys.stderr)
                for blob in info['blobs']:
                    print(blob)

    def decrypt(self, *inputs):
        for filename in inputs:
            if self.bs:
                filename = self.bs.download_if_necessary(filename)  # probably merge this with self.consume somehow?
            decompressor = zstd.ZstdDecompressor()
            if filename.endswith('.mfn'):
                mfn = self.load_manifest(filename)
                for og_filename, info in mfn.items():
                    copy_filename = path.normpath('./{}'.format(og_filename))
                    dir_path = path.dirname(copy_filename)
                    if dir_path:
                        makedirs(dir_path, exist_ok=True)
                    with open(copy_filename, 'wb') as f, decompressor.stream_writer(f) as decompress_out:
                        for blob in info['blobs']:
                            if self.bs:
                                blob = self.bs.download_if_necessary(blob)
                            self.decrypt_single_blob(blob, out=decompress_out)
                    utime(copy_filename, times=(info['atime'], info['mtime']))
                if self.consume:
                    remove(filename)
            else:
                with decompressor.stream_writer(_stdout()) as decompress_out:
                    self.decrypt_single_blob(filename, out=decompress_out)


if __name__ == '__main__':
    args = docopt(__doc__, version='Pog 0.1')
    # print(args)

    chunk_size = parse_size(args.get('--chunk-size', '100MB'))
    compresslevel = int(args.get('--compresslevel', '3'))
    store_absolute_paths = args['--store-absolute-paths']

    secret, crypto_box = get_asymmetric_encryption(args.get('--decryption-keyfile'), args.get('--encryption-keyfile'))
    if not crypto_box and not secret:
        secret = get_secret(args.get('--keyfile'))

    with BlobStore(args.get('--save-to')) as bs:
        decrypt = args['--decrypt'] or args['--dump-manifest'] or args['--dump-manifest-index'] or args.get('--decryption-keyfile')
        if decrypt:
            consume = args['--consume']
            d = Decryptor(secret, crypto_box, consume, bs)
            if args['--dump-manifest']:
                d.dump_manifest(*args['<INPUTS>'])
            elif args['--dump-manifest-index']:
                d.dump_manifest_index(*args['<INPUTS>'])
            else:
                d.decrypt(*args['<INPUTS>'])
        else:
            en = Encryptor(secret, crypto_box, chunk_size, compresslevel, store_absolute_paths, bs)
            en.encrypt(*args['<INPUTS>'])
