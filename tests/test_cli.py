from os import environ
from subprocess import PIPE
from unittest import TestCase
from unittest.mock import patch

from .helpers import TestDirMixin
from pog.cli import PogCli, POG_ROOT


class PogCliTest(TestDirMixin, TestCase):
    # test for the PogCli class
    def test_keyfiles(self):
        cli = PogCli()

        # pick decryption file
        for i in range(3):
            cli.set_keyfiles('foo.encrypt', 'foo.decrypt', 'other.keyfile')
            self.assertEqual(cli.config.get('decryption-keyfile'), 'foo.decrypt')
            self.assertEqual(cli.config.get('encryption-keyfile'), None)
            self.assertEqual(cli.config.get('keyfile'), None)

        cli.set_keyfiles('foo.encrypt', 'other.keyfile')
        self.assertEqual(cli.config.get('decryption-keyfile'), None)
        self.assertEqual(cli.config.get('encryption-keyfile'), 'foo.encrypt')
        self.assertEqual(cli.config.get('keyfile'), None)

        cli.set_keyfiles('other.keyfile', 'second.keyfile')
        self.assertEqual(cli.config.get('decryption-keyfile'), None)
        self.assertEqual(cli.config.get('encryption-keyfile'), None)
        self.assertEqual(cli.config.get('keyfile'), 'other.keyfile')

        # clear
        cli.set_keyfiles()
        self.assertEqual(cli.config.get('decryption-keyfile'), None)
        self.assertEqual(cli.config.get('encryption-keyfile'), None)
        self.assertEqual(cli.config.get('keyfile'), None)

    @patch('pog.cli.Popen', autospec=True)
    def test_dump_manifest(self, mock_run):
        mock_run.return_value = mock_run
        mock_run.__enter__.return_value = mock_run
        mock_run.stdout = [
            b'* 1.txt:\n',
            b'abcdef12345\n',
            b'fghjkl34567\n',
        ]

        cli = PogCli()
        cli.set_keyfiles('foo.decrypt')
        res = cli.dumpManifest('my.mfn')
        self.assertEqual(res, {'1.txt': ['abcdef12345', 'fghjkl34567']})

        env = dict(environ)
        env['PYTHONPATH'] = POG_ROOT
        mock_run.assert_called_once_with(
            ['python', '-u', '-m', 'pog.pog', '--dump-manifest', 'my.mfn', '--decryption-keyfile=foo.decrypt'],
            env=env, stdout=PIPE,
        )

    @patch('pog.cli.Popen', autospec=True)
    def test_dump_manifest_index(self, mock_run):
        mock_run.return_value = mock_run
        mock_run.__enter__.return_value = mock_run
        mock_run.stdout = [
            b'abcdef12345\n',
            b'fghjkl34567\n',
        ]

        cli = PogCli()
        cli.set_keyfiles('foo.encrypt')
        res = list(cli.dumpManifestIndex('my.mfn'))
        self.assertEqual(res, ['abcdef12345', 'fghjkl34567'])

        env = dict(environ)
        env['PYTHONPATH'] = POG_ROOT
        mock_run.assert_called_once_with(
            ['python', '-u', '-m', 'pog.pog', '--dump-manifest-index', 'my.mfn', '--encryption-keyfile=foo.encrypt'],
            env=env, stdout=PIPE,
        )

    @patch('pog.cli.Popen', autospec=True)
    def test_decrypt(self, mock_run):
        mock_run.return_value = mock_run
        mock_run.__enter__.return_value = mock_run
        mock_run.stdout = [
            b'* 1/2: foo.txt\n',
            b'* 2/2: bar.txt\n',
        ]

        cli = PogCli()
        cli.set_keyfiles('foo.decrypt')
        res = list(cli.decrypt('my.mfn'))
        self.assertEqual(res, [
            {'current': 1, 'filename': 'foo.txt', 'total': 2},
            {'current': 2, 'filename': 'bar.txt', 'total': 2}
        ])

        env = dict(environ)
        env['PYTHONPATH'] = POG_ROOT
        mock_run.assert_called_once_with(
            ['python', '-u', '-m', 'pog.pog', '--decrypt', 'my.mfn', '--decryption-keyfile=foo.decrypt'],
            env=env, stdout=PIPE,
        )
