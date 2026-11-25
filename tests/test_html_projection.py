"""Canonical HTML keeps the existing native v1 tuple and real context isolation."""
import base64
import copy
import ctypes
import json
import unittest
import test_delivery_envelope as envelope


@unittest.skipUnless(envelope.CC, 'C compiler required; skips are not acceptance')
class HTMLProjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        envelope.DeliveryEnvelope.setUpClass.__func__(cls)
        for name in ('delivery_public_projection_parse', 'delivery_public_projection_header_parse'):
            fn = getattr(cls.lib, name)
            fn.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
            fn.restype = ctypes.c_int
        cls.lib.delivery_public_projection_header.argtypes = [ctypes.c_void_p]
        cls.lib.delivery_public_projection_header.restype = ctypes.c_void_p
        cls.lib.delivery_public_projection_free.argtypes = [ctypes.c_void_p]
        cls.lib.delivery_public_projection_free.restype = None
        cls.lib.delivery_public_projection_equal.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cls.lib.delivery_public_projection_equal.restype = ctypes.c_int
        cls.lib.delivery_manifest_free.argtypes = [ctypes.c_void_p]
        cls.lib.delivery_manifest_free.restype = None

    tearDownClass = classmethod(envelope.DeliveryEnvelope.tearDownClass.__func__)

    def parse(self, value, header=False):
        wire = json.dumps(value).encode() if isinstance(value, dict) else value
        pointer = ctypes.c_void_p()
        fn = self.lib.delivery_public_projection_header_parse if header else self.lib.delivery_public_projection_parse
        self.assertEqual(fn(wire, len(wire), ctypes.byref(pointer)), 1)
        self.assertTrue(pointer)
        self.addCleanup(self.lib.delivery_public_projection_free, pointer)
        return pointer

    def test_html_roundtrip_preserves_locale_language_and_cookie_context(self):
        value = dict(version=1, bucket='html', locale='en_US', language='en',
                     cookieValues=[dict(name='currency', valueBase64='RVVS')])
        original = self.parse(value)
        header_pointer = self.lib.delivery_public_projection_header(original)
        self.assertTrue(header_pointer)
        try:
            header = ctypes.string_at(header_pointer)
        finally:
            self.lib.delivery_manifest_free(header_pointer)
        self.assertEqual(json.loads(base64.b64decode(header)), value)
        self.assertEqual(self.lib.delivery_public_projection_equal(original, self.parse(header, header=True)), 1)
        for field, replacement in (('locale', 'fr_FR'), ('language', 'fr'),
                                   ('cookieValues', [dict(name='currency', valueBase64='VVNE')])):
            changed = copy.deepcopy(value)
            changed[field] = replacement
            with self.subTest(field=field):
                self.assertEqual(self.lib.delivery_public_projection_equal(original, self.parse(changed)), 0)


if __name__ == '__main__':
    unittest.main()
