import socket
import threading
from hashlib import sha512
from connection import Connection
import time


class Node(threading.Thread):
    """
    The Node object acts a server and it is what inbound connections connect to.
    It also manages all connections made.
    """
    def __init__(self, host, port, callback=None):
        super(Node, self).__init__()

        self.terminate_flag = threading.Event()
        self.callback = callback

        self.host = host
        self.port = port

        self.inbound_nodes = []
        self.outbound_nodes = []

        self.id = str(sha512((str(host) + str(port)).encode()).hexdigest())[0:8]

        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.debug = True
        self.flag = False  # True if there is an error in initialising the node

        self.nodeip = ''  # Temporary storage of another node's ip

        self.sent = 0
        self.received = 0

        self.last_send = 0e9  # Time when we last sent a message
        self.last_recv = 0e9  # Time when we last received a message

    def debug_print(self, msg):
        """
        Method for printing
        :param msg: string
        :return: None
        """
        if self.debug:
            self.print_message(msg)

    def init_server(self):
        """
        Initializes the main node
        :return:
        """
        try:
            self.debug_print('Node: Initialising of the Node on port: ' + str(self.port) + ' with host: ' + str(self.host))
            self.s.bind((self.host, self.port))
            self.s.settimeout(10.0)
            self.s.listen(1)
            self.flag = True
        except OSError as e:
            self.debug_print(('Node:  Error Initialising Node ' + str(e)))
            self.flag = False

    def connect_to_node(self, host, port):
        """
        Method for connecting to another Node
        :param host: string
        :param port: int
        :return: Bool
        """
        if host == self.host:
            self.debug_print('Node: Cannot connect to ourselves')
            self.failed_to_connect()
            return False

        for node in self.outbound_nodes:
            if node.host == host and node.PORT == port:
                self.debug_print('Node: Already connected to node')
                return False

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            self.debug_print("Node: Connecting to %s on port %s" % (host, port))
            sock.connect((host, port))

            sock.send(self.id.encode('utf-8'))
            connected_node_id = str(sock.recv(4096).decode('utf-8'))
            time.sleep(0.1)
            server_thread = self.create_connection(sock, connected_node_id, host, port, 1)
            server_thread.start()

            self.outbound_nodes.append(server_thread)
            self.outbound_node_connected(server_thread)

            return True

        except socket.timeout:
            self.debug_print("Node: Can't connect with node: Socket timed out")
            self.failed_to_connect()

        except Exception as e:
            self.debug_print("Node: Couldn't connect  with node:" + str(e))
            self.failed_to_connect()

    def disconnect_from_node(self, node):
        """
        Method for ending a connection with a node.
        :param node: Connection
        :return: None
        """
        if node in self.outbound_nodes:
            node.stop()
            self.outbound_nodes.remove(node)
        elif node in self.inbound_nodes:
            node.stop()
            self.inbound_nodes.remove(node)
        else:
            self.debug_print('Node: Cannot disconnect from node we are not connected to')

    def create_connection(self, connection, id, host, port, ty):
        """
        Creates a Connection object for a newly connected inbound node.
        :param connection: Socket
        :param id: string
        :param host: string
        :param port: string
        :param ty: int
        :return: Connection
        """
        self.nodeip = host  # ip address of the other node
        return Connection(self, connection, id, host, port, ty)

    def send_to_nodes(self, data, exclude=None):
        """
        Send a message to multiple nodes.
        :param data: JSON dictionary
        :param exclude: List of Connections - Connections that we don't want to send message to
        :return:
        """
        if exclude is None:
            exclude = []

        for n in self.inbound_nodes:
            if n not in exclude:
                self.send_to_node(n, data)

        for n in self.outbound_nodes:
            if n not in exclude:
                self.send_to_node(n, data)

    def send_to_node(self, n, d):
        """
        Sends a message to a node
        :param n: Connection
        :param d: JSON dictionary
        :return: None
        """
        if n in self.inbound_nodes or n in self.outbound_nodes:
            n.send(d)
            self.sent += 1
        else:
            self.debug_print('Node: Cannot find node to send to')

    def get_nodes(self):
        """
        Returns arrays of the string formats of our connection.
        Used for displaying information in the UI
        :return: List, List
        """
        outbound_nodes = [str(n) + '\n' for n in self.outbound_nodes]
        inbound_nodes = [str(n) + '\n' for n in self.inbound_nodes]
        return outbound_nodes, inbound_nodes

    def run(self):
        """
        Main Loop of the Thread.
        The Node constantly listens for new nodes that are connecting to us.
        :return: None
        """
        while not self.terminate_flag.is_set():
            try:
                self.debug_print("Node:  Waiting for connections")
                c, a = self.s.accept()
                connected_node_id = c.recv(4096).decode('utf-8')
                self.debug_print('Node: Connected Node Id:' + str(connected_node_id))
                c.send(self.id.encode('utf-8'))
                self.debug_print("Node: Connection received from " + str(a[0]))
                time.sleep(0.1)
                client_thread = self.create_connection(c, connected_node_id, a[0], a[1], 0)
                client_thread.start()

                self.inbound_nodes.append(client_thread)
                self.inbound_node_connected(client_thread)

            except socket.timeout:
                pass

            except KeyboardInterrupt:  # Allows for a clean termination of the program
                self.terminate_flag.set()

            except Exception as e:
                raise e

        self.debug_print("Node: Stopping Node")
        out = self.outbound_nodes
        inbound = self.inbound_nodes
        for p in out:
            p.stop()
            self.outbound_nodes.remove(p)
        for p in inbound:
            p.stop()
            self.inbound_nodes.remove(p)
        time.sleep(1)

        self.s.close()
        self.debug_print("Node:Node Stopped")
        self.node_stopped()

    # These methods are for the callback function in the Handler object
    def inbound_node_connected(self, node):
        if self.callback:
            self.callback("inbound_node_connected", self, node, {})

    def outbound_node_connected(self, node):
        if self.callback:
            self.callback("outbound_node_connected", self, node, {})

    def inbound_node_disconnected(self, node):
        if self.callback:
            self.callback('inbound_node_disconnected', self, node, {})

    def node_disconnected(self, node):
        if self.callback:
            self.callback('node_disconnected', self, node, {})

    def node_message(self, node, msg):
        self.last_recv = time.time_ns()
        if self.callback:
            self.callback('node_message', self, node, msg)
            self.received += 1

    def print_message(self, msg):
        if self.callback:
            self.callback('print', self, None, msg)

    def node_stopped(self):
        if self.callback:
            self.callback('node_stopped', self, None, {})

    def failed_to_connect(self):
        if self.callback:
            self.callback('failed_to_connect', self, None, {})

    def update_last_send(self):
        if self.callback:
            self.callback('update_last_send', self, None, {})
