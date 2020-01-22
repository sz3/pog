[![Build Status](https://travis-ci.org/sz3/pog.svg?branch=master)](https://travis-ci.org/sz3/pog)
[![Coverage Status](https://coveralls.io/repos/sz3/pog/badge.svg?branch=master&service=github)](https://coveralls.io/github/sz3/pog?branch=master)

### Pretty Ok Gncryption

* File encryption and backups!
* Uses `nacl.SecretBox` and `zstandard`!
* Chunks up large files!
* Can be used to generate encrypted archives locally, or as a backup tool that pushes to cloud storage providers. (`s3`, `b2`, ...tbd)

This tool is built around symmetric encryption (specifically `crypto_secretbox`, which is `xsalsa20poly1305`. Doing asymmetric PGP-like things is not in the cards -- but there is an experimental use case using asymmetric crypto that will likely be supported.

* Still in beta!
* Don't rely on this to keep your government leaks secret!
