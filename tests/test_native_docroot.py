"""CMS discovery must follow native Hestia document roots and custom roots."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from inventory import document_root


class NativeDocumentRoot(unittest.TestCase):
    def test_native_list_document_root_is_used_without_guessing_or_extra_command(self):
        hestia=Mock(side_effect=AssertionError('No fallback needed'))
        self.assertEqual(document_root(hestia,'alice','one.example',
            {'document_root':'/home/alice/web/shared.example/public_html/shop/'}),
            '/home/alice/web/shared.example/public_html/shop')

    def test_single_domain_native_fallback_resolves_custom_document_root(self):
        hestia=Mock(return_value={'one.example':{'DOCUMENT_ROOT':'/srv/hosting/alice/custom'}})
        self.assertEqual(document_root(hestia,'alice','one.example',{}),'/srv/hosting/alice/custom')
        hestia.assert_called_once_with('v-list-web-domain','alice','one.example','json')

    def test_incomplete_or_relative_native_root_is_rejected(self):
        for value in (None,'relative/public_html','/home/alice/../bob/public_html'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                document_root(Mock(return_value={'one.example':{'DOCUMENT_ROOT':value}}),
                              'alice','one.example',{})


if __name__=='__main__':unittest.main()
