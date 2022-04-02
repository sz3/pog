#!/usr/bin/python3

"""Pretty Ok Gncryption
(the G is silent)

Usage:
  pog --encrypt=<filename> [--save-to=<b2|s3|script.sh|...>] [--chunk-size=<bytes>]
      [--compresslevel=<1-22>] [--concurrency=<1-N>] [--store-absolute-paths] [--label=<backup>] <INPUTS>...
  pog --decrypt=<filename> [--dump-manifest] [--consume] <INPUTS>...
  pog --encrypt=<filename> --dump-manifest-index <INPUTS>...
  pog (-h | --help)

Examples:
  pog --encrypt=pki.encrypt /path/to/myfile.original > outputs.txt
  pog --decrypt=pki.decrypt $(cat outputs.txt) > myfile.copy

  pog --encrypt=pki.encrypt /path/to/file* --save-to=s3://mybucket,b2://myotherbucket
  pog --encrypt=pki.encrypt --dump-manifest-index 2019-*
  pog --decrypt=pki.decrypt s3://mybucket/2019-10-31T12:34:56.012345.mfn
  pog --decrypt=pki.decrypt --consume 2019-10-31T12:34:56.012345.mfn

Options:
  -h --help                        Show this help.
  --version                        Show version.
  -l --label=<backup>              The prefix/label for the backup manifest file.
  --chunk-size=<bytes>             When encrypting, split large files into <chunkMB> size parts [default: 100MB].
  --compresslevel=<1-22>           Zstd compression level. [default: 6]
  --concurrency=<1-N>              How many threads to use for uploads. [default: 8]
  --consume                        Used with decrypt -- after decrypting a blob, delete it from disk to conserve space.
  --decrypt=<filename>             Decryption -- <filename> contains the (binary) private key.
  --encrypt=<filename>             Encryption -- <filename> contains the (binary) public key.
  --store-absolute-paths           Store files under their absolute paths (i.e. for backups)
  --save-to=<b2|s3|/script.sh|...> During encryption, where to save encrypted data. Can be a cloud service (s3, b2), or the
                                   path to a script to run with (<encrypted file name>, <temp file path>).
"""
import hmac
import sys
from base64 import urlsafe_b64encode
from collections import ChainMap
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from hashlib import sha256
from json import dumps, loads
from os import fdopen, makedirs, remove, utime, path, getenv
from tempfile import TemporaryDirectory, gettempdir

import zstandard as zstd
from mcleece.crypto_box import PrivateKey, PublicKey, SealedBox as mcleece_SealedBox
from nacl.secret import SecretBox as nacl_SecretBox
from nacl.utils import random as nacl_random
from docopt import docopt
from humanfriendly import parse_size

from pog.lib.blob_store import BlobStore, download_list
from pog.lib.local_file_list import local_file_list


MANIFEST_INDEX_BYTES = 4  # up to 4GB


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
    if box == nacl_SecretBox or isinstance(box, nacl_SecretBox):
        overhead = nacl_SecretBox.NONCE_SIZE + nacl_SecretBox.MACBYTES
    else:  # mcleece_SealedBox
        overhead = box.message_header_size()  # it's 314
    return overhead


def prepare_crypto_box(decryption_keyfile=None, encryption_keyfile=None):
    secret = None
    box = None

    if encryption_keyfile:
        with open(encryption_keyfile, 'rb') as f:
            secret = f.read()
        box = mcleece_SealedBox(PublicKey(secret))
        secret = sha256(secret).digest()

    if decryption_keyfile:
        with open(decryption_keyfile, 'rb') as f:
            dont_share_this_secret = f.read()
        private_key = PrivateKey(dont_share_this_secret)
        box = mcleece_SealedBox(private_key)

    return secret, box


def blobname(content, secret):
    content_hash = hmac.new(secret, content, sha256).digest()
    return urlsafe_b64encode(content_hash)


def _print_progress(count, total, filename):
    print('*** {}/{}: {}'.format(count, total, filename))


class Encryptor():
    def __init__(self, secret, crypto_box, chunk_size=100000000, compresslevel=6, concurrency=8,
                 store_absolute_paths=False, blob_store=None):
        self.secret = sha256(secret).digest()
        self.index_box = nacl_SecretBox(secret)
        self.box = crypto_box
        self.chunk_size = chunk_size
        self.compresslevel = compresslevel
        self.concurrency = concurrency
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
        ll = len(data)
        if ll < self.chunk_size:
            pad_length = ll % 256
            # 8 bytes for frame header, then pad
            padding = b'\x50\x2A\x4D\x18' + (pad_length).to_bytes(4, byteorder='little') + nacl_random(pad_length)
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

    def _write(self, f, data):
        data = self._pad_data(data)
        f.write(self.box.encrypt(data))

    def save_manifest(self, mfn, filename=None):
        if not filename:
            filename = '{}.mfn'.format(datetime.now().isoformat())

        with TemporaryDirectory(dir=_get_temp_dir()) as tempdir:
            temp_path = path.join(tempdir, filename)
            Manifest(self.box).save(temp_path, mfn, self.index_box, self.compresslevel)
            self.blob_store.save(filename, temp_path)
        return filename

    def generate_encrypted_blobs(self, filename):
        cctx = zstd.ZstdCompressor(level=self.compresslevel)
        td = TemporaryDirectory(dir=_get_temp_dir())
        with open(filename, 'rb') as f, cctx.stream_reader(f) as compressed_stream, td as tempdir:
            while True:
                data = compressed_stream.read(self.chunk_size)
                if not data:
                    break

                blob_name = blobname(data, self.secret).decode('utf-8')
                temp_path = path.join(tempdir, blob_name)
                with open(temp_path, 'wb') as f:
                    self._write(f, data)
                yield temp_path

    def encrypt_and_store_file(self, args):
        filename, current_count, total_count = args
        _print_progress(current_count+1, total_count+1, filename)
        outputs = []
        for temp_path in self.generate_encrypted_blobs(filename):
            blob_name = path.basename(temp_path)
            self.blob_store.save_blob(blob_name, temp_path)
            outputs.append(blob_name)
            print(blob_name)
        return {
            self.archived_filename(filename):
                {
                    'blobs': outputs,
                    'atime': path.getatime(filename),
                    'mtime': path.getmtime(filename),
                }
        }

    def encrypt(self, *inputs, mfn_filename=None):
        mfn = dict()
        all_inputs = local_file_list(*inputs)

        exe = ThreadPoolExecutor(max_workers=self.concurrency)
        args = [(filename, count, len(all_inputs)) for count, filename in enumerate(all_inputs)]
        mfn = exe.map(self.encrypt_and_store_file, args)
        mfn = dict(ChainMap(*mfn))  # smash the maps together
        mfn = dict(sorted(mfn.items()))

        mfn_filename = self.save_manifest(mfn, mfn_filename)
        _print_progress(len(all_inputs)+1, len(all_inputs)+1, mfn_filename)


class Manifest():
    HEADER_SIZE = _box_overhead(mcleece_SealedBox) + MANIFEST_INDEX_BYTES

    def __init__(self, crypto_box):
        self.box = crypto_box

    def _write_header(self, f, index_box, compressed_index_length):
        # index header
        payload_length = (compressed_index_length + _box_overhead(index_box)).to_bytes(MANIFEST_INDEX_BYTES, byteorder='big')
        index_header = index_box.encrypt(payload_length)
        assert len(index_header) == _box_overhead(index_box) + MANIFEST_INDEX_BYTES

        # manifest header
        pad_length = len(index_header) + compressed_index_length + _box_overhead(index_box)
        pad_length = pad_length.to_bytes(MANIFEST_INDEX_BYTES, byteorder='big')
        manifest_header = self.box.encrypt(pad_length)

        # write both. Order will be:
        # manifest header, index header, index, manifest
        f.write(manifest_header)
        f.write(index_header)

    def _mfn_get_all_blobs(self, mfn):
        for og_filename, info in mfn.items():
            yield from info['blobs']

    def save(self, filename, mfn, index_box, compresslevel=6):
        with open(filename, 'wb') as f:
            all_blobs = sorted(list(self._mfn_get_all_blobs(mfn)))
            index_bytes = dumps(all_blobs).encode('utf-8')
            index_bytes = _compress(index_bytes, compresslevel)

            # write header, then index
            self._write_header(f, index_box, len(index_bytes))
            bites = index_box.encrypt(index_bytes)
            f.write(bites)

            # then mfn data
            full_manifest_bytes = dumps(mfn).encode('utf-8')
            full_manifest_bytes = _compress(full_manifest_bytes, compresslevel)
            f.write(self.box.encrypt(full_manifest_bytes))

    def _read_header(self, f):
        header_bytes = f.read(self.HEADER_SIZE)
        pad_length = self.box.decrypt(header_bytes)
        assert len(pad_length) == MANIFEST_INDEX_BYTES
        pad_length = int.from_bytes(pad_length, 'big')
        return pad_length

    def load(self, filename):
        with open(filename, 'rb') as f:
            # read header
            pad_length = self._read_header(f)

            # discard manifest index
            f.read(pad_length)

            # read the full manifest
            data = f.read()
            json_bytes = _decompress(self.box.decrypt(data))
            return loads(json_bytes.decode('utf-8'))

    def show(self, *inputs, show_filenames=True):
        for filename in download_list(inputs):
            print('*** {}:'.format(filename), file=sys.stderr)
            mfn = self.load(filename)
            for og_filename, info in mfn.items():
                if show_filenames:
                    print('* {}:'.format(og_filename))
                for blob in info['blobs']:
                    print(blob)


class ManifestIndex():
    HEADER_SIZE = _box_overhead(nacl_SecretBox) + MANIFEST_INDEX_BYTES

    def __init__(self, secret=None):
        self.index_box = nacl_SecretBox(secret)

    def _read_index_header(self, f):
        header_ciphertext = f.read(self.HEADER_SIZE)
        header_bytes = self.index_box.decrypt(header_ciphertext)
        assert len(header_bytes) == MANIFEST_INDEX_BYTES
        payload_length = int.from_bytes(header_bytes, 'big')
        return payload_length

    def load(self, filename):
        with open(filename, 'rb') as f:
            # skip first header
            f.read(Manifest.HEADER_SIZE)
            # then read the real deal
            payload_len = self._read_index_header(f)
            data = f.read(payload_len)
            json_bytes = _decompress(self.index_box.decrypt(data))
            return loads(json_bytes.decode('utf-8'))

    def show(self, *inputs):
        for filename in download_list(inputs):
            print('*** {}:'.format(filename), file=sys.stderr)
            mfn_index = self.load(filename)
            for blob in mfn_index:
                print(blob)


class Decryptor():
    def __init__(self, crypto_box, consume=False):
        self.box = crypto_box
        self.consume = consume

    def load_manifest(self, filename):
        return Manifest(self.box).load(filename)

    def decrypt_single_blob(self, filename, out):
        with open(filename, 'rb') as f:
            data = f.read()
            # two level decrypt?
            out.write(self.box.decrypt(data))  # `out` handles decompression
        if self.consume:
            remove(filename)

    def dump_manifest(self, *inputs, show_filenames=True):
        Manifest(self.box).show(*inputs, show_filenames=show_filenames)

    def decrypt(self, *inputs):
        for filename, fs_info, partials in download_list(inputs, extract=True):
            decompressor = zstd.ZstdDecompressor()
            if filename.endswith('.mfn'):
                mfn = self.load_manifest(filename)
                for count, (og_filename, info) in enumerate(mfn.items()):
                    if partials and og_filename not in partials:
                        continue
                    copy_filename = path.normpath('./{}'.format(og_filename))
                    dir_path = path.dirname(copy_filename)
                    if dir_path:
                        makedirs(dir_path, exist_ok=True)
                    with open(copy_filename, 'wb') as f, decompressor.stream_writer(f) as decompress_out:
                        for blob in download_list(info['blobs'], fs_info=fs_info):
                            self.decrypt_single_blob(blob, out=decompress_out)
                    utime(copy_filename, times=(info['atime'], info['mtime']))
                    # print progress to stdout
                    _print_progress(count+1, len(mfn), og_filename)
                if self.consume:
                    remove(filename)
            else:
                with decompressor.stream_writer(_stdout()) as decompress_out:
                    self.decrypt_single_blob(filename, out=decompress_out)


def main():
    args = docopt(__doc__, version='Pog 0.3.0a')
    chunk_size = parse_size(args.get('--chunk-size'))
    compresslevel = int(args.get('--compresslevel'))
    concurrency = int(args.get('--concurrency'))
    store_absolute_paths = args.get('--store-absolute-paths')

    secret, crypto_box = prepare_crypto_box(args.get('--decrypt'), args.get('--encrypt'))

    decrypt = (
        args.get('--dump-manifest') or
        args.get('--decrypt')
    )
    if decrypt:
        consume = args.get('--consume')
        d = Decryptor(crypto_box, consume)
        if args.get('--dump-manifest'):
            d.dump_manifest(*args['<INPUTS>'])
        else:
            d.decrypt(*args['<INPUTS>'])

    elif args.get('--dump-manifest-index'):
        mi = ManifestIndex(secret)
        mi.show(*args['<INPUTS>'])

    else:
        backup_label = args.get('--label')
        mfn_filename = None if not backup_label else '{}-{}.mfn'.format(backup_label, datetime.now().isoformat())
        bs = BlobStore(args.get('--save-to'))
        en = Encryptor(secret, crypto_box, chunk_size, compresslevel, concurrency, store_absolute_paths, bs)
        en.encrypt(*args['<INPUTS>'], mfn_filename=mfn_filename)


if __name__ == '__main__':
    main()
