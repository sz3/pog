from setuptools import setup, find_packages


setup(
    name='pogcli',
    license='MIT',
    url='https://github.com/sz3/pog',
    version='0.0.1',

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
        'docopt>=0.6.2',
        'humanfriendly>=4.18',
        'PyNaCl>=1.3.0',
        'zstandard>=0.11.1',
    ],

    description='Pretty Ok Gncryption',
    long_description=(
        'File encryption and backup utility.'
    ),

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
