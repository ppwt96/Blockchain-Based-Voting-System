# Handler Object
import threading
import time
import socket
from node import Node
import json
from blockchain import Blockchain
from block import Block
from transaction import Transaction


class NodeHandler(threading.Thread):
    """
    Handler Object manages a devices connections and blockchain.
    """

    # These attributes are standard for every device, and are required for the p-2-p network
    default_peer = '10.37.0.42'
    port = 54846
    version = '1.0'
    services = 0

    def __init__(self, path, app=None):
        super(NodeHandler, self).__init__()
        self.terminate_flag = threading.Event  # Flag that is set when we call for the node to be stopped
        self.GUI = app  # All print messages will go back to this method so they will appear on the GUI

        self.blockchain = Blockchain(path, handler=self)  # This nodes version of the blockchain

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # To get the internal IP address of the device running this code
            s.connect(('10.255.255.255', 1))
            self.IP = s.getsockname()[0]
        except Exception:
            self.IP = '127.0.0.1'
        finally:
            s.close()

        self.peers = []  # List of the IP addresses of nodes that we are connected to
        self.known_peers = [self.default_peer]  # List of IP addresses that are on the network
        self.visited = []  # List of IP addresses that we have visited
        self.connecting_thread = None  # Stores Thread object that is trying to connect to a Node

        self.max_peers = 5  # The maximum number of peers that a node can have

        self.node = Node(self.IP, NodeHandler.port, self.callback)
        self.GUI.device_id = self.node.id
        self.GUI.blockheight = str(self.blockchain.block_height)

        self.GUI.ip = self.IP
        self.GUI.default_node = self.default_peer
        self.GUI.max_peers = str(self.max_peers)

        self.last_connection = '0.0.0.0'
        self.blocks_mined = 0  # Stores how many blocks have been mined

        self.attempts = 0  # Stores how many attempts have been made to get the blockchain from a node.

    def debug_print(self, msg):
        """
        Prints messages to the Console of the GUI.
        :param msg:
        :return:
        """
        self.GUI.print(msg)

    def start_node(self):
        """
        Starts this devices main node
        :return: None
        """
        self.node.init_server()
        if self.node.flag:
            self.node.start()
        else:
            self.debug_print('Handler: Problem starting the node')

        self.establish_connection_with_network()

    def establish_connection_with_network(self):
        """
        Method that performs a breadth first search of the network.
        :return:
        """
        if self.connecting_thread is None and len(self.known_peers) > 0:
            if len(self.node.outbound_nodes) < 2:
                self.connecting_thread = threading.Thread(target=self.node.connect_to_node,
                                                          args=(self.known_peers[0], NodeHandler.port))
                self.connecting_thread.start()

    def stop_node(self):
        """
        Stops the main node.
        Called when the user quits the application.
        :return: None
        """
        if self.node is not None:
            self.debug_print('Preparing to stop node')
            self.node.send_to_nodes(self.create_message({'msg': 'disconnect'}))
            self.node.terminate_flag.set()

    def create_message(self, dictionary):
        """
        Converts dictionary into a JSON object for sending.
        :param dictionary: dict
        :return: dict
        """
        try:
            data = dictionary
            data['time'] = str(time.time_ns())
            if self.node is not None:
                data['snid'] = self.node.id
                pass
            return json.dumps(data)

        except Exception as e:
            raise e

    def send_peers(self, n=None):
        """
        Sends a list of our peers to a node
        :param n:
        :return:
        """
        if n is not None:
            if len(self.peers) > self.max_peers:
                self.debug_print('Handler: exceeded max peers')
                self.node.send_to_node(n, self.create_message({'msg': 'disconnect', 'peers': self.peers}))
            else:
                self.node.send_to_node(n, self.create_message({'peers': self.peers}))
        else:
            self.node.send_to_nodes(self.create_message({'peers': self.peers}))

    def handshake(self, n):
        """
        Initializes the handshake between two nodes.
        It is only called if we have formed an outbound connection.
        :param n: Connection
        :return: None
        """
        d = {'msg': 'version_req'}
        self.node.send_to_node(n, self.create_message(d))

    def get_blocks(self, n):
        """
        Requests blocks from another node.
        :param n: Connection
        :return: None
        """
        d = {'get_blocks': [self.blockchain.block_height, self.blockchain.block_height+8]}
        self.node.send_to_node(n, self.create_message(d))

    def broadcast_block(self, ex=None):
        """
        Sends a block to our peers
        :param ex: Node - The node that we don't want to send the block back to
        :return: None
        """
        d = {'new_block': self.blockchain.get_last_block().get_sending_form()}
        if ex is not None:
            self.node.send_to_nodes(self.create_message(d), [ex])
        else:
            self.node.send_to_nodes(self.create_message(d))

    def broadcast_blockheight(self):
        """
        Sends our blockheight to our peers
        :return: Node
        """
        d = {'block_height': self.blockchain.block_height}
        self.node.send_to_nodes(self.create_message(d))

    def broadcast_tx(self, tx, ex=None):
        """
        Sends a transaction to our peers.
        :param tx: Transaction
        :param ex: Node - The node that we don't want to send the transaction back to
        :return: None
        """
        d = {'new_tx': tx.get_sending_form()}
        if ex is not None:
            self.node.send_to_nodes(self.create_message(d), [ex])
        else:
            self.node.send_to_nodes(self.create_message(d))

    def send_memory_pool(self, n):
        """
        Sends our memory pool to another node.
        :param n: Connection
        :return: None
        """
        d = {'mem_pool': [tx.get_sending_form() for tx in self.blockchain.memory_pool]}
        self.node.send_to_node(n, self.create_message(d))

    def request_memory_pool(self, n):
        """
        Sends a request message for a node's memory-pool
        :param n: Connection
        :return: None
        """
        self.node.send_to_node(n, self.create_message({'msg': 'mem_pool_req'}))

    def create_block(self, b):
        """
        Converts a block dictionary back to a Block object.
        :param b: dict
        :return: Bool - States if the block was built properly or not.
        """
        transactions = []
        for tx in b['transactions']:
            transactions.append(self.create_transaction(tx))

        new_block = Block(b['previous_hash'], transactions, b['difficulty'], b['height'])
        new_block.nonce = b['nonce']
        new_block.timestamp = b['timestamp']
        if new_block.generate_hash() == b['hash']:
            new_block.hash = b['hash']
            new_block.encoded = b
            self.debug_print("Handler: Block correctly built")
            if self.blockchain.add_block(new_block):
                return True
        else:
            self.debug_print('Handler: Incorrectly Built BLock')
        return False

    def create_transaction(self, tx):  # tx is a transaction in dictionary form
        """
        Convers transaction dictionary into a Transaction object.
        :param tx: dict
        :return: Transaction
        """
        new_tx = Transaction(tx['type'], tx['value'], None, None, self.blockchain)
        new_tx.txid = tx['txid']
        new_tx.timestamp = tx['timestamp']
        new_tx.inputs = tx['inputs']
        new_tx.outputs = tx['outputs']
        new_tx.from_address = new_tx.inputs[0]['recipient']
        to_addr = []
        for i in new_tx.inputs:
            if i['sig'] is not None:
                i['sig'] = i['sig'].encode('utf-8')

        for o in new_tx.outputs:
            if o['recipient'] not in to_addr:
                to_addr.append(o['recipient'])

            if o['sig'] is not None:
                o['sig'] = o['sig'].encode('utf-8')

        if new_tx.type == 2:
            new_tx.outputs[0]['value']['sig'] = new_tx.outputs[0]['value']['sig'].encode('utf-8')
            new_tx.value['sig'] =new_tx.value['sig'].encode('utf-8')
        new_tx.to_address = to_addr
        return new_tx

    def handler(self, data, n):
        """
        Method that handles incoming messages.
        :param data: JSON dictionary
        :param n: Connection - Connection that received the message
        :return: None
        """
        msg = json.loads(data)
        items = [i[0] for i in msg.items()]
        try:
            if 'new_block' in items:
                self.debug_print('Recieved New Block')
                if self.create_block(msg['new_block']):
                    self.broadcast_block(n)

            if 'new_tx' in items:
                tx = self.create_transaction(msg['new_tx'])
                self.blockchain.add_transaction(tx, n)

            if 'peers' in items:
                new = [p for p in msg['peers'] if p not in self.peers and p != self.IP and p not in self.known_peers]
                self.debug_print('Handler: New Peers:' + str(new))
                self.known_peers += new
                if n in self.node.outbound_nodes and 'msg' not in items:
                    self.handshake(n)

            if 'version' in items:
                array = msg['version']  # Array is in the form [version, services, blockheight]
                self.debug_print('Version ' + str(array))
                n.version = array[0]
                n.services = array[1]
                n.blockheight = array[2]
                if array[2] > self.blockchain.block_height:
                    self.get_blocks(n)
                else:
                    self.request_memory_pool(n)

            if 'msg' in items:
                string = msg['msg']
                if string == 'version_req':
                    if len(self.peers) > self.max_peers:
                        d = {'msg': 'disconnect'}
                        self.node.send_to_node(n, self.create_message(d))
                        self.node.disconnect_from_node(n)
                        return

                    d = {'version': [NodeHandler.version, NodeHandler.services, self.blockchain.block_height]}

                    if n.version == '':
                        d['msg'] = 'version_req'  # If we don't know data about the node, we request it from them.
                    self.node.send_to_node(n, self.create_message(d))

                elif string == 'disconnect':  # Tells us that the connection is ending
                    self.node.disconnect_from_node(n)

                elif string == 'mem_pool_req':
                    self.send_memory_pool(n)

            if 'get_blocks' in items:
                if msg['get_blocks'][0] <= self.blockchain.block_height-8:
                    blocks = [self.blockchain.database.block_from_height(i).get_sending_form() for i in range(msg['get_blocks'][0]+1,msg['get_blocks'][0]+8)]

                else:
                    blocks = [self.blockchain.database.block_from_height(i).get_sending_form() for i in range(msg['get_blocks'][0]+1,self.blockchain.block_height+1)]

                d = {'blocks': blocks}
                m = self.create_message(d)

                self.node.send_to_node(n, m)

            if 'blocks' in items:
                h = self.blockchain.block_height
                blocks = msg['blocks']
                for block in blocks:
                    self.create_block(block)

                if n.blockheight > self.blockchain.block_height and self.attempts < 4:  # Stops and infinite loop
                    if self.blockchain.block_height == h:
                        self.attempts += 1
                    self.get_blocks(n)
                elif n.blockheight == self.blockchain.block_height:
                    self.broadcast_blockheight()
                    self.request_memory_pool(n)
                else:
                    self.attempts = 0

            if 'block_height' in items:
                n.blockheight = msg['block_height']

            if 'mem_pool' in items:
                for tx in msg['mem_pool']:
                    self.blockchain.add_transaction(self.create_transaction(tx))

        except Exception as e:
            print(e)
            raise e

    def callback(self, event, node, other, data):
        """
        Callback method for the main node. A way of handling new/broken connections and messages.
        :param event: string
        :param node:
        :param other: Connection
        :param data: string
        :return: None
        """
        if 'disconnected' in event:
            self.peers.remove(other.host)
            l = len(self.peers)
            self.GUI.connections = str(l)
            if l == 0:
                self.GUI.status = 'Disconnected'
            if other.type == 0:
                self.GUI.inbound.remove(str(other))
            elif other.type == 1:
                self.GUI.outbound.remove(str(other))
            self.GUI.update_network()
            self.establish_connection_with_network()

        elif "connected" in event:
            self.peers.append(other.host)
            self.GUI.status = 'Connected'
            self.GUI.connections = str(len(self.peers))
            self.last_connection = other.id
            # When two nodes connect, one will create an inbound connection and the other will create an outbound connection
            if event == "inbound_node_connected":
                self.send_peers(other)
                self.GUI.inbound.append(str(other))
                self.GUI.update_network()

            elif event == "outbound_node_connected":
                self.GUI.outbound.append(str(other))
                del self.connecting_thread
                self.connecting_thread = None
                self.visited.append(self.known_peers.pop(0))
                if len(self.peers) > self.max_peers:
                    self.debug_print('Max Peers Exceeded')
                    self.node.disconnect_from_node(other)

                self.GUI.update_network()

        elif "node_message" == event:
            self.handler(data, other)
            self.GUI.received = time.ctime(self.node.last_recv/1e9)
            return

        elif 'failed' in event and len(self.peers) <= 0:  # Called when we can't form an outbound connection

            self.GUI.status = 'Not Connected'
            del self.connecting_thread
            self.connecting_thread = None
            self.known_peers.pop(0)
            self.establish_connection_with_network()

        elif 'print' == event:
            self.debug_print(data)

        elif 'update_last_send' == event:
            self.GUI.sent = time.ctime(self.node.last_send/1e9)

    def get_node(self, id):
        """
        method used for retrieving connection from its id
        :param id: string
        :return: Connection
        """
        for n in self.node.inbound_nodes:
            if n.id == id:
                return n
        for n in self.node.outbound_nodes:
            if n.id == id:
                return n

    def block_mined(self):  # Called when we mine a block
        self.GUI.update_blockchain()
        self.broadcast_block()
        self.broadcast_blockheight()

    def block_added(self):  # Called when we add a block that we haven't mined
        self.GUI.update_blockchain()
        self.broadcast_blockheight()

    def tx_added(self, tx, ex):  # Called when we add a transaction to our memory pool
        self.broadcast_tx(tx, ex)
        self.GUI.update_blockchain()

