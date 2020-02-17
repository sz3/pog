from os import mkdir
from tempfile import TemporaryDirectory
from unittest import TestCase

from pog.lib.local_file_list import local_file_list


class LocalFileListTest(TestCase):
    def setUp(self):
        self.test_dir = TemporaryDirectory()
        for i in range(1, 10):
            with open(f'{self.test_dir.name}/{i}.txt', 'wb'):
                pass

        mkdir(f'{self.test_dir.name}/subdir')
        with open(f'{self.test_dir.name}/subdir/file.txt', 'wb'):
            pass

    def tearDown(self):
        with self.test_dir:
            pass

    def test_files(self):
        expected = [f'{self.test_dir.name}/{i}.txt' for i in range(1, 5)]

        self.assertEqual(
            local_file_list(*expected),
            expected,
        )

    def test_dir(self):
        expected = [f'{self.test_dir.name}/{i}.txt' for i in range(1, 10)] + [f'{self.test_dir.name}/subdir/file.txt']
        self.assertEqual(
            local_file_list(self.test_dir.name),
            expected,
        )

    def test_no_dups(self):
        expected = [f'{self.test_dir.name}/{i}.txt' for i in range(1, 10)] + [f'{self.test_dir.name}/subdir/file.txt']
        self.assertEqual(
            local_file_list(self.test_dir.name, *expected),
            expected,
        )

    def test_glob(self):
        expected = [f'{self.test_dir.name}/{i}.txt' for i in range(1, 10)] + [f'{self.test_dir.name}/subdir/file.txt']
        self.assertEqual(
            local_file_list(f'{self.test_dir.name}/**/*'),
            expected,
        )
