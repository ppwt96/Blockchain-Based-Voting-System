"""
Block object store information about a number of transactions.

The BLock class is used for storing a normal block.

The Mining Block class inherits from the Block and Thread Classes, and it is used to carry out the mining algorithm.
"""

from time import time_ns
from hashlib import sha256
import threading


class Block:
    def __init__(self, ph, txs, difficulty, height, genesis=False, callback=None):
        self.callback = callback
        if not genesis:
            self.timestamp = time_ns()  # Nano Seconds since epoch
        else:
            self.timestamp = 0  # By definition, genesis block has a timestamp of 0

        self.transactions = txs  # List of transaction objects
        self.order_transactions()
        self.previous_hash = ph  # 64 character string
        self.difficulty = difficulty
        self.nonce = 0  # nonce starts at 0 by default and is used for mining
        self.hash = self.generate_hash()
        self.genesis = genesis  # Boolean value
        self.height = height  # Points to where the block is in the chain so it can be found easily

    def generate_hash(self):
        """
        Method computes the hash of the block using the sha256 algorithm.
        :return: string
        """
        d = str(self.timestamp) + str(self.previous_hash) + str(self.nonce) + self.get_transaction_data()
        return sha256(d.encode()).hexdigest()

    def order_transactions(self):
        """
        Orders the transaction objects by their timestamp.
        :return: None
        """
        self.transactions.sort(key=lambda x: x.timestamp)  # Orders the transaction objects based on their timestamp

    def get_transaction_data(self):
        """
        Converts the transaction objects into a string to be passed into the hashing algorithm.
        Inputs and Outputs are dictionaries, and just converting the dictionary to a string is bad because the keys are
        in a random order. This method ensures that the correct string is produced every time.
        :return: string
        """
        data = ''
        self.order_transactions()
        for tx in self.transactions:
            tx.order_inputs_and_outputs()
            data += tx.get_core_data()
            for i in tx.inputs:
                data += str(i['txid']) + str(i['value']) + str(i['index']) + str(i['type']) + str(i['recipient']) + str(
                    i['sig'])

            for o in tx.outputs:
                data += str(o['txid']) + str(o['value']) + str(o['index']) + str(o['type']) + str(o['recipient']) + str(
                    o['sig'])

        return data

    def validate_transactions(self):
        """
        Looks for an invalid transaction in the block.
        :return: Bool
        """
        for tx in self.transactions:
            if not tx.verify():
                return False
        else:
            return True

    def get_dictionary_form(self):
        """
        Converts block object into a dictionary.
        :return: dict
        """
        t = []
        for tx in self.transactions:
            t.append(tx.get_dictionary_form())
        d = {'timestamp': self.timestamp, 'hash': self.hash, 'previous_hash': self.previous_hash, 'nonce': self.nonce,
             'difficulty': self.difficulty, 'height': self.height, 'transactions': t}
        return d

    def get_sending_form(self):
        """
        Converts block into a dictionary that can be used to send the block to other devices.
        Different from get_dictionary_form() because extra formatting needs to be done with the signatures in the
        transactions.
        :return: dict
        """
        t = []
        for tx in self.transactions:
            t.append(tx.get_sending_form())
        d = {'timestamp': self.timestamp, 'hash': self.hash, 'previous_hash': self.previous_hash,
             'nonce': self.nonce,
             'difficulty': self.difficulty, 'height': self.height, 'transactions': t, 'data': self.get_transaction_data()}
        return d


class MiningBlock(Block, threading.Thread):
    """
    Inherits from Block because it is a form of a block.
    Inherits from Thread because mining needs to be done on a separate thread to the rest of the program.
    """
    def __init__(self, ph, txs, difficulty, height, genesis=False, callback=None):
        super(MiningBlock, self).__init__(ph, txs, difficulty, height, genesis=genesis, callback=callback)
        threading.Thread.__init__(self)
        self.terminate_flag = threading.Event()

    def mining_algorithm(self, tx_data):
        """
        Calculates hash as part of the mining algorithm.
        Different to generate_hash() because it doesn't call get_transaction_data() each time.

        :param tx_data: string
        :return: string
        """
        d = str(self.timestamp) + str(self.previous_hash) + str(self.nonce) + tx_data
        return sha256(d.encode()).hexdigest()

    def mine_block(self):
        """
        Mining algorithm.
        :return: None
        """
        string = self.get_transaction_data()
        if self.callback is not None:
            self.callback.debug_print('Mining Block: Started Mining')
        while self.mining_algorithm(string)[0:self.difficulty] != '0' * self.difficulty and not self.terminate_flag.is_set():
            self.nonce += 1

        self.hash = self.generate_hash()

        return

    def stop(self):
        """
        Terminates the thread.
        :return:
        """
        self.terminate_flag.set()

    def run(self):
        """
        Main loop of the thread
        :return: None
        """
        self.mine_block()

        if self.callback is not None:
            if self.terminate_flag.is_set():
                self.callback.debug_print('Mining BLock: Mining terminated')
            else:
                self.callback.debug_print('Mining Block: Finished mining')
                self.callback.finished_mining(self)
