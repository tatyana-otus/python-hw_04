import select
import socket
import logging
import re
import os
from datetime import datetime
from time import gmtime, strftime
import mimetypes
import urllib

EOL1 = b"\n\n"
EOL2 = b"\r\n\r\n"
EOL = b"\r\n"

MAX_HTTP_GET_REQ_SIZE = 8*1024


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
            self.request = normalize_path(self.request, self.root_dir)
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
        except Exception:
            self.valid = False
            return
        self.valid = True

    def get_initline(self):
        res = type(self).header_re.match(self.body)
        self.method = res.group(1)
        self.location = res.group(2)
        self.version = res.group(3)

    def get_headers(self):
        h_begin = self.body.find("\n")
        h_list = filter(None, self.body[h_begin:].split("\n"))
        self.headers = dict(s.split(': ', 1) for s in h_list)

    def keep_alive(self):
        if self.version == "HTTP/1.1":
            return True
        if self.version == "HTTP/1.0" and self.headers.get("Connection: ") == "keep-alive":
            return True
        return False


def normalize_path(request, root_dir):
        request.path = os.path.join(root_dir, request.location)
        request.path = urllib.parse.unquote(request.path)
        request.path = os.path.normpath(request.path)
        request.path = urllib.parse.urlparse(request.path).path
        if not request.path.startswith(root_dir):
            request.path = ""
        if os.path.isdir(request.path):
            request.path = os.path.join(request.path, "index.html")
        return request


def get_response(request):
    keepalive = request.keep_alive()
    headers = "Data: {}\r\nServer: OTUServer\r\n".format(strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime()))
    version = str.encode(request.version or "HTTP/1.0")
    body = b""
    if not request.valid:
        status = b"400 Bad Request\r\n"
    if request.method == 'GET' or request.method == 'HEAD':
        if os.path.isfile(request.path):
            headers += get_content_headers(request.path)
            if request.method == 'GET':
                with open(request.path, 'rb') as f:
                    body = bytearray(f.read())
            status = b" 200 OK\r\n"
        else:
            keepalive = False
            status = b" 404 Not Found\r\n"
    else:
        status = b" 405 Method Not Allowed\r\n"
    headers += "Connection: keep-alive\r\n" if keepalive else "Connection: close\r\n"
    response = version + status + headers.encode('utf-8') + EOL
    if body:
        response = response + body + EOL
    return keepalive, response


def get_content_headers(file_path):
    header = ""
    size = os.path.getsize(file_path)
    header = "Content-Length: {}\r\n".format(size)
    content_type, encoding = mimetypes.guess_type(file_path)
    if content_type:
        header += "Content-Type: {}\r\n".format(content_type)
    return header
