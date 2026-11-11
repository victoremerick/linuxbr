"""Check the diagnostic consent transport and its data boundary."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/linuxbr-system/files/usr/lib/linuxbr-system'))
from support_remote import dispatch


class SupportRemote(unittest.TestCase):
    def test_poll_and_send_are_separate(self):
        transport = Mock(return_value={'request_id': 'request_1'})
        config = {'device': 'machine-1'}
        self.assertEqual(dispatch(config, 'pending', transport, io.BytesIO()),
                         {'request_id': 'request_1'})
        transport.assert_called_once_with(config, 'GET', '/v1/diagnostic')

        payload = {'request_id': 'request_1', 'report': {
            'schema': 1, 'diagnóstico': {'Rede': {'conectividade': 'full'}}}}
        data = io.BytesIO(json.dumps(payload).encode())
        self.assertEqual(dispatch(config, 'send', transport, data), {'sent': True})
        transport.assert_called_with(config, 'POST', '/v1/diagnostic', payload)

    def test_decline_sends_only_the_request_id(self):
        transport = Mock()
        self.assertEqual(dispatch({}, 'decline', transport, io.BytesIO(b'{"request_id":"request_1"}')),
                         {'declined': True})
        transport.assert_called_once_with({}, 'POST', '/v1/diagnostic',
                                         {'request_id': 'request_1', 'decline': True})

    def test_report_rejects_raw_logs_unknown_values_and_unbounded_payloads(self):
        transport = Mock()
        for fields in ({'conectividade': 'secret-token'}, {'log': 'raw log'}, {}):
            payload = {'request_id': 'request_1', 'report': {
                'schema': 1, 'diagnóstico': {'Rede': fields}}}
            with self.assertRaises(ValueError):
                dispatch({}, 'send', transport, io.BytesIO(json.dumps(payload).encode()))
        with self.assertRaises(ValueError):
            dispatch({}, 'send', transport, io.BytesIO(b'a' * (16 * 1024 + 1)))
        transport.assert_not_called()


if __name__ == '__main__':
    unittest.main()
