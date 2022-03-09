"""
Transaction object records exchanges of funds between addresses
"""

from time import time_ns
from hashlib import sha256
from Token import Token
import ecdsa
import base64
import copy


class Transaction:
    def __init__(self, ty, data, from_addr, to_addr, blockchain=None):
        self.timestamp = time_ns()
        self.type = ty
        self.value = data
        self.from_address = from_addr
        self.to_address = [to_addr]  # Could be a list

        self.inputs = []  # Array of dictionaries
        self.outputs = []  # Array of dictionaries

        self.hash = self.generate_hash()
        self.txid = self.hash[0:32]
        self.blockchain = blockchain

        self.valid = False

    def debug_print(self, msg):
        """
        Method used to print messages that arise from a transaction.
        :param msg: string
        :return: None
        """
        if self.blockchain is not None:
            self.blockchain.debug_print(msg)

    def generate_hash(self):
        """
        Generates hash to create the TXID.
        :return: string
        """
        return sha256(self.get_core_data().encode()).hexdigest()

    def get_inputs(self):
        """
        Method creates inputs for the transaction.
        :return: None
        """
        try:
            if self.from_address == 'blockchain':
                self.inputs.append({'txid': self.txid, 'value': 'Mining Reward', 'index': 0, 'type': 0, 'recipient': 'blockchain', 'sig': None})
                self.create_outputs()

            else:
                if self.type != 2:
                    utxos = self.blockchain.get_utxos_of_type(self.from_address, 0)  # List of dictionary objects
                    values = [i['value'] for i in utxos]
                    if len(values) != 0:
                        values = self.merge_sort(values)
                        total = 0
                        inputs = []
                        n = 0
                        if self.type == 0:
                            target = self.value
                        else:
                            target = 1

                        while total < target and n < len(values):
                            total += values[n]
                            possible_inputs = [j for j in utxos if j['value'] == values[n]]
                            inputs.append(possible_inputs[0])
                            utxos.remove(possible_inputs[0])
                            n += 1

                        if total >= target:
                            self.inputs = inputs
                            self.create_outputs()
                        else:
                            self.debug_print('Transaction: Insufficient funds')
                    else:
                        self.debug_print('Transaction: Cannot get any inputs')
                else:
                    utxos = self.blockchain.get_utxos_of_type(self.from_address, 1)
                    for utxo in utxos:
                        if utxo['value']['tkid'] == self.value['tkid'] \
                                and utxo['value']['voter_address'] == self.from_address \
                                and utxo['value']['poll_address'] == self.to_address[0]:  # Only 1 'to address' in a
                            # type 2 transaction
                            self.inputs.append(utxo)
                            self.create_outputs()
                            return
                    else:
                        self.debug_print('Transaction: cannot use given utxo')
        except Exception as e:
            return

    def merge_sort(self, numbers):
        """
        Values of possible inputs for a transaction are put through a sort. Whilst there are some drawbacks,
        transactions try to spend smaller value inputs before the larger ones.
        :param numbers: List of integers
        :return: List of integers
        """
        arrays = []
        for n in numbers:
            arrays.append([n])

        while len(arrays) > 1:
            temp = []
            for i in range(int(len(arrays)/2)):
                a = arrays[2*i]
                b = arrays[2*i+1]
                temp.append(self.merge_lists(a, b))

            if len(arrays) % 2 != 0:
                temp.append(arrays[-1])

            arrays = temp
        return arrays[0]

    @staticmethod
    def merge_lists(a, b):
        """
        Part of the merge sort algorithm
        :param a: List
        :param b: List
        :return: List
        """
        new = []
        while len(a) > 0 and len(b) > 0:
            if a[0] <= b[0]:
                new.append(a.pop(0))
            else:
                new.append(b.pop(0))

        if len(a) > 0:
            new += a
        else:
            new += b
        return new

    def get_input_total(self):
        """
        Returns the total number of tokes being inputted into the transaction
        :return: int
        """
        total = 0
        for utxo in self.inputs:
            if utxo['type'] == 0 and utxo['value'] != 'Mining Reward':
                total += utxo['value']
            else:
                total += 1
        return total

    def get_output_total(self, change=True):
        """
        Returns the total number of tokens being outputted from the transaction
        :param change: Bool - True if we want to count the change (output that goes back to the sender)
        :return: int
        """
        total = 0
        for output in self.outputs:
            if output['type'] == 0:
                if change:
                    total += output['value']
                elif output['recipient'] != self.from_address:
                    total += output['value']

            else:
                if change:
                    total += 1
                elif output['recipient'] != self.from_address:
                    total += 1

        return total

    def create_outputs(self):
        """
        Method that creates the outputs of the transaction.
        :return: None
        """
        if self.from_address == 'blockchain':

            """
            The index is 0 as there is only one output.
            When the mining reward is released, funds are only given to one address
            """
            self.outputs.append({'value': self.value, 'recipient': self.to_address[0], 'txid': self.txid, 'index': 0,
                                 'type': self.type, 'sig': None})

        else:
            if self.type == 0:
                self.outputs.append({'value': self.value, 'recipient': self.to_address[0], 'txid': self.txid, 'index': 0,
                                     'type': self.type})
                change = self.get_input_total() - self.value
                if change > 0:
                    self.outputs.append({'value': change, 'recipient': self.from_address,
                                        'txid': self.txid, 'index': 1, 'type': self.type})

                    self.to_address.append(self.from_address)
            elif self.type == 1:
                self.outputs.append({'value': self.value, 'recipient': self.to_address[0], 'txid': self.txid, 'index': 0,
                                     'type': self.type})

                change = self.get_input_total() - 1
                if change > 0:
                    self.outputs.append({'value': change, 'recipient': self.from_address,
                                         'txid': self.txid, 'index': 1, 'type': 0})

                    self.to_address.append(self.from_address)
            else:
                self.outputs.append({'value': self.value, 'recipient': self.to_address[0], 'txid': self.txid, 'index': 0,
                                     'type': self.type})

    def add_output(self, value, to_address, ty): # Method to allow for multiple transactions to run off the same inputs
        """
        Allows for multiple transactions to run off the same inputs. For example, an input of 10 empty tokens could be
        converted into two type 1 outputs and one type 0 output (of value 8)
        :param value: int or dict
        :param to_address: string
        :param ty: int
        :return: None
        """
        if ty == 0 and self.type == 0:
            if self.get_input_total() >= self.value + value:
                change = self.get_input_total() - (self.value + value)
                if change > 0:
                    self.outputs[1]['value'] = change  # Changes the amount that will go back the the sender address
                else:
                    self.outputs.pop(1)
                    self.to_address.remove(self.from_address)
                self.outputs.append(
                    {'value': value, 'recipient': to_address, 'txid': self.txid, 'index': 0,
                     'type': self.type})
                self.outputs[-1]['index'] = len(self.outputs) - 1
                self.to_address.append(to_address)

            else:
                self.debug_print('Transaction: Insufficient Funds To Add Output')

        elif ty == 1 and self.type == 1:
            if self.get_output_total(False) <= self.get_input_total() - 1:  # Checks that there is room for at least one more output of type 1

                change = self.get_input_total() - self.get_output_total(False) - 1  # Calculates if there is any change
                if change > 0:
                    self.outputs[1]['value'] = self.get_input_total() - self.get_output_total(False) - 1
                else:
                    self.outputs.pop(1)  # This if fine as the change output is always index 1 until there is no change
                    self.to_address.remove(self.from_address)
                self.outputs.append({'value': value, 'recipient': to_address, 'txid': self.txid, 'index': 0,
                                     'type': ty})
                self.outputs[-1]['index'] = len(self.outputs) - 1
                self.to_address.append(to_address)

            else:
                self.debug_print('Transaction: Requirements not met for another Output')

    def get_outputs(self):  # returns string forms of outputs so they can be signed
        """
        Returns the correct string form of outputs so they can be signed.

        :return: List of strings
        """
        array = []
        for output in self.outputs:
            array.append(str(output['value']) + str(output['recipient']) + str(output['txid']) + str(output['index']))

        return array  # Returns a list as each output is signed individually.

    def verify(self):
        """
        Verifies the transaction.
        :return: Bool
        """
        if self.inputs == [] or self.outputs == []:
            self.debug_print('Transaction(verify): No inputs or outputs')
            return False

        if self.from_address == 'blockchain' and self.inputs[0]['value'] == 'Mining Reward' and self.value == self.blockchain.mining_reward:  # needed to allow the passing of mining reward
            return True
        elif self.from_address == 'blockchain':
            self.debug_print('Transaction (verify) Invalid Coinbase Transaction')
            return False

        if self.type == 0 and (self.value > self.get_output_total() or self.get_output_total(True) != self.get_input_total()):
            self.debug_print('Transaction (verify): Insufficient Funds')
            return False
        elif self.type == 1:
            for o in self.outputs:
                if o['type'] == 1 and o['value']['voter_address'] != o['recipient']:
                    self.debug_print('Transaction (verify): Invalid sending of token')
                    return False

        elif self.type == 2:
            tk = Token().from_dictionary(self.value)
            if not tk.verify():
                self.debug_print('Transaction (verify): Invalid Token')
                return False

        try:
            vk = ecdsa.VerifyingKey.from_string((bytes.fromhex(self.from_address)), curve=ecdsa.SECP256k1)
            for output in self.outputs:
                vk.verify(base64.b64decode(output['sig']), self.get_outputs()[output['index']].encode())

            self.debug_print('Transaction (verify): Transaction Verified')
            return True

        except KeyError:
            self.debug_print('Transaction (verify): There is no signature')
            return False

        except ecdsa.BadSignatureError:
            self.debug_print('Transaction (verify): Bad Signature')
            return False

    def get_core_data(self):
        """
        Gets the data that is used to form the TXID.
        :return: string
        """
        return str(self.timestamp) + str(self.type) + str(self.from_address) + str(self.to_address)

    def get_dictionary_form(self):
        """
        Returns the dictionary form of the Transaction.
        :return:
        """
        if self.type == 0:
            d = {'txid': self.txid, 'timestamp': self.timestamp, 'type': self.type, 'inputs': self.inputs,
                 'outputs': self.outputs, 'value': self.value}
        else:
            d = {'txid': self.txid, 'timestamp': self.timestamp, 'type': self.type, 'inputs': self.inputs,
                 'outputs': self.outputs, 'value': self.value}
        return d

    def get_sending_form(self):
        """
        Returns the dictionary form of the Transaction that can be used to send to other devices.
        Signatures need extra formatting for sending as a JSON object.
        :return: dict
        """
        i = copy.deepcopy(self.inputs)
        o = copy.deepcopy(self.outputs)
        for input in i:
            if input['sig'] is not None:
                input['sig'] = input['sig'].decode('utf-8').replace("'", '"')

        for output in o:
            if output['sig'] is not None:
                output['sig'] = output['sig'].decode('utf-8').replace("'", '"')
                if self.type == 2:
                    output['value'] = Token.from_dictionary(output['value']).get_sending_form()

        if self.type == 0:
            d = {'txid': self.txid, 'timestamp': self.timestamp, 'type': self.type, 'inputs': i,
                 'outputs': o, 'value': self.value}
        else:
            d = {'txid': self.txid, 'timestamp': self.timestamp, 'type': self.type, 'inputs': i,
                 'outputs': o, 'value': Token.from_dictionary(self.value).get_sending_form()}

        return d

    def order_inputs_and_outputs(self):
        """
        Orders inputs and outputs.
        :return: None
        """
        self.inputs.sort(key=lambda x: (x['txid'], x['index']))
        self.outputs.sort(key=lambda x: x['index'])
