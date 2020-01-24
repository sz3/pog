#!/usr/bin/python3

"""Cleanup script for Pog's cloud backup functionality.

In beta. Use at your own peril.

Usage:
  pog-cleanup [--keyfile=<filename> | --decryption-keyfile=<filename> | --encryption-keyfile=<filename>]
              [--backup=<b2|s3|..>] [--reckless-abandon]
  pog-cleanup (-h | --help)

Examples:
  python -m pog.cloud_cleanup --encryption-keyfile=pki.encrypt --backup=s3

Options:
  -h --help                        Show this help.
  --version                        Show version.
  --decryption-keyfile=<filename>  Use asymmetric decryption -- <filename> contains the (binary) private key.
  --encryption-keyfile=<filename>  Use asymmetric encryption -- <filename> contains the (binary) public key.
  --keyfile=<filename>             Instead of prompting for a password, use file contents as the secret.
  --backup=<b2|s3|filename|...>    Cloud service (s3, b2) to scrutinize.
  --reckless-abandon               Delete files.
"""

from collections import defaultdict
from itertools import combinations
from os.path import basename, join as path_join
from tempfile import TemporaryDirectory

from docopt import docopt

from pog.cli import PogCli
from pog.fs.pogfs import get_cloud_fs


def get_blobs(local_mfn, config):
    cl = PogCli(config)
    return set(cl.dumpManifestIndex(local_mfn))


def doit(config, fs, reckless_abandon=False):
    with TemporaryDirectory() as tempdir:
        mfns = sorted([f for f in fs.list_files(recursive=False) if f.endswith('.mfn')])
        for mfn in mfns:
            fs.download_file(path_join(tempdir, mfn), mfn)

        # construct chains
        blobs = {}
        for mfn in mfns:
            local_path = path_join(tempdir, mfn)
            blobs[mfn] = get_blobs(local_path, config)

        obsoleted_by = defaultdict(set)
        for a, b in combinations(mfns, 2):
            same = len(blobs[a] and blobs[b])
            diff = len(blobs[a] ^ blobs[b])

            similarity = same / (same + diff)
            if similarity > .9:
                if a > b:
                    obsoleted_by[b].add(a)
                else:
                    obsoleted_by[a].add(b)
            print('{a} vs {b} similarity: {similarity}'.format(a=a, b=b, similarity=similarity))

        print('***')
        print(obsoleted_by)

        final_mfns = set(mfn for mfn in mfns if not obsoleted_by[mfn])
        print('***')
        print('final list:')
        print(final_mfns)

        for mfn in mfns:
            if mfn not in final_mfns:
                print('would remove {}'.format(mfn))
                if reckless_abandon:
                    fs.remove_file(mfn)

        blobs_to_keep = set()
        for m, b in blobs.items():
            if m in final_mfns:
                blobs_to_keep |= b

        print(len(blobs_to_keep))

        for blob in fs.list_files('data/', recursive=True):
            if basename(blob) in blobs_to_keep:
                continue
            print('would remove {}'.format(blob))
            if reckless_abandon:
                fs.remove_file(blob)


def main():
    args = docopt(__doc__, version='Pog Cloud Cleanup 0.0')

    config = {}
    for opt in ['encryption-keyfile', 'decryption-keyfile', 'keyfile']:
        enc = args.get('--{}'.format(opt))
        if enc:
            config[opt] = enc

    fs = get_cloud_fs(args.get('--backup'))()

    reckless_abandon = args['--reckless-abandon']

    doit(config, fs, reckless_abandon)


if __name__ == '__main__':
    main()
