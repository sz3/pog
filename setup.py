from os import path
from setuptools import setup, find_packages


here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='pogcli',
    license='MIT',
    url='https://github.com/sz3/pog',
    version='0.1.4',

    entry_points={
        'console_scripts': [
            'pog = pog.pog:main',
            'pog-create-keypair = pog.create_keypair:main',
            'pog-cleanup = pog.cloud_cleanup:main',
        ],
    },
    packages=find_packages(exclude=('tests', 'pogui')),
    package_data={
        'pog': ['scripts/*.sh'],
    },

    python_requires='>=3.6',
    install_requires=[
        'argon2-cffi>=19.2.0',
        'docopt>=0.6.2',
        'humanfriendly>=4.18',
        'PyNaCl>=1.3.0',
        'zstandard>=0.11.1',
    ],
    extras_require={
        'b2': ['b2'],
        's3': ['boto3'],
    },

    description='File encryption and backup utility',
    long_description=long_description,
    long_description_content_type='text/markdown',

    author="Stephen Zimmerman",
    author_email="sz@galacticicecube.com",

    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
)
