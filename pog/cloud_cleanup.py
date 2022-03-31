#!/usr/bin/python3

"""Cleanup script for pog cloud backups.

In beta. Use at your own peril.

Usage:
  pog-cleanup --encrypt=<filename> [--backup=<b2|s3|..>] [--reckless-abandon] [--exp-similarity-check]
  pog-cleanup (-h | --help)

Examples:
  python -m pog.cloud_cleanup --encryption-keyfile=pki.encrypt --backup=s3

Options:
  -h --help                        Show this help.
  --version                        Show version.
  --encrypt=<filename>             Keyfile for encryption -- <filename> contains the (binary) public key.
  --backup=<b2|s3|filename|...>    Cloud service (s3, b2) to scrutinize.
  --reckless-abandon               Delete files.
  --exp-similarity-check           Attempt to clean up old backups if newer ones seem to supercede them. (experimental!)
"""

from collections import defaultdict
from dateutil import parser as dateutil_parse
from itertools import combinations
from os.path import basename, join as path_join
from tempfile import TemporaryDirectory

from docopt import docopt

from pog.cli import PogCli
from pog.lib.blob_store import parse_storage_str
from pog.fs.pogfs import get_cloud_fs


def get_blobs(local_mfn, config):
    cl = PogCli(config)
    return set(cl.dumpManifestIndex(local_mfn))


def obsolete_by_manifest_name(mfns, blobs):
    # group common prefixes together
    groups = defaultdict(list)
    for mfn in mfns:
        if not mfn.endswith('.mfn'):
            continue

        # path will be "xyz-2020-10-26T02:00:06.995497.mfn"
        # we want the date
        splits = mfn[:-4].rsplit('-')
        dt_str = '-'.join(splits[-3:])
        try:
            dateutil_parse.parse(dt_str)
        except:  # not a date?
            continue

        label = splits[0]
        if len(splits) == 3 or label == '':
            continue
        groups[label].append(mfn)

    obsoleted_by = defaultdict(set)
    for label, ms in groups.items():
        max_mfn = sorted(ms)[-1]
        for mfn in ms:
            if mfn != max_mfn:
                obsoleted_by[mfn].add(max_mfn)
    return obsoleted_by


def obsolete_by_similarity(mfns, blobs):
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

    for f in obsoleted_by.keys():
        print('would remove {} (similarity)'.format(f))
    return obsoleted_by


def _obsolete(config, fs, which='manifest_name'):
    with TemporaryDirectory() as tempdir:
        mfns = sorted([f for f in fs.list_files(recursive=False) if f.endswith('.mfn')])
        for mfn in mfns:
            fs.download_file(path_join(tempdir, mfn), mfn)

        # construct chains
        blobs = {}
        for mfn in mfns:
            local_path = path_join(tempdir, mfn)
            blobs[mfn] = get_blobs(local_path, config)

        obsoleted_by = obsolete_by_manifest_name(mfns, blobs)
        if which == 'similarity':
            obsoleted_by.update(obsolete_by_similarity(mfns, blobs))

        print('***')
        print(obsoleted_by)

        final_mfns = set(mfn for mfn in mfns if not obsoleted_by[mfn])
        print('***')
        print('final list:')
        print(final_mfns)

        for mfn in mfns:
            if mfn not in final_mfns:
                yield mfn

        blobs_to_keep = set()
        for m, b in blobs.items():
            if m in final_mfns:
                blobs_to_keep |= b

        print(len(blobs_to_keep))

        for blob in fs.list_files('data/', recursive=True):
            if basename(blob) in blobs_to_keep:
                continue
            yield blob


def check_for_obsolete_data(config, fs, reckless_abandon=False, similarity_check=False):
    similarity_check = 'similarity' if similarity_check else 'manifest_name'
    obsolete = list(_obsolete(config, fs, similarity_check))
    for filename in obsolete:
        print('would remove {}'.format(filename))
        if reckless_abandon:
            fs.remove_file(filename)


def main():
    args = docopt(__doc__, version='Pog Cloud Cleanup 0.0')

    config = {}
    for opt in ['encrypt']:
        enc = args.get('--{}'.format(opt))
        if enc:
            config[opt] = enc

    target, bucket = parse_storage_str(args.get('--backup'))[0]
    fs = get_cloud_fs(target)(bucket)

    reckless_abandon = args['--reckless-abandon']
    similarity_check = args['--exp-similarity-check']

    check_for_obsolete_data(config, fs, reckless_abandon, similarity_check)


if __name__ == '__main__':
    main()
