[![Build Status](https://travis-ci.org/sz3/pog.svg?branch=master)](https://travis-ci.org/sz3/pog)
[![Coverage Status](https://coveralls.io/repos/sz3/pog/badge.svg?branch=master&service=github)](https://coveralls.io/github/sz3/pog?branch=master)

### Pretty Ok Gncryption

File encryption and backups! Uses `nacl.SecretBox`! Chunks up files! Can be used to generate encrypted archives, or as a backup tool to s3/b2/(...tbd).

This tool is built around symmetric encryption (specifically `crypto_secretbox`, which is `xsalsa20poly1305`. Doing weird asymmetric PGP-like things is out of scope -- but there is an experimental use case using asymmetric crypto that will likely be supported.

Still in beta! Don't rely on it to keep your government leaks secret!