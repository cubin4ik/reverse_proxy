import socket
import select
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

IP = '127.0.0.1'
PORT = 8000
BUFF = 2 ** 12

tasks = list()
to_read = dict()
to_write = dict()

HEADERS = [
    'GET / HTTP/1.1',
    'Host: example.com',
    'Connection: keep-alive',
    'Accept: text/html',
    '\n',
]
HTTP_REQUEST = '\n'.join(HEADERS).encode()


def send_request():
    # time.sleep(1)
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server_sock.connect((IP, PORT))
    except socket.error as e:
        logging.info(f'Server {(IP, PORT)} is not responding: {e}')
    else:
        yield 'write', server_sock
        logging.info(f'Sending to server request')
        server_sock.send(HTTP_REQUEST)
        tasks.append(get_response(server_sock))
        tasks.append(send_request())


def get_response(server_sock):
    yield 'read', server_sock
    response = server_sock.recv(BUFF)

    logging.info(f'Receiving from proxy response: {response}')
    server_sock.close()


def event_loop():
    while True:
        while not tasks:
            ready_to_read, ready_to_write, _ = select.select(to_read, to_write, [])

            for sock in ready_to_read:
                tasks.append(to_read.pop(sock))

            for sock in ready_to_write:
                tasks.append(to_write.pop(sock))

        try:
            task = tasks.pop(0)
            reason, sock = next(task)

            if reason == 'read':
                to_read[sock] = task
            if reason == 'write':
                to_write[sock] = task
        except StopIteration:
            print('End of iteration.')


if __name__ == '__main__':
    tasks.append(send_request())
    event_loop()
