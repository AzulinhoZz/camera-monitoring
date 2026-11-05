"""Exercise upstream POP3/HTTP framing regression cases without network access."""
import argparse
import hashlib
import http.client
import io
import json
from pathlib import Path
import poplib
import sysconfig


class Socket:
    def __init__(self, data):
        self.data = data

    def makefile(self, mode):
        return io.BytesIO(self.data)


def validate():
    cases = 0
    for value in list(range(32)) + [127]:
        obj = object.__new__(poplib.POP3)
        obj.encoding = 'UTF-8'
        obj._debugging = 0
        sent = []
        obj._putline = sent.append
        try:
            obj._putcmd('USER test' + chr(value))
        except ValueError:
            pass
        else:
            raise AssertionError('POP3 accepted a control character')
        assert not sent, 'POP3 wrote an invalid command'
        cases += 1
    obj._putcmd('USER synthetic-user')
    assert sent == [b'USER synthetic-user']
    cases += 1
    for value in [b'-1', b'+1', b'0x1', b'1_0', b' 1', b'g1']:
        response = http.client.HTTPResponse(Socket(
            b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n' + value + b'\r\na\r\n0\r\n\r\n'))
        response.begin()
        try:
            response.read()
        except http.client.IncompleteRead:
            pass
        else:
            raise AssertionError('HTTP accepted invalid chunk framing')
        finally:
            response.close()
        cases += 1
    response = http.client.HTTPResponse(Socket(
        b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3;ext=value\r\nabc\r\n0\r\n\r\n'))
    response.begin()
    assert response.read() == b'abc'
    response.close()
    cases += 1
    for value in ['+5', '-5', '5_0', '5 0', '0x5']:
        response = http.client.HTTPResponse(Socket(
            ('HTTP/1.1 200 OK\r\nContent-Length: ' + value + '\r\n\r\nHello').encode()))
        response.begin()
        assert response.length is None
        assert response.read() == b'Hello'
        response.close()
        cases += 1
    for value in ['7', '7 ', '7\t', '7 \t ', ' 7 ']:
        response = http.client.HTTPResponse(Socket(
            ('HTTP/1.1 200 OK\r\nContent-Length: ' + value + '\r\n\r\nHello\r\nextra').encode()))
        response.begin()
        assert response.length == 7
        assert response.read() == b'Hello\r\n'
        response.close()
        cases += 1
    return {'result': 'PASS', 'regression_cases': cases, 'network': 'none',
            'modules': {name: hashlib.sha256((Path(sysconfig.get_path('stdlib')) / name).read_bytes()).hexdigest()
                        for name in ['poplib.py', 'http/client.py']},
            'limits': 'Reviewed upstream regression inputs only; no scan finding suppressed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = validate()
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
