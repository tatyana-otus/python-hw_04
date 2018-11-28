import select
import socket
import logging
import re
import os
from time import gmtime, strftime
from collections import namedtuple
import argparse
import operator
import mimetypes
import urllib
import threading
import multiprocessing

import http_session

PORT = 80
default_config = {
    "ROOT_DIR": os.path.join(os.getcwd(), "http-test-suite"),
    "WORKERS": multiprocessing.cpu_count()
}

OptDes = namedtuple('OptDes', 'flags type default nargs help')
options = {"ROOT_DIR": OptDes('-r',
                              lambda p: os.path.abspath(p) if os.path.isdir(p)
                              else exec('raise(argparse.ArgumentTypeError("No such directory: {}".format(p)))'),
                              default_config["ROOT_DIR"],
                              '?',
                              "Path to root dir"),
           "WORKERS": OptDes('-w',
                             int,
                             default_config["WORKERS"],
                             '?',
                             "The number of worker processes")}


def parse_opt(opt_des):
    opt = {}
    parser = argparse.ArgumentParser()
    for key, des in opt_des.items():
        parser.add_argument(des.flags, type=des.type,
                            default=des.default,
                            nargs=des.nargs, dest=key,
                            help=des.help)
    args = parser.parse_args()
    for key in opt_des:
        f = operator.attrgetter(key)
        opt[key] = f(args)
    return opt


def worker_run(id, server_socket, root_dir):
    try:
        logging.debug("Http Worker {} Start".format(id))
        connections = {}
        server_soc = server_socket
        server_fd = server_soc.fileno()
        e = select.epoll()
        e.register(server_fd, select.EPOLLIN)
        while True:
            events = e.poll(1)
            for fd, event_type in events:
                if fd == server_fd:  # server socket
                    try:
                        client_socket, address = server_soc.accept()
                        client_socket.setblocking(0)
                        client_fd = client_socket.fileno()
                        e.register(client_fd, select.EPOLLIN)
                        connections[client_fd] = http_session.Session(client_socket, root_dir)
                        logging.debug("{} Received connection: {}".format(id, client_fd))
                    except BlockingIOError:
                        pass
                else:                # client socket
                    if event_type & select.EPOLLIN:
                        if connections[fd].read():                # reading from client socket
                            if connections[fd].is_writeable():
                                if not connections[fd].write():   # writing to client socket
                                    e.modify(fd, select.EPOLLOUT)
                                    continue
                                else:
                                    if connections[fd].keepalive:
                                        continue
                            else:
                                continue
                    elif event_type & select.EPOLLOUT:
                        if not connections[fd].write():            # writing to client socket
                            continue
                        else:
                            if connections[fd].keepalive:
                                e.modify(fd, select.EPOLLIN)
                                continue
                    e.unregister(fd)
                    connections[fd].socket.close()
                    del connections[fd]
    except KeyboardInterrupt:
        logging.debug("Http Worker {} Stop".format(id))
        e.unregister(server_fd)
        e.close()


def main():
    try:
        logging.basicConfig(level=logging.INFO,
                            format='[%(asctime)s] %(levelname).1s %(message)s',
                            datefmt='%Y.%m.%d %H:%M:%S',
                            filename=None,
                            filemode='w')

        config = parse_opt(options)

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setblocking(0)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        server_socket.bind(('localhost', PORT))
        server_socket.listen(100)
        logging.info("Listening on port {} ...".format(PORT))

        workers_list = []
        for id in range(config["WORKERS"]):
            p = multiprocessing.Process(target=worker_run,
                                        args=(id, server_socket,
                                              config["ROOT_DIR"]))
            p.start()
            workers_list.append(p)

        for i in range(config["WORKERS"]):
            workers_list[i].join()

    except KeyboardInterrupt:
        server_socket.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("Unexpected error: {}".format(e))
