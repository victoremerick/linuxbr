#!/usr/bin/env python3
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from PyQt6.QtCore import QBuffer,QByteArray,QIODevice,QCoreApplication
from PyQt6.QtGui import QImage
import webapp_icons as icons
APP=QCoreApplication.instance() or QCoreApplication([])


class Favicons(unittest.TestCase):
    def test_private_addresses_and_non_https_are_rejected(self):
        for address in ['127.0.0.1','192.168.0.114','10.0.0.1','169.254.169.254','::1']:
            with patch.object(socket,'getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))]):
                with self.assertRaises(ValueError):icons.public_url('https://example.com/favicon.ico')
        for url in ['http://example.com/icon','file:///etc/passwd','https://user:password@example.com/icon','https://example.com:8443/icon']:
            with self.assertRaises(ValueError):icons.public_url(url)

    def test_public_address_is_returned_for_pinned_connection(self):
        with patch.object(socket,'getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]):
            self.assertEqual(icons.public_url('https://example.com/favicon.ico'),('example.com','93.184.216.34','/favicon.ico'))

    def test_real_image_is_converted_and_bounded(self):
        image=QImage(512,384,QImage.Format.Format_ARGB32);image.fill(0xff227744)
        buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly);self.assertTrue(image.save(buffer,'PNG'))
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp)/'icon.png';icons.store_image(bytes(buffer.data()),destination)
            result=QImage(str(destination));self.assertEqual((result.width(),result.height()),(256,192))
            self.assertEqual(list(Path(tmp).glob('.favicon-*')),[])

    def test_invalid_image_keeps_existing_icon(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp)/'icon.png';destination.write_bytes(b'previous')
            with self.assertRaises(ValueError):icons.store_image(b'not an image',destination)
            self.assertEqual(destination.read_bytes(),b'previous')

    def test_icon_parser_limits_candidates(self):
        parser=icons.Icons();parser.feed('<link rel="icon" href="/favicon.png">'*20)
        self.assertEqual(len(parser.urls),8)


if __name__=='__main__':unittest.main()
