import base64
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
import signed_catalog as backend


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.key=Ed25519PrivateKey.generate();public=self.key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        self.source=dict(source_id='test-source',public_key=base64.b64encode(public).decode())
        self.key_id=hashlib.sha256(public).hexdigest()
        now=datetime.now(timezone.utc)
        self.data=dict(schema=1,source_id='test-source',revision=1,issued_at=now.isoformat(),expires_at=(now+timedelta(days=1)).isoformat(),apps=[])

    def signed(self,data=None):
        payload=json.dumps(data or self.data).encode()
        return dict(algorithm='ed25519',key_id=self.key_id,payload=base64.b64encode(payload).decode(),signature=base64.b64encode(self.key.sign(payload)).decode())

    def test_signature_and_tampering(self):
        self.assertEqual(backend.verify(self.signed(),self.source)['revision'],1)
        bad=self.signed();bad['payload']=base64.b64encode(b'{}').decode()
        with self.assertRaises(ValueError):backend.verify(bad,self.source)

    def test_expiry_and_offline(self):
        now=datetime.now(timezone.utc)
        data=dict(self.data,issued_at=(now-timedelta(days=2)).isoformat(),expires_at=(now-timedelta(days=1)).isoformat())
        with self.assertRaises(ValueError):backend.verify(self.signed(data),self.source)
        self.assertTrue(backend.verify(self.signed(data),self.source,True)['expired'])

    def test_downgrade_and_same_revision_change(self):
        source=dict(self.source,revision=2)
        with self.assertRaises(ValueError):backend.verify(self.signed(),source)
        source=dict(self.source,revision=1,payload_sha256='0'*64)
        with self.assertRaises(ValueError):backend.verify(self.signed(),source)

    def test_identity_and_future_date(self):
        with self.assertRaises(ValueError):backend.verify(self.signed(dict(self.data,source_id='other')),self.source)
        data=dict(self.data,issued_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
        with self.assertRaises(ValueError):backend.verify(self.signed(data),self.source)

    def test_bad_schema_and_public_key(self):
        with self.assertRaises(ValueError):backend.verify(self.signed(dict(self.data,revision=True)),self.source)
        with self.assertRaises(ValueError):backend.key_bytes('not a key')

    def test_duplicate_application_and_unsafe_url(self):
        app=dict(id='example',kind='web',name='Example',description='Example',category='Web',source='https://example.com/',url='https://example.com/',favicon='https://example.com/favicon.ico',revision=1,status='published')
        with self.assertRaises(ValueError):backend.verify(self.signed(dict(self.data,apps=[app,app])),self.source)
        with self.assertRaises(ValueError):backend.verify(self.signed(dict(self.data,apps=[dict(app,url='https://127.0.0.1/')])),self.source)

    def test_explicit_key_rotation_preserves_revision_floor(self):
        descriptor=dict(self.source,fingerprint=self.key_id,discovery_url='https://example.com/discovery',catalog_url='https://example.com/catalog')
        previous=dict(descriptor,fingerprint='a'*64,revision=2)
        with patch.object(backend,'read',return_value=previous),patch.object(backend,'fetch',return_value=self.signed()),patch.object(backend,'write') as write:
            with self.assertRaises(ValueError):backend.rotate('example',descriptor,'a'*64,self.key_id)
            write.assert_not_called()
        envelope=self.signed(dict(self.data,revision=3))
        with patch.object(backend,'read',return_value=previous),patch.object(backend,'fetch',return_value=envelope),patch.object(backend,'write') as write:
            with self.assertRaises(ValueError):backend.rotate('example',descriptor,'b'*64,self.key_id)
            self.assertEqual(backend.rotate('example',descriptor,'a'*64,self.key_id),0)
            self.assertEqual(write.call_args.args[1]['revision'],3)
            self.assertEqual(write.call_args.args[1]['fingerprint'],self.key_id)

    def test_bundled_source_preserves_removal_and_local_trust(self):
        source=dict(self.source,fingerprint=self.key_id,discovery_url='https://example.com/discovery',catalog_url='https://example.com/catalog',envelope=self.signed())
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);defaults=root/'defaults';defaults.mkdir();local=root/'local'
            (defaults/'official.json').write_text(json.dumps(source))
            with patch.object(backend,'DEFAULTS',defaults),patch.object(backend,'folder',return_value=local):
                self.assertEqual(len(backend.sources()),1)
                backend.change('official',remove=True)
                self.assertEqual(backend.sources(),[])
                (local/'.initialized-official').unlink()
                backend.write('official',dict(source,enabled=False))
                self.assertFalse(backend.sources()[0]['enabled'])

    def test_invalid_bundled_signature_is_never_imported(self):
        source=dict(self.source,fingerprint=self.key_id,discovery_url='https://example.com/discovery',catalog_url='https://example.com/catalog',envelope=self.signed())
        source['envelope']['signature']=base64.b64encode(b'0'*64).decode()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);defaults=root/'defaults';defaults.mkdir();local=root/'local'
            (defaults/'official.json').write_text(json.dumps(source))
            with patch.object(backend,'DEFAULTS',defaults),patch.object(backend,'folder',return_value=local):
                with self.assertRaises(ValueError):backend.sources()
                self.assertFalse((local/'official.json').exists())


if __name__=='__main__':unittest.main()
