from os import environ
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
            cli.set_keyfiles(['foo.encrypt', 'foo.decrypt', 'other.keyfile'])
            self.assertEqual(cli.config.get('decryption-keyfile'), 'foo.decrypt')
            self.assertEqual(cli.config.get('encryption-keyfile'), None)
            self.assertEqual(cli.config.get('keyfile'), None)

        cli.set_keyfiles(['foo.encrypt', 'other.keyfile'])
        self.assertEqual(cli.config.get('decryption-keyfile'), None)
        self.assertEqual(cli.config.get('encryption-keyfile'), 'foo.encrypt')
        self.assertEqual(cli.config.get('keyfile'), None)

        cli.set_keyfiles(['other.keyfile', 'second.keyfile'])
        self.assertEqual(cli.config.get('decryption-keyfile'), None)
        self.assertEqual(cli.config.get('encryption-keyfile'), None)
        self.assertEqual(cli.config.get('keyfile'), 'other.keyfile')

    @patch('pog.cli.check_output', autospec=True)
    def test_dump_manifest(self, mock_run):
        mock_run.return_value = b'* 1.txt:\nabcdef12345\nfghjkl34567\n'

        cli = PogCli()
        cli.set_keyfiles(['foo.decrypt'])
        res = cli.dumpManifest('my.mfn')
        self.assertEqual(res, {'1.txt': ['abcdef12345', 'fghjkl34567']})

        env = dict(environ)
        env['PYTHONPATH'] = POG_ROOT
        mock_run.assert_called_once_with(
            ['python', '-m', 'pog.pog', '--dump-manifest', 'my.mfn', '--decryption-keyfile=foo.decrypt'],
            env=env
        )

    @patch('pog.cli.check_output', autospec=True)
    def test_dump_manifest_index(self, mock_run):
        mock_run.return_value = b'abcdef12345\nfghjkl34567\n'

        cli = PogCli()
        cli.set_keyfiles(['foo.encrypt'])
        res = list(cli.dumpManifestIndex('my.mfn'))
        self.assertEqual(res, ['abcdef12345', 'fghjkl34567'])

        env = dict(environ)
        env['PYTHONPATH'] = POG_ROOT
        mock_run.assert_called_once_with(
            ['python', '-m', 'pog.pog', '--dump-manifest-index', 'my.mfn', '--encryption-keyfile=foo.encrypt'],
            env=env
        )
