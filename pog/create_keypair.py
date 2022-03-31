#!/usr/bin/python3

# create and store a Curve25519 keypair for use by the encryptor

from os import chmod
from stat import S_IREAD, S_IRGRP

from mcleece.crypto_box import PrivateKey, PublicKey


def generate(filename):
    secret_key, public_key = PrivateKey.generate()
    decryption_keyfile = '{}.decrypt'.format(filename)
    with open(decryption_keyfile, 'wb') as f:
        f.write(bytes(secret_key))
    chmod(decryption_keyfile, S_IREAD)

    encryption_keyfile = '{}.encrypt'.format(filename)
    with open(encryption_keyfile, 'wb') as f:
        f.write(bytes(public_key))
    chmod(encryption_keyfile, S_IREAD | S_IRGRP)

    return encryption_keyfile, decryption_keyfile


def main():
    enc, dec = generate('pki')
    print('`{}` contains the (public) key for encryption'.format(enc))
    print('`{}` contains the (private) key for decryption'.format(dec))
    print('Keep it secret. Keep it safe.')


if __name__ == '__main__':
    main()
