[![Build Status](https://github.com/sz3/pog/workflows/ci/badge.svg)](https://github.com/sz3/pog/actions?query=workflow%3Aci)
[![Coverage Status](https://coveralls.io/repos/github/sz3/pog/badge.svg?branch=master)](https://coveralls.io/github/sz3/pog?branch=master)
[![PyPI Version](https://img.shields.io/pypi/v/pogcli.svg)](https://pypi.python.org/pypi/pogcli)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/pogcli.svg)](https://pypi.python.org/pypi/pogcli)

## Pretty Ok Gncryption

* File encryption and backups!
* Uses [`libmcleece`](https://github.com/sz3/pymcleece) (a variation of `libsodium`'s `crypto_sealedbox`) and `zstandard`!
* Chunks up large files!
* Can be used to generate encrypted archives (or backups) to a local directory -- including a shared mount, or to push directly to a few cloud storage providers. (`s3`, `b2`, ...tbd)
* There is a GUI: [pogui](https://github.com/sz3/pogui).

Pog is a tool for paranoid, incremental backups. We might have 200 files today, 210 tomorrow, and 220 the next day (but some may be deleted!).

This tool is built around asymmetric encryption -- to use it, we first generate a public+private keypair. The idea is that we will use our "public" key for automated backups -- though we still don't really want to advertise it! Our private (or "secret") key will be kept somewhere safe, and only used when we need to restore our backup.

From a technical standpoint, the construct used is libmcleece's `mcleece_crypto_box_seal`, which is the post-quantum `Classic McEliece` + `x25519` + `xsalsa20poly1305` for encoding a per-file secret, and `crypto_secretbox` (encrypting the data using the secret).

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
* Pog does not manage cloud storage credentials -- it asks that we configure our environment with API keys before use.
	* To validate s3 credentials:
		* `awscli ls <bucket_name>`
	* To validate b2 credentials:
		* `b2 ls <bucket_name>`

### Generating a keypair
```
pog-create-keypair
```
* *.encrypt is used for creating archives.
* *.decrypt is used for extracting them (and should be kept somewhere safe)

### Creating cloud archives and backups

* Consider an S3 backup:

```
pog /home/user/my_file.txt --encrypt=/home/user/secret.encrypt --save-to=s3://my-bucket --store-absolute-paths
```

This does a few things:
1. `my_file.txt` is encrypted with `secret.encrypt`. If the file is sufficiently large, it is split into multiple chunks during encryption.
2. The encrypted contents ("blob") of `my_file.txt` are saved to the s3 bucket `my-bucket`, under the top-level `data/` subdirectory.
3. An encrypted "manifest" file is created, named according to the time the archive was created. This manifest file acts as an index from filenames (`/home/user/my_file`) to one or more encrypted blobs.
   a. The `--store-absolute-paths` flag tells the manifest to resolve ambiguous paths with the absolute path (`/home/user/my_file`) instead of the relative path (`my_file`). This can be useful to have when extracting archives or backups.
4. The manifest file is also saved to `my-bucket` in s3.

----

* Here is another example, with a series of directories:

```
pog /opt/games /opt/apps /opt/music --encrypt=secret.encrypt --save-to=s3://my-bucket,b2://my-b2-bucket
```

* This will recursively go through those 3 directories, gathering up all files and saving the encrypted data to both s3 and b2.

The command line help (`pog -h`) shows other useful examples.

### Creating local archives

* It is also possible to use Pog to encrypt a single file.

```
pog --encrypt=secret.encrypt /home/myfile.original > outputs.txt
```

* and to decrypt:

```
pog --decrypt=secret.decrypt $(cat outputs.txt) > myfile.copy
```

### Reading archives and backups

For a given manifest file (`2020-01-23T12:34:56.012345.mfn`), we can download and extract the archive like so:

```
pog --decrypt=secret.decrypt s3:/my-bucket/2020-01-23T12:34:56.012345.mfn
```

* If a local manifest file is provided, it is assumed that the data blobs are already downloaded into the working directory.

## Algorithm

* files are compressed with `zstandard`, and split ("chunked") into blobs. The default chunk size is 50MB.

* blob contents are encrypted with `mcleece_crypto_box_seal`. This is a variation of `crypto_sealedbox` -- an asymmetric key exchange is used to encrypt a random 256 bit key *per-blob*. That random key is used to encrypt the data.

* the file->blob relationship is stored in an encrypted manifest file (`.mfn`), which also stores file metadata -- e.g. last modified time.
	* the `.mfn` can be thought of as the dictionary for the archive.
	* blobs *can* be decrypted without the manifest, *IF* the blob order is correct. However, only the file contents are stored in the blobs. The original file name and file metadata will not survive the trip.

* blobs are named by urlsafe base64(hmac(sha256(secret), content)). The "secret" is derived from the encryption (public) key.
	* the goal is to pseudo-randomize the names of the blobs, while still keeping them consistent for backups run with the same key.
	* we want to "leak" the content hash only to the extent it's necessary to save work on successive backups (e.g. "I don't need to reupload blob X, it already exists")
	* because we use the content hash for this purpose, we can achieve some amount of file de-duplication.

## Disclaimer

I'm a not a cryptographer, just an engineer with internet access.
