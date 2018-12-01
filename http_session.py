import select
import socket
import logging
import re
import os
from datetime import datetime
from time import gmtime, strftime
import mimetypes
import urllib
import functools

EOL1 = b"\n\n"
EOL2 = b"\r\n\r\n"
EOL = b"\r\n"

MAX_HTTP_GET_REQ_SIZE = 8*1024

HTTP_METODS = ["GET", "HEAD"]

OK = 200
BAD_REQUEST = 400
NOT_FOUND = 404
METHOD_NOT_ALLOWED = 405

RESPONSES = {
    200: b'200 OK',

    400: b'400 Bad Request',
    404: b'404 Not Found',
    405: b'405 Method Not Allowed',
}


class Session:
    def __init__(self, socket, root_dir):
        self.r_buffer = b''
        self.w_buffer = b''
        self.socket = socket
        self.request = None
        self.root_dir = root_dir
        self.keepalive = False

    def read(self):
        try:
            data = self.socket.recv(1024)
        except ConnectionResetError:
            return False
        if data:
            self.r_buffer += data
            if len(self.r_buffer) > MAX_HTTP_GET_REQ_SIZE:
                return False
            return True
        return False

    def is_writeable(self):
        if EOL1 in self.r_buffer or EOL2 in self.r_buffer:
            logging.debug("Request: {}".format(self.r_buffer))
            self.request = HttpRequest(self.r_buffer)
            self.request.validate(self.root_dir)
            self.request.path = normalize_path(self.request.location, self.root_dir)
            logging.debug("Path: {}".format(self.request.path))
            self.keepalive, self.w_buffer = get_response(self.request)
            self.r_buffer = b''
            return True
        return False

    def write(self):
        result = self.socket.send(self.w_buffer)
        if result == len(self.w_buffer):
            logging.debug("Resnose: {}".format(self.w_buffer))
            return True
        else:
            self.w_buffer = self.w_buffer[result:]
            return False


class HttpRequest:
    header_re = re.compile(r"^(GET|HEAD)\s/?(.*?)\s(HTTP/.*?)\r\n")

    def __init__(self, buffer):
        self.method = ""
        self.location = ""
        self.version = ""
        self.path = ""
        self.headers = {}
        self.body = buffer.decode("utf-8")
        self.valid = False

    def validate(self, root_dir):
        try:
            self.get_initline()
            self.get_headers()
        except Exception as e:
            self.valid = False
            return
        self.valid = True

    def get_initline(self):
        res = type(self).header_re.match(self.body)
        self.method = res.group(1)
        self.location = res.group(2)
        self.version = res.group(3)

    def get_headers(self):
        h_list = [l.strip() for l in self.body.split("\n") if ":" in l]
        for line in h_list:
            key, value = line.split(':', 1)
            self.headers[key] = value.strip()

    def keep_alive(self):
        if self.version == "HTTP/1.1":
            return True
        if self.version == "HTTP/1.0" and self.headers.get("Connection:") == "keep-alive":
            return True
        return False


@functools.lru_cache(1024)
def normalize_path(path, root_dir):
        norm_path = os.path.join(root_dir, path)
        norm_path = urllib.parse.unquote(norm_path)
        norm_path = os.path.normpath(norm_path)
        norm_path = urllib.parse.urlparse(norm_path).path
        if not norm_path.startswith(root_dir):
            return ""
        if os.path.isdir(norm_path):
            norm_path = os.path.join(norm_path, "index.html")
        return norm_path


def get_headers(keepalive):
    headers = "Date: {}\r\nServer: OTUServer\r\n".format(strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime()))
    headers += "Connection: keep-alive\r\n" if keepalive else "Connection: close\r\n"
    return headers


@functools.lru_cache(1024)
def get_content_headers(file_path):
    header = ""
    size = os.path.getsize(file_path)
    header = "Content-Length: {}\r\n".format(size)
    content_type, encoding = mimetypes.guess_type(file_path)
    if content_type:
        header += "Content-Type: {}\r\n".format(content_type)
    return header


def response_40x(status, version, keepalive):
    headers = get_headers(keepalive)
    return version + b' ' + RESPONSES[status] + EOL + headers.encode('utf-8') + EOL


def response_200(version, keepalive, path, body):
    headers = get_headers(keepalive)
    headers += get_content_headers(path)
    r = version + b' ' + RESPONSES[OK] + EOL + headers.encode('utf-8') + EOL
    if not body:
        return r
    return r + body + EOL


def get_response(request):
    version = str.encode(request.version or "HTTP/1.0")
    body = b""
    ka = request.keep_alive()
    if not request.valid:
        return ka, response_40x(BAD_REQUEST, version, ka)
    if request.method in HTTP_METODS:
        if os.path.isfile(request.path):
            if request.method == 'GET':
                try:
                    with open(request.path, 'rb') as f:
                        body = bytearray(f.read())
                except IOError:
                    return ka, response_40x(BAD_REQUEST, version, ka)
            return ka, response_200(version, ka, request.path, body)
        else:
            return False, response_40x(NOT_FOUND, version, False)
    return ka, response_40x(METHOD_NOT_ALLOWED, version, ka)
