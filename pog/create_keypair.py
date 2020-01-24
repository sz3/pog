#!/usr/bin/python3

# create and store a Curve25519 keypair for use by the encryptor

from os import chmod
from stat import S_IREAD, S_IRGRP

from nacl.public import PrivateKey


def generate(filename):
    secret_key = PrivateKey.generate()
    decryption_keyfile = '{}.decrypt'.format(filename)
    with open(decryption_keyfile, 'wb') as f:
        f.write(bytes(secret_key))
    chmod(decryption_keyfile, S_IREAD)

    encryption_keyfile = '{}.encrypt'.format(filename)
    with open(encryption_keyfile, 'wb') as f:
        f.write(bytes(secret_key.public_key))
    chmod(encryption_keyfile, S_IREAD | S_IRGRP)

    return encryption_keyfile, decryption_keyfile


def main():
    enc, dec = generate('pki')
    print('`{}` contains the key for encryption'.format(enc))
    print('`{}` contains the key for decryption'.format(dec))
    print(
        'The private key is in `{}`. It can be used to regenerate '
        'the "public" (encryption) key if necessary.'.format(dec)
    )
    print('Keep it secret. Keep it safe.')


if __name__ == '__main__':
    main()
