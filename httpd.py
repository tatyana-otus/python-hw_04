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
        server_fd = server_socket.fileno()
        e = select.epoll()
        e.register(server_fd, select.EPOLLIN)
        while True:
            events = e.poll(1)
            for fd, event_type in events:
                if fd == server_fd:  # server socket
                    accept_soc(server_socket, e, connections, root_dir)
                elif event_type & select.EPOLLIN:
                    read_soc(e, fd, connections)
                elif event_type & select.EPOLLOUT:
                    write_soc(e, fd, connections)
                else:
                    close_soc(e, fd, connections)
    except KeyboardInterrupt:
        logging.debug("Http Worker {} Stop".format(id))
        e.unregister(server_fd)
        e.close()


def accept_soc(server_soc, e, connections, root_dir):
    try:
        client_socket, address = server_soc.accept()
        client_socket.setblocking(0)
        client_fd = client_socket.fileno()
        e.register(client_fd, select.EPOLLIN)
        connections[client_fd] = http_session.Session(client_socket, root_dir)
    except BlockingIOError:
        pass


def write_soc(e, fd, connections):
    if not connections[fd].write():
        e.modify(fd, select.EPOLLOUT)
        return
    if not connections[fd].keepalive:
        close_soc(e, fd, connections)
    else:
        e.modify(fd, select.EPOLLIN)


def read_soc(e, fd, connections):
    if not connections[fd].read():
        close_soc(e, fd, connections)
        return
    if not connections[fd].is_writeable():
        return
    write_soc(e, fd, connections)


def close_soc(e, fd, connections):
    e.unregister(fd)
    connections[fd].socket.close()
    del connections[fd]


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
