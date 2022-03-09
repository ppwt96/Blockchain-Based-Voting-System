"""
Blockchain object stores, manages and performs calculations on the data that makes up the blockchain.
"""

from block import Block, MiningBlock
from transaction import Transaction
from database_manager import BlockchainDatabase


class Blockchain:
    def __init__(self, p, wallet=None, handler=None):
        self.database = BlockchainDatabase(self, p)
        self.block_height = self.database.get_block_height()  # Number of blocks in chain

        self.chain = self.database.create_recent_chain()  # List that stores blocks
        self.memory_pool = []  # List that stores unconfirmed transactions
        self.mining_reward = 10  # Number of tokens given upon mining block

        self.difficulty = 6  # Determines the amount of work required to mine a block

        self.wallet = wallet  # The wallet object of the user using the device
        self.handler = handler  # Handler object of the device
        self.mining = False  # Keeps track of whether we are mining a bock or not on another thread
        self.mining_thread = None

        self.create_genesis_block()

        if wallet is not None:
            self.update_wallet()

    def debug_print(self, msg):
        if self.handler is not None:
            self.handler.debug_print(msg)

    def create_genesis_block(self):
        """
        Creates and adds the genesis block to the blockchain.
        :return: None
        """
        if self.block_height < 0:
            genesis = Block("0" * 64, [], self.difficulty, 0, genesis=True)
            genesis.nonce = 1670
            genesis.hash = genesis.generate_hash()
            self.chain.append(genesis)
            try:
                self.database.add_block(genesis)
            except Exception as e:
                self.debug_print('Blockchain: ' + str(e))
                pass
            self.block_height = 0
            self.debug_print('Blockchain: Added Genesis Block')
        else:
            self.debug_print('Blockchain: Cannot add another genesis block')
        return

    def create_new_block(self, mining=False):
        """
        Creates the backbone for the next block in the chain.
        :param mining: Bool - States whether the block will be used for mining
        :return: Block or MiningBlock
        """
        # Select up to 64 transactions from memory pool
        transactions = self.memory_pool[0:64]
        coinbase = Transaction(0, self.mining_reward, 'blockchain', self.wallet.address, self)
        coinbase.get_inputs()
        transactions.append(coinbase)
        self.debug_print('Blockchain: Creating block')
        if mining:
            return MiningBlock(self.get_last_block().hash, transactions, self.difficulty, self.block_height + 1,
                               callback=self)
        else:
            return Block(self.get_last_block().hash, transactions, self.difficulty, self.block_height + 1,
                         callback=self)

    def add_block(self, block, mined=False):
        """
        Verifies and adds block to the chain.
        :param block: Block
        :param mined: Bool - States whether this device has mined the block or not
        :return: Bool
        """
        self.debug_print('Blockchain: Adding block')
        ch = [self.get_last_block(), block]
        # This if statement validates the block
        if block.validate_transactions() and self.is_valid(ch) and block.height == self.block_height + 1 \
                and '0' * block.difficulty == block.hash[0:block.difficulty] and block.difficulty >= self.difficulty:
            for transaction in block.transactions:
                for tx_input in transaction.inputs:
                    self.update_utxos(tx_input)

            if self.mining:
                self.mining_thread.terminate_flag.set()
            self.mining = False  # This is fine here, as if we receive a valid block, we would stop mining anyway
            self.chain.append(block)
            self.update_chain()
            self.update_memory_pool(block.transactions)

            self.debug_print('Blockchain: Block added')
            self.database.add_block(block)  # This will also add the transactions, inputs, outputs, utxos to database
            self.block_height += 1
            self.update_wallet()
            if mined:
                self.handler.blocks_mined += 1
                self.handler.block_mined()
            else:
                self.handler.block_added()
            if self.handler.GUI.mining:
                self.mine_block()
            return True
        else:
            self.debug_print('Blockchain: Cannot add invalid block')
            if block.height != self.block_height + 1:
                self.debug_print("Blockchain: Problem with block's height")
            elif '0' * block.difficulty != block.hash[0:block.difficulty] or block.difficulty < self.difficulty:
                self.debug_print("Blockchain: Block doesn't conform to required difficulty")
            return False

    def mine_block(self):
        """
        Sets up and starts the mining block.
        :return: None
        """
        if not self.mining:
            self.mining_thread = self.create_new_block(True)
            self.mining = True
            self.mining_thread.start()
        else:
            self.debug_print('Blockchain: Cannot start the mining a block when we are already mining another')

    def finished_mining(self, block):
        """
        Method is called by the MiningBlock when it has finished mining.
        It converts the MiningBlock to a Block for passing into the add_block() method.
        This avoids the possibility of updating the database from different threads at the same time.
        :param block: MiningBlock
        :return: None
        """
        b = Block(block.previous_hash, block.transactions, block.difficulty, block.height)
        b.timestamp = block.timestamp
        b.nonce = block.nonce
        b.hash = block.hash
        if b.hash == b.generate_hash():
            self.add_block(b, True)
        del block  # Deletes thread to avoid collision problems

    def stop_mining(self):
        """
        Terminates the MiningBlock Thread.
        Could be called by the user or when the app is closed.
        :return: None
        """
        if self.mining_thread is not None:
            self.mining_thread.terminate_flag.set()
            del self.mining_thread
            self.mining = None
        else:
            self.debug_print('Blockchain: Cannot terminate mining process when it has not started')

    def add_transaction(self, transaction, node=None):
        """
        Verifies and adds transactions to the memory pool.
        :param transaction: Transaction
        :param node: Connection that we received the transaction from
        :return:
        """
        memory_pool_inputs = []
        if transaction.verify():
            for tx in self.memory_pool:
                if tx.txid == transaction.txid:
                    self.debug_print('Blockchain: Cannot add the same transaction')
                    return
                for i in tx.inputs:
                    memory_pool_inputs.append(i)
            intersection = [i for i in transaction.inputs if i in memory_pool_inputs]
            if intersection:
                self.debug_print('Blockchain: Output used twice, cannot add transaction')

            self.memory_pool.append(transaction)
            self.sort_memory_pool()
            self.update_wallet()
            self.handler.tx_added(transaction, node)
            self.debug_print('Blockchain: Added Transaction')
            return True
        else:
            self.debug_print('Blockchain: Cannot add invalid transaction')
            return False

    def sort_memory_pool(self):
        """
        Sorts the transactions in the memory pool by their timestamp.
        :return: None
        """
        self.memory_pool.sort(key=lambda x: x.timestamp)

    def is_valid(self, chain=None):  # Returns Boolean value
        """
        Verifies that a chain of blocks form a blockchain.
        :param chain: List of Blocks
        :return: Bool
        """
        if chain is None:
            chain = self.chain

        for j in range(1, len(chain)):
            block = chain[j]
            previous_block = chain[j - 1]
            if block.hash != block.generate_hash():  # Checks that the block's hash is valid
                self.debug_print("Blockchain: Problem with block's hash")
                return False
            elif block.previous_hash != previous_block.hash:
                # Checks the the blocks previous hash is the same as the previous blocks hash
                self.debug_print('Blockchain: Problem with p_hash')
                return False

        else:
            return True

    def get_results(self, poll_addr):
        """
        Finds all of the type 2 transactions that have been sent to the poll address.
        :param poll_addr: string
        :return: List of ints
        """
        results = []
        for utxo in self.get_utxos_of_type(poll_addr, 2):
            ans = utxo['value']['ans']
            results.append(ans)

        return results

    def get_serialized_votes(self, poll_addr):
        """
        Finds the number of the type 1 transactions that the poll address has sent
        :param poll_addr: string
        :return: string
        """
        return str(len(self.database.get_serialized_votes(poll_addr)))

    def update_utxos(self, tx_input):
        """
        Calls for the database to update the outputs that have been used as inputs for transactions.
        :param tx_input: dict
        :return: None
        """
        self.database.update_utxo(tx_input)

    def update_chain(self):  # Deletes oldeest items in chain, so it doesn't take up too much memory
        """
        Manages the part of the blockchain that is stored in memory. It deletes oldest items in the chain.
        :return: None
        """
        n = len(self.chain)
        if len(self.chain) > 16:
            del self.chain[0:n - 16]

    def update_memory_pool(self, transactions):
        """
        Removes transactions in the memory pool that are now stored in a block on the blockchain.
        :param transactions: list of Transactions
        :return: None
        """
        txids = [tx.txid for tx in transactions]
        removed = []
        for item in self.memory_pool:
            print(item.txid)
            if item.txid in txids:
                removed.append(item)

        for tx in removed:
            self.memory_pool.remove(tx)

    def get_pending_votes(self, addr=None):
        """
        Gets a users pending votes.
        :param addr: string
        :return: list of Transactions
        """
        if addr is None:
            addr = self.wallet.address
        utxos = self.get_utxos_of_type(addr, 1)
        return utxos

    def print_chain(self, chain=None):
        """
        Prints the blockchain into a readable format.
        Only used when debugging.
        :param chain: List of Blocks
        :return: None
        """
        if chain is None:
            chain = self.chain

        n = 0
        for block in chain:
            print('Block', block.height)
            for item, value in block.get_dictionary_form().items():
                if item == 'transactions':
                    print('    transactions:')
                    for transaction in block.transactions:
                        for it, v in transaction.get_dictionary_form().items():
                            if it == 'inputs' or it == 'outputs':
                                print('        ' + it)
                                for i in v:
                                    print('             ', str(i))
                            else:
                                print('        ' + it + ': ' + str(v))

                        print('')

                else:
                    print('    ' + item + ': ' + str(value))
            n += 1

    def create_chain_from_database(self):
        """
        Calls for the database to convert its data back into a chain of Block objects.
        :return: List of Blocks
        """
        ph = "0" * 64
        ch = []
        for n in range(self.block_height + 1):  # Block-height is 0 only when genesis block is added
            b = self.database.create_block(ph)
            ch.append(b)
            ph = b.hash

        return ch

    def get_last_block(self):
        return self.chain[-1]

    def get_total_number_of_tokens(self, ty,
                                   address=None):
        """
        This gets the number of a particular type of token a user would have if the memory pool was mined.
        :param ty: int
        :param address: str
        :return: int
        """
        if address is None:
            address = self.wallet.address
        total = self.database.get_tokens(address, ty)
        for tx in self.memory_pool:
            if tx.from_address == address:
                if tx.type == 0 and ty == 0:
                    total -= tx.value
                elif tx.type == 1 and ty == 0:
                    for i in tx.inputs:
                        if i['type'] == 0:
                            total -= i['value']
                    for o in tx.outputs:
                        if o['type'] == 0 and o['recipient'] == address:
                            total += 1

                elif tx.type == 2 and ty == 1:  # Type 2 tx only has 1 input and 1 output
                    total -= 1

            elif address in tx.to_address and address != tx.from_address:
                if tx.type == 0 and ty == 0:
                    total += tx.value

                elif tx.type == 1 and ty == 1:
                    total += 1

                elif tx.type == 2 and ty == 2:
                    total += 1

        return total

    def get_actual_number_of_tokens(self, ty,
                                    address=None):  # Tokens that user has access to. i.e can be used in transaction
        """
        The number of a particular type of token that a user can spend in a transaction.
        :param ty: int
        :param address: str
        :return: int
        """
        if address is None:
            address = self.wallet.address

        total = self.database.get_tokens(address, ty)  # Returns Number of tokens according to the mined blockchain
        for tx in self.memory_pool:
            if tx.from_address == address:
                if ty == 0 and tx.type == 0:
                    for i in tx.inputs:
                        total -= i['value']
                elif ty == 0 and tx.type == 1:
                    for i in tx.inputs:
                        total -= i['value']
                elif ty == 1 and tx.type == 2:
                    total -= 1

        return total

    def get_utxos_of_type(self, addr, ty):
        """
        Gets a user's unspent outputs. Used for creating a transaction.
        Method also removes any outputs that are in the memory pool.
        :param addr: str
        :param ty: int
        :return: list of dictionaries
        """
        utxos = self.database.get_utxos(addr, ty)
        outputs = []
        mem_pool_inputs = [i for sub in [tx.inputs for tx in self.memory_pool] for i in sub]
        for u in utxos:
            o = {'txid': u[0], 'index': u[1], 'value': eval(u[2]), 'recipient': u[3], 'sig': u[4],
                 'type': u[5]}
            if o not in mem_pool_inputs:
                outputs.append(o)

        return outputs

    def get_submitted_votes(self, addr=None):
        """
        Gets the number of votes that a user has submitted.
        :param addr: string
        :return: int
        """
        if addr is None:
            addr = self.wallet.address

        t = 0
        for tx in self.memory_pool:
            if tx.type == 2 and tx.from_address == addr:
                t += 1

        r = self.database.get_confirmed_votes(addr)

        t += len(r)
        return t

    def get_confirmed_votes(self, addr=None):
        """
        Gets the number of votes that are stored on the blockchain which have been submitted by a user.
        Provides end-to-end verifiability without revealing how the user voted.
        :param addr: string
        :return: int
        """
        if addr is None:
            addr = self.wallet.address

        r = self.database.get_confirmed_votes(addr)
        return len(r)

    def update_wallet(self):
        """
        Updates attributes in the Wallet object.
        :return: None
        """
        if self.wallet is not None:
            self.wallet.pending_tokens = self.get_pending_votes(self.wallet.address)

            self.wallet.empty_tks = self.get_total_number_of_tokens(0, self.wallet.address)
            self.wallet.number_pending_votes = self.get_actual_number_of_tokens(1)
