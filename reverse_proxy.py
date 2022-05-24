import socket
import select
import logging
import configparser

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

targets = dict()
broken_targets = []
config = configparser.ConfigParser()
config.read('servers.conf')

for server_conf in config.sections():
    target_ip = config[server_conf]['IP']
    target_port = int(config[server_conf]['PORT'])

    targets[(target_ip, target_port)] = 0  # initial value of requests on server

# Reverse Proxy configurations
IP, PORT = '127.0.0.1', 8000
BUFF = 2 ** 12
QUEUE = 5

# Event loop feeders
tasks = list()
to_read = dict()
to_write = dict()


def log_load():
    logging.info('------> Current Load <------')
    for target_addr, load in targets.items():
        print(target_addr, load)
    print('-' * 30)


def get_target_addr():
    """Returns address (IP, PORT) of least loaded socket"""

    sock_addr = min(targets, key=targets.get)
    targets[sock_addr] += 1
    log_load()
    return sock_addr


def decrease_server_load(sock_addr):
    if sock_addr in targets:
        targets[sock_addr] -= 1
        log_load()


def remove_target(broken_target_addr):
    """Removes broken server from active servers list"""

    if broken_target_addr in targets:
        pending_requests = targets.pop(broken_target_addr)
        broken_targets.append(broken_target_addr)


def redo_request(client_sock, request):
    """When server is down task should be returned to queue"""

    tasks.append(request_target(client_sock, request))

    # TODO: get all uncompleted tastks back to queue
    # for request in pending_requests:
    #     tasks.append(request(request[0], request[1]))


def update_targets():
    """Checks if any of broken targets are back online"""

    for target in broken_targets:
        ping_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            ping_sock.connect(target)
        except socket.error:
            pass
        else:
            targets[target] = 0
            broken_targets.remove(target)
        finally:
            ping_sock.close()


def run_server():
    proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_sock.bind((IP, PORT))
    proxy_sock.listen(QUEUE)
    logging.info(f'Started server at {IP}:{PORT}')

    while True:
        yield 'read', proxy_sock
        client_sock, address = proxy_sock.accept()
        logging.info(f'Connection from {address}')

        tasks.append(get_request(client_sock))


def get_request(client_sock):
    yield 'read', client_sock
    request = client_sock.recv(BUFF)

    tasks.append(request_target(client_sock, request))


def send_response(client_sock, response):
    yield 'write', client_sock
    client_sock.send(response)
    client_sock.close()


def request_target(client_sock, request):
    if broken_targets:
        update_targets()

    target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    target_addr = get_target_addr()

    try:
        target_sock.connect(target_addr)
    except socket.error:
        remove_target(target_addr)
        redo_request(client_sock, request)
    else:
        yield 'write', target_sock
        target_sock.send(request)
        tasks.append(target_response(target_sock, client_sock, request))


def target_response(target_sock, client_sock, request):
    yield 'read', target_sock
    try:
        response = target_sock.recv(BUFF)
    except socket.error:
        remove_target(target_sock)
        redo_request(client_sock, request)
    else:
        # TODO: check if server is down
        target_addr = target_sock.getpeername()
        target_sock.close()
        decrease_server_load(target_addr)

        tasks.append(send_response(client_sock, response))


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
            job, sock = next(task)

            if job == 'read':
                to_read[sock] = task
            if job == 'write':
                to_write[sock] = task
        except StopIteration:
            pass


if __name__ == '__main__':
    tasks.append(run_server())
    event_loop()
