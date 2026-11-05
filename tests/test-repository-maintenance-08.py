#!/usr/bin/env python3
"""Real certificate and signature checks with temporary, isolated material."""
from datetime import datetime,timedelta,timezone
from email.utils import format_datetime
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('repository_maintenance',ROOT/'scripts/repository-maintenance.py')
maintenance=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(maintenance)
UTC=timezone.utc


def command(*args,env=None):
    return subprocess.run(list(map(str,args)),env=env,input=b'',capture_output=True,timeout=30,check=True).stdout


@unittest.skipUnless(shutil.which('openssl') and shutil.which('gpg') and shutil.which('gpgv'),'OpenSSL/GnuPG necessários')
class RepositoryMaintenance08(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory();cls.root=Path(cls.temporary.name)
        cls.tls=cls.root/'tls';cls.tls.mkdir(mode=0o700)
        cls.gpg=cls.root/'gpg';cls.gpg.mkdir(mode=0o700)
        cls.env={**os.environ,'GNUPGHOME':str(cls.gpg)}
        command('openssl','req','-new','-x509','-nodes','-newkey','rsa:2048','-days','30','-sha256',
                '-subj','/CN=Test Repository Authority','-addext','basicConstraints=critical,CA:TRUE,pathlen:0',
                '-addext','keyUsage=critical,keyCertSign,cRLSign','-keyout',cls.tls/'ca.key','-out',cls.tls/'ca.crt')
        command('openssl','req','-new','-nodes','-newkey','rsa:2048','-sha256','-subj','/CN=Repository test',
                '-keyout',cls.tls/'server.key','-out',cls.root/'server.csr')
        extensions=cls.root/'server.cnf';extensions.write_text('[server]\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=@names\n[names]\nDNS.1=localhost\nDNS.2=repo.test\nIP.1=127.0.0.1\nIP.2=::1\n')
        command('openssl','x509','-req','-in',cls.root/'server.csr','-CA',cls.tls/'ca.crt','-CAkey',cls.tls/'ca.key',
                '-set_serial','10','-days','2','-sha256','-extfile',extensions,'-extensions','server','-out',cls.tls/'server.crt')
        for name in ('ca.key','server.key'):(cls.tls/name).chmod(0o600)
        command('gpg','--batch','--pinentry-mode','loopback','--passphrase','','--quick-generate-key',
                'Repository Test <repository@example.invalid>','ed25519','sign','1d',env=cls.env)
        output=command('gpg','--batch','--with-colons','--list-secret-keys',env=cls.env).decode()
        cls.fingerprint=next(line.split(':')[9] for line in output.splitlines() if line.startswith('fpr:'))
        cls.public_key=command('gpg','--batch','--export',cls.fingerprint,env=cls.env)

    @classmethod
    def tearDownClass(cls):
        command('gpgconf','--kill','gpg-agent',env=cls.env)
        cls.temporary.cleanup()

    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.directory=Path(temporary.name)
        self.tls=self.directory/'tls';shutil.copytree(type(self).tls,self.tls)
        self.publication=self.directory/'publication';self.distribution=self.publication/'dists/trixie'
        index=self.distribution/'main/binary-amd64/Packages';index.parent.mkdir(parents=True)
        content=b'Package: linuxbr-test\nVersion: 0.8\nArchitecture: all\n\n';index.write_bytes(content)
        now=datetime.now(UTC)
        self.release=('Origin: LinuxBR\nDate: '+format_datetime(now,usegmt=True)+'\nValid-Until: '+
            format_datetime(now+timedelta(days=7),usegmt=True)+'\nSHA256:\n '+hashlib.sha256(content).hexdigest()+' '+str(len(content))+' main/binary-amd64/Packages\n')
        (self.publication/'linuxbr-archive-keyring.gpg').write_bytes(type(self).public_key)
        self.keyring=self.directory/'trusted-keyring.gpg';self.keyring.write_bytes(type(self).public_key)
        self.sign()

    def sign(self):
        release=self.distribution/'Release';release.write_text(self.release)
        for output in ('InRelease','Release.gpg'):(self.distribution/output).unlink(missing_ok=True)
        command('gpg','--batch','--pinentry-mode','loopback','--passphrase','','--local-user',self.fingerprint,
                '--clearsign','--output',self.distribution/'InRelease',release,env=self.env)
        command('gpg','--batch','--pinentry-mode','loopback','--passphrase','','--local-user',self.fingerprint,
                '--armor','--detach-sign','--output',self.distribution/'Release.gpg',release,env=self.env)

    def health(self,**kwargs):
        return maintenance.health(self.publication,self.tls,self.keyring,'repo.test',warn_days=0,**kwargs)

    def test_real_gpg_signatures_index_hashes_tls_chain_and_identity(self):
        result=self.health();self.assertEqual(result['status'],'ok',result)
        publication=next(check for check in result['checks'] if check['check']=='publication')
        self.assertEqual(publication['signatures'],['InRelease','Release.gpg']);self.assertEqual(publication['indices_checked'],1)
        self.assertIn(self.fingerprint,publication['fingerprints'])
        result=maintenance.health(self.publication,self.tls,host='repo.test',warn_days=3)
        self.assertEqual(result['status'],'warning');self.assertTrue(any(check['check']=='trust-reference' for check in result['checks']))

    def test_metadata_renewal_preserves_indexes_identity_and_becomes_noop(self):
        before=(self.distribution/'main/binary-amd64/Packages').read_bytes()
        with patch.dict(os.environ,self.env):
            unchanged=maintenance.renew_metadata(self.publication,self.keyring,self.fingerprint)
            self.assertEqual(unchanged['status'],'unchanged')
            renewed=maintenance.renew_metadata(self.publication,self.keyring,self.fingerprint,force=True)
            self.assertEqual(renewed['status'],'renewed');self.assertTrue(renewed['atomic'])
            self.assertEqual(maintenance.renew_metadata(self.publication,self.keyring,self.fingerprint)['status'],'unchanged')
        self.assertEqual((self.distribution/'main/binary-amd64/Packages').read_bytes(),before)
        checked=maintenance.check_publication(self.publication,self.keyring)
        self.assertEqual(checked['fingerprints'],[self.fingerprint])
        self.assertGreater(checked['expires_at'],datetime.now(UTC)+timedelta(days=13))

    def test_metadata_refuses_identity_change_tampering_and_symlink(self):
        before=(self.distribution/'InRelease').read_bytes()
        with self.assertRaises(ValueError):maintenance.renew_metadata(self.publication,self.keyring,'A'*40,force=True)
        link=self.directory/'publication-link';link.symlink_to(self.publication,target_is_directory=True)
        with self.assertRaises(ValueError):maintenance.renew_metadata(link,self.keyring,self.fingerprint,force=True)
        (self.distribution/'main/binary-amd64/Packages').write_bytes(b'altered')
        with self.assertRaises(ValueError):maintenance.renew_metadata(self.publication,self.keyring,self.fingerprint,force=True)
        self.assertEqual((self.distribution/'InRelease').read_bytes(),before)

    def test_metadata_restores_previous_directory_after_verification_failure(self):
        before={str(p.relative_to(self.distribution)):p.read_bytes() for p in self.distribution.rglob('*') if p.is_file()}
        actual=maintenance.check_publication;calls=0
        def check(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==3:raise ValueError('injected final verification failure')
            return actual(*args,**kwargs)
        with patch.dict(os.environ,self.env),patch.object(maintenance,'check_publication',side_effect=check):
            with self.assertRaises(ValueError):maintenance.renew_metadata(self.publication,self.keyring,self.fingerprint,force=True)
        self.assertEqual({str(p.relative_to(self.distribution)):p.read_bytes() for p in self.distribution.rglob('*') if p.is_file()},before)
        actual(self.publication,self.keyring)

    def test_rejects_altered_signatures_and_index_contents(self):
        release=self.distribution/'Release';release.write_text(self.release.replace('LinuxBR','Changed'))
        self.assertEqual(self.health()['status'],'error')
        self.sign();(self.distribution/'main/binary-amd64/Packages').write_bytes(b'tampered')
        self.assertEqual(self.health()['status'],'error')
        with self.assertRaises(ValueError):maintenance._signature_fingerprints(b'[GNUPG:] EXPKEYSIG 12345678 Test\n[GNUPG:] VALIDSIG ABCDEF1234567890\n')

    def test_signed_expired_future_dates_and_symlink_indices_rejected(self):
        now=datetime.now(UTC)
        self.release=self.release.replace(format_datetime(now+timedelta(days=7),usegmt=True),format_datetime(now-timedelta(days=1),usegmt=True))
        # Set the dates independently so elapsed seconds cannot affect replacement.
        lines=self.release.splitlines();lines[1]='Date: '+format_datetime(now-timedelta(days=2),usegmt=True);lines[2]='Valid-Until: '+format_datetime(now-timedelta(days=1),usegmt=True)
        self.release='\n'.join(lines)+'\n';self.sign();self.assertEqual(self.health()['status'],'error')
        lines[1]='Date: '+format_datetime(now+timedelta(days=1),usegmt=True);lines[2]='Valid-Until: '+format_datetime(now+timedelta(days=7),usegmt=True)
        self.release='\n'.join(lines)+'\n';self.sign();self.assertEqual(self.health()['status'],'error')
        lines[1]='Date: '+format_datetime(now,usegmt=True);self.release='\n'.join(lines)+'\n';self.sign()
        index=self.distribution/'main/binary-amd64/Packages';outside=self.directory/'outside';outside.write_bytes(index.read_bytes());index.unlink();index.symlink_to(outside)
        self.assertEqual(self.health()['status'],'error')

    def test_renewal_preserves_ca_server_key_sans_and_previous_certificate(self):
        before={path.name:path.read_bytes() for path in self.tls.iterdir()}
        old=maintenance.certificate_info(self.tls/'server.crt')
        result=maintenance.renew_certificate(self.tls,'repo.test',days=7)
        new=maintenance.certificate_info(self.tls/'server.crt')
        self.assertEqual(old['san'],new['san']);self.assertNotEqual(old['serial'],new['serial']);self.assertGreater(new['not_after'],old['not_after'])
        for name in ('ca.crt','ca.key','server.key'):self.assertEqual((self.tls/name).read_bytes(),before[name])
        self.assertEqual(Path(result['backup']).read_bytes(),before['server.crt'])
        self.assertFalse(result['service_reloaded']);self.assertEqual(self.health()['status'],'ok')
        self.assertFalse((self.tls/'.certificate-renewal.lock').exists())

    def test_renewal_refuses_wrong_name_short_ca_and_insecure_key(self):
        before=(self.tls/'server.crt').read_bytes()
        with self.assertRaises(ValueError):maintenance.renew_certificate(self.tls,'wrong.test',7)
        with self.assertRaises(ValueError):maintenance.renew_certificate(self.tls,'repo.test',40)
        (self.tls/'server.key').chmod(0o644)
        with self.assertRaises(ValueError):maintenance.renew_certificate(self.tls,'repo.test',7)
        self.assertEqual((self.tls/'server.crt').read_bytes(),before)

    def test_renewal_refuses_mismatched_key_symlink_and_active_lock(self):
        before=(self.tls/'server.crt').read_bytes()
        (self.tls/'server.key').write_bytes((self.tls/'ca.key').read_bytes())
        with self.assertRaises(ValueError):maintenance.renew_certificate(self.tls,'repo.test',7)
        shutil.copyfile(type(self).tls/'server.key',self.tls/'server.key')
        key=self.tls/'server.key';key.unlink();key.symlink_to(type(self).tls/'server.key')
        with self.assertRaises(ValueError):maintenance.renew_certificate(self.tls,'repo.test',7)
        key.unlink();shutil.copyfile(type(self).tls/'server.key',key);key.chmod(0o600)
        (self.tls/'.certificate-renewal.lock').write_text('other operation')
        with self.assertRaises(ValueError):maintenance.renew_certificate(self.tls,'repo.test',7)
        self.assertEqual((self.tls/'server.crt').read_bytes(),before)

    def test_renewed_certificate_accepts_real_tls_connection_with_original_ca(self):
        maintenance.renew_certificate(self.tls,'repo.test',7)
        server=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);server.load_cert_chain(self.tls/'server.crt',self.tls/'server.key')
        client=ssl.create_default_context(cafile=str(self.tls/'ca.crt'))
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(5)
        errors=[]
        def serve():
            try:
                connection,_address=listener.accept()
                with server.wrap_socket(connection,server_side=True) as secure:secure.sendall(b'OK')
            except Exception as exc:errors.append(exc)
        thread=threading.Thread(target=serve,daemon=True);thread.start()
        try:
            with socket.create_connection(listener.getsockname(),timeout=5) as connection:
                with client.wrap_socket(connection,server_hostname='repo.test') as secure:
                    self.assertEqual(secure.recv(2),b'OK')
                    self.assertEqual(hashlib.sha256(secure.getpeercert(binary_form=True)).hexdigest(),
                        hashlib.sha256(ssl.PEM_cert_to_DER_cert((self.tls/'server.crt').read_text())).hexdigest())
        finally:thread.join(6);listener.close()
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])


if __name__=='__main__':unittest.main()
