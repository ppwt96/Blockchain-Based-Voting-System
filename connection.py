import socket
import time
import threading


class Connection(threading.Thread):
    """
    Connection Object is what is used to represent and communicate with another device.
    Inherits attributes from a thread, so it can run without disrupting the rest of the project
    """
    def __init__(self, main_node, sock, id, host, port, ty):
        super(Connection, self).__init__()

        self.main_node = main_node
        self.type = ty  # 0 - inbound, 1 - outbound
        self.sock = sock
        self.terminate_flag = threading.Event()

        self.buffer = ''

        # These variables store key attributes of the node that this connection represents
        self.host = host
        self.port = port
        self.id = id
        self.version = ''  # Version of the node's code
        self.services = ''  # Stores int that tells us what the node can do
        self.last_send = ''  # Time since we last sent something to this
        self.last_recv = ''  # Time since we last received something from this node
        self.blockheight = 0  # How many blocks are stored on the node

        self.debug_print("Connection: Started with client (" + self.id + ") '" + self.host + ":" + str(self.port) + "'")

    def debug_print(self, msg):
        """
        Method for printing.
        :param msg: string
        :return: None
        """
        if self.main_node is not None:
            self.main_node.debug_print(msg)

    def send(self, data):
        """
        Sends a message to the other device
        :param data: JSON message
        :return: None
        """
        try:
            data += '-TSN'  # So the receiving node knows when the message has ended
            self.sock.sendall(data.encode('utf-8'))
            self.last_send = time.time_ns()
            self.main_node.last_send = time.time_ns()
            self.main_node.update_last_send()
        except Exception as e:
            self.debug_print("Connection: Node stopping because of exception " + str(e))
            self.terminate_flag.set()

    def stop(self):
        """
        Terminates the thread.
        :return: None
        """
        self.terminate_flag.set()

    def run(self):
        """
        Main loop of the thread.
        Constantly listens for messages from the connection
        :return: None
        """
        self.sock.settimeout(1)

        while not self.terminate_flag.is_set():
            line = ""

            try:
                line = self.sock.recv(4096)
                self.last_recv = time.time_ns()
                if line == b'':  # Happens when connection breaks - used for hard socket closures
                    self.terminate_flag.set()
            except socket.timeout:
                pass

            except Exception as e:
                self.terminate_flag.set()
                print(e)

            if line != "":
                try:
                    self.buffer += str(line.decode('utf-8'))

                except Exception as e:
                    self.debug_print("Connection: Error decoding line: " + str(e))

                # Get the messages by finding the message ending -TSN
                index = self.buffer.find("-TSN")
                while index > 0:
                    message = self.buffer[0:index]
                    self.buffer = self.buffer[index + 4::]

                    self.main_node.node_message(self, message)

                    index = self.buffer.find("-TSN")

            time.sleep(0.01)

        self.main_node.debug_print('Connection: Connection Stopped with host {}'.format(self.host))
        self.main_node.node_disconnected(self)

    def __str__(self):
        return """Node ID: {}\nAddress: {}""".format(self.id, self.host)
