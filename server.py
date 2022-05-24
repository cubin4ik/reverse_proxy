import socket
import selectors
import logging
import time
from datetime import datetime, timedelta

IP = '127.0.0.1'
PORT = int(input('Enter port number: '))
QUEUE = 20
BUFF_SIZE = 2 ** 12
HANDLE_TIME = 3  # server load simulation
LOG_TIMEOUT = timedelta(seconds=2)
last_logged_time = datetime.now()
active_sockets = []

selector = selectors.DefaultSelector()
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def server():
    host_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host_socket.bind((IP, PORT))
    host_socket.listen(QUEUE)
    logging.info(f'Started server at {IP}:{PORT}')

    selector.register(fileobj=host_socket,
                      events=selectors.EVENT_READ,
                      data=accept_connection)


def accept_connection(host_socket):
    remote_socket, address = host_socket.accept()
    active_sockets.append(remote_socket)

    selector.register(fileobj=remote_socket,
                      events=selectors.EVENT_READ,
                      data=handle_request)


def handle_request(remote_socket):
    request = remote_socket.recv(BUFF_SIZE)

    if request:
        time.sleep(HANDLE_TIME)  # IO latency simulation
        remote_socket.send(request)
    else:
        pass

    selector.unregister(remote_socket)
    remote_socket.close()
    active_sockets.remove(remote_socket)


def update_log_time():
    last_logged_time = datetime.now()


def delay():
    return (datetime.now() - last_logged_time) < LOG_TIMEOUT


def event_loop():
    while True:
        events = selector.select()

        if not delay():
            logging.info(f'Requests on server: {len(active_sockets)}')
            update_log_time()

        for key, bitmap in events:
            callback = key.data
            callback(key.fileobj)


if __name__ == '__main__':
    server()
    event_loop()
