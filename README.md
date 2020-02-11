[![Build Status](https://travis-ci.org/sz3/pog.svg?branch=master)](https://travis-ci.org/sz3/pog)
[![Coverage Status](https://coveralls.io/repos/github/sz3/pog/badge.svg?branch=master)](https://coveralls.io/github/sz3/pog?branch=master)
[![PyPI Version](https://img.shields.io/pypi/v/pogcli.svg)](https://pypi.python.org/pypi/pogcli)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/pogcli.svg)](https://pypi.python.org/pypi/pogcli)

## Pretty Ok Gncryption

* File encryption and backups!
* Uses `nacl.SecretBox` and `zstandard`!
* Chunks up large files!
* Can be used to generate encrypted archives locally, or as a backup tool that pushes to cloud storage providers. (`s3`, `b2`, ...tbd)

This tool is built around symmetric encryption -- specifically `crypto_secretbox`, which is `xsalsa20poly1305`. Doing asymmetric PGP-like things is not in the cards -- but there is an experimental use case using asymmetric crypto that will likely be supported.

* Still in beta!
* Don't rely on this to keep your government leaks secret!

## Installation

Use `pip`:
```
pip install pogcli
```

or from source,
```
python setup.py build
python setup.py install
```

## Usage

(WIP)

## Algorithm

* files are compressed with `zstandard`, and split ("chunked") into blobs. The default chunk size is 50MB.

* blob contents are encrypted with `crypto_secretbox`. The key is 256 bits, independent *per-blob*, and stored in the blob header.

* the blob header is encrypted in one of 3 ways:
	* `crypto_secretbox` with key=sha256(argon2.ID with `time_cost=8, memory_cost=102400, parallelism=8, hash_len=32`)
		* this is what is used when you get a password prompt
	* `crypto_secretbox` with key=sha256(keyfile contents)
		* this is what the `--keyfile` option does
	* `crypto_sealedbox` with an X25519 key pair
		* this is what `--decryption-keyfile` and `--encryption-keyfile` do
		* an X25519 key pair can be generated with pog-create-keypair.

* the file->blob relationship is stored in an encrypted manifest file (`.mfn`), which also stores file metadata -- e.g. last modified time.
	* the `.mfn` can be thought of as the dictionary for the archive.
	* blobs *can* be decrypted without the manifest, *IF* the blob order is correct. However, only the file contents are stored in the blobs. The original file name and file metadata will not survive the trip.

* blobs are named by urlsafe base64(sha256(sha256(secret) + sha256(content)). The "secret" is derived from the encryption key.
	* the goal is to pseudo-randomize the names of the blobs, while still keeping them consistent for backups run with the same key.
	* we want to "leak" the content hash only to the extent it's necessary to save work on successive backups (e.g. "I don't need to reupload blob X, it already exists")
	* because we use the content hash for this purpose, we can achieve some amount of file de-duplication.


## Disclaimer

I'm a not a cryptographer, just an engineer with internet access.
