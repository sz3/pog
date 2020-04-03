[![Build Status](https://travis-ci.org/sz3/pog.svg?branch=master)](https://travis-ci.org/sz3/pog)
[![Coverage Status](https://coveralls.io/repos/github/sz3/pog/badge.svg?branch=master)](https://coveralls.io/github/sz3/pog?branch=master)
[![PyPI Version](https://img.shields.io/pypi/v/pogcli.svg)](https://pypi.python.org/pypi/pogcli)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/pogcli.svg)](https://pypi.python.org/pypi/pogcli)

## Pretty Ok Gncryption

* File encryption and backups!
* Uses `nacl.SecretBox` and `zstandard`!
* Chunks up large files!
* Can be used to generate encrypted archives locally, or as a backup tool that pushes to cloud storage providers. (`s3`, `b2`, ...tbd)
* There is a GUI: [pogui](https://github.com/sz3/pogui).

This tool is built around symmetric encryption -- specifically libsodium's `crypto_secretbox`, which is `XSalsa20+Poly1305`. Doing asymmetric PGP-like things is not in the cards -- but there is an experimental use case using asymmetric crypto that will likely be supported.

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

### Credentials
* Pog does not manage cloud storage credentials -- it asks that you configure your environment with API keys before use.
	a. To validate s3 credentials:
		* awscli ls <bucket_name>
	b. To validate b2 credentials:
		* b2 ls <bucket_name>

### Using a password or keyfiles
1. symmetric keyfile
	* any file can be used as a keyfile.
	* the contents of the keyfile will be hashed, and that hash will become the cryptographic key
	* cryptographic randomness (ex: 1024 bytes from /dev/urandom) is recommended
2. asymmetric keyfiles
	* the `pog-create-keypair` script will generate an "encrypt" and "decrypt" keypair.
	* encrypt is used for creating archives
	* decrypt is used for extracting them
3. Password entry
	* if no keyfiles are specified, Pog supports password entry for creating or reading archives

### Creating cloud archives and backups

* Consider an S3 backup:
`pog /home/user/my_file.txt --keyfile=/home/user/secret.keyfile --save-to=s3://my-bucket --store-absolute-paths`

This does a few things:
1. `my_file.txt` is encrypted with `secret.keyfile`. If the file is sufficiently large, it is split into multiple pieces during encryption.
2. The encrypted contents ("blob") of `my_file.txt` is saved to the s3 bucket `my-bucket`, under the top-level `data/` subdirectory.
3. An encrypted "manifest" file is created, named according to the time the archive was created. This manifest file acts as an index from filenames (`/home/user/my_file`) to one or more encrypted blobs.
   a. The `--store-absolute-paths` flag tells the manifest to resolve ambiguous paths with the absolute path (`/home/user/my_file`) instead of the relative path (`my_file`). This can be useful to have when extracting archives or backups.
4. The manifest file is also saved to `my-bucket` in s3.

----

* Here is another example, with a series of directories:
`pog /opt/games /opt/apps /opt/music --encryption-keyfile=secret.encrypt --save-to=s3://my-bucket,b2://my-b2-bucket`

* This will recursively go through those 3 directories, gathering up all files and saving the encrypted blobs to both s3 and b2.

The command line help shows other useful examples.

### Creating local archives

* It is also possible to use Pog to encrypt a single file.
`pog /home/myfile.original > outputs.txt`

* and to decrypt:
`pog --decrypt $(cat outputs.txt) > myfile.copy`

### Reading archives and backups

For a given manifest file (`2020-01-23T12:34:56.012345.mfn`), we can download and extract the archive like so:
`pog --decrypt s3:/my-bucket/2020-01-23T12:34:56.012345.mfn --keyfile=/home/user/secret.keyfile`

* The `--decrypt` flag should be specified for read+decrypt -- the default behavior is to write+encrypt.
* If a `--decryption-keyfile` is provided, `--decrypt` is assumed.
* If a local manifest file is provided, it is assumed that the data blobs are already downloaded into the working directory.

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
		* an X25519 key pair can be generated with `pog-create-keypair`.

* the file->blob relationship is stored in an encrypted manifest file (`.mfn`), which also stores file metadata -- e.g. last modified time.
	* the `.mfn` can be thought of as the dictionary for the archive.
	* blobs *can* be decrypted without the manifest, *IF* the blob order is correct. However, only the file contents are stored in the blobs. The original file name and file metadata will not survive the trip.

* blobs are named by urlsafe base64(sha256(sha256(secret) + sha256(content)). The "secret" is derived from the encryption key.
	* the goal is to pseudo-randomize the names of the blobs, while still keeping them consistent for backups run with the same key.
	* we want to "leak" the content hash only to the extent it's necessary to save work on successive backups (e.g. "I don't need to reupload blob X, it already exists")
	* because we use the content hash for this purpose, we can achieve some amount of file de-duplication.

## Disclaimer

I'm a not a cryptographer, just an engineer with internet access.
