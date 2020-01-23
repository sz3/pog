import argon2
from hashlib import sha256


def pass_to_hash(pw):
    # prompted passwords are likely to be weaker -> potentially brute-forceable. So we'll use a stronger hash algo.
    # the argon2 params here are based on the `argon2-cffi` defaults
    kindofasalt = sha256(pw.encode('utf-8')).digest()
    ar2 = argon2.low_level.hash_secret_raw(
        pw.encode('utf-8'), kindofasalt, time_cost=8, memory_cost=102400, parallelism=8, hash_len=32,
        type=argon2.low_level.Type.ID
    )
    return ar2
