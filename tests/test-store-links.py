from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from store_links import parse_link,find_entry


class LinkTests(unittest.TestCase):
    def test_valid_links(self):
        self.assertEqual(parse_link('linuxbr-store://app/linuxbr-official/whatsapp'),('linuxbr-official','whatsapp'))
        self.assertEqual(parse_link('linuxbr-store://app/builtin/vlc'),('builtin','vlc'))

    def test_reject_untrusted_arguments(self):
        for value in ['https://app/builtin/vlc','linuxbr-store://app/builtin/../vlc',
                      'linuxbr-store://app/builtin/vlc?exec=bad','linuxbr-store://user@app/builtin/vlc',
                      'linuxbr-store://app/builtin/%2fbin','linuxbr-store://app/builtin/vlc#bad',
                      'linuxbr-store://app/builtin/vlc\n']:
            with self.assertRaises(ValueError):parse_link(value)

    def test_match_source_identity_and_never_accept_a_url(self):
        entries=[{'id':'signed:personal-name:whatsapp','signed_source':'personal-name',
                  'signed_source_id':'linuxbr-official','signed_app':'whatsapp'}]
        self.assertIs(find_entry(entries,'linuxbr-official','whatsapp'),entries[0])
        self.assertIsNone(find_entry(entries,'other-source','whatsapp'))
        self.assertIsNone(find_entry(entries,'builtin',entries[0]['id']))

    def test_duplicate_source_id_requires_review(self):
        row={'signed_source_id':'linuxbr-official','signed_app':'whatsapp'}
        with self.assertRaises(ValueError):find_entry([row,row],'linuxbr-official','whatsapp')


if __name__=='__main__':unittest.main()
