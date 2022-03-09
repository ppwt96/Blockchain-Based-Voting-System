"""
Object that manages the database that stores the blockchain.
"""

import sqlite3
from transaction import Transaction
from block import Block
import os


class BlockchainDatabase:
    def __init__(self, blockchain, p,  name='/blockchain', ):
        self.name = name
        with sqlite3.connect(p + name + '.db', check_same_thread=False) as self.db:
            self.cursor = self.db.cursor()

        self.setup_database()
        self.blockchain = blockchain

    def setup_database(self):
        """
        Runs SQL to setup the database.
        :return: None
        """

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS Blocks(
        hash CHAR(64) PRIMARY KEY,
        previous_hash CHAR(64),
        timestamp INTEGER,
        difficulty INTEGER,
        nonce INTEGER,
        height INTEGER
        );
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS Transactions(
        txid CHAR(32) PRIMARY KEY,
        block_hash CHAR(64),
        type INTEGER,
        value TEXT,
        from_address CHAR(64),
        timestamp INTEGER,
        FOREIGN KEY (block_hash) REFERENCES Blocks(hash)
        );
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS Inputs(
        txid CHAR(32),
        output_txid CHAR(32),
        ind INTEGER,
        value TEXT,
        recipient CHAR(64),
        sig BLOB,
        type INTEGER,
        PRIMARY KEY (txid, output_txid, ind),
        FOREIGN KEY (txid) REFERENCES Transactions(txid)
        );
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS Outputs(
        txid CHAR(32),
        ind INTEGER,
        value TEXT,
        recipient CHAR(64),
        sig BLOB,
        utxo BOOLEAN,
        type INTEGER,
        PRIMARY KEY (txid, ind),
        FOREIGN KEY (txid) REFERENCES Transactions(txid)
        );
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS Serialised_Tokens(
        tkid CHAR(16) PRIMARY KEY,
        poll_address CHAR(64),
        voter_address CHAR(64),
        timestamp INTEGER,
        question VARCHAR,
        options VARCHAR,
        ans VARCHAR,
        sig BLOB,
        txid CHAR(32),
        ind INTEGER,
        locked BOOLEAN,
        FOREIGN KEY (txid) REFERENCES Outputs(txid),
        FOREIGN KEY (ind) REFERENCES Outputs(ind)
        );
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS Locked_Tokens(
        tkid CHAR(16) PRIMARY KEY,
        poll_address CHAR(64),
        voter_address CHAR(64),
        timestamp INTEGER,
        question VARCHAR,
        options VARCHAR,
        ans VARCHAR,
        sig BLOB,
        txid CHAR(32),
        ind INTEGER,
        FOREIGN KEY (txid) REFERENCES Outputs(txid),
        FOREIGN KEY (ind) REFERENCES Outputs(ind)
        );
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS Memory_Pool(
        txid CHAR(32),
        ind INTEGER,
        FOREIGN KEY (txid) REFERENCES Outputs(txid),
        FOREIGN KEY (ind) REFERENCES Outputs(ind),
        PRIMARY KEY (txid, ind)
        );
        """)

    def add_block(self, block):
        """
        Adds a block to the database.
        :param block: Block
        :return: None
        """
        sql = '''
        INSERT INTO Blocks VALUES (?,?,?,?,?,?);
        '''
        hash = block.hash
        p_hash = block.previous_hash
        t = block.timestamp
        d = block.difficulty
        n = block.nonce
        h = block.height
        self.cursor.execute(sql, [hash, p_hash, t, d, n, h])
        self.db.commit()
        for transaction in block.transactions:
            self.add_transaction(transaction, hash)

        return

    def add_transaction(self, tx, h):
        """
        Adds a transaction to the database.
        :param tx: Transaction
        :param h: int
        :return: None
        """
        sql = '''
        INSERT INTO Transactions VALUES (?,?,?,?,?,?);
        '''
        self.cursor.execute(sql, [tx.txid, h, tx.type, str(tx.value), tx.from_address, tx.timestamp])
        self.db.commit()

        for i in tx.inputs:
            self.add_input(i, tx.txid)

        for o in tx.outputs:
            self.add_output(o)

        return

    def add_input(self, i, txid):
        """
        Adds an input to the database.
        :param i: dict
        :param txid: string
        :return:
        """
        sql = '''
        INSERT INTO Inputs VALUES (?,?,?,?,?,?,?);
        '''
        self.cursor.execute(sql, [txid, i['txid'], i['index'], str(i['value']), i['recipient'], i['sig'], i['type']])
        self.db.commit()
        return

    def add_output(self, o):
        """
        Adds an output to the database.
        :param o: dict
        :return: None
        """
        sql = '''
        INSERT INTO Outputs VALUES (?,?,?,?,?,?,?);
        '''
        self.cursor.execute(sql, [o['txid'], o['index'], str(o['value']), o['recipient'], o['sig'], True, o['type']])
        self.db.commit()

        if o['type'] == 1:
            self.add_token(o['value'], o['txid'], o['index'])
        elif o['type'] == 2:
            self.update_token(o['value'], o['txid'], o['index'])

    def update_utxo(self, utxo):
        """
        Updates outputs in the database that have now been spent.
        :param utxo:
        :return: None
        """
        sql = '''
        UPDATE Outputs
        SET utxo = FALSE
        WHERE txid = ? AND ind = ?'''

        self.cursor.execute(sql, [utxo['txid'], utxo['index']])
        self.db.commit()

    def get_utxos(self, addr, ty):
        sql2 = '''
        SELECT Outputs.txid, Outputs.ind, Outputs.value, Outputs.recipient, Outputs.sig, type FROM Outputs
        WHERE utxo = TRUE AND recipient = ? and type = ?
        '''

        self.cursor.execute(sql2, [addr, ty])
        results = self.cursor.fetchall()

        return results

    def get_tokens(self, addr, ty):
        """
        Returns the number of tokens of a particular type that haven't been spent, as known by the Blockchain.
        A user's funds can be found from just their UTXO's.
        :param addr:
        :param ty:
        :return:
        """

        sql = '''
        SELECT value FROM Outputs
        WHERE utxo = TRUE AND recipient = ? and type = ?
        '''

        self.cursor.execute(sql, [addr, ty])
        results = self.cursor.fetchall()
        t = 0
        if ty == 0:
            for value in results:
                t += int(value[0])
        else:
            t = len(results)

        return t

    def create_transaction(self, txid):
        """
        Creates a Transaction object from releavnt data in the database
        :param txid: string
        :return: Transaction
        """
        inputs = []
        outputs = []

        sql = '''SELECT type, from_address, txid, timestamp FROM Transactions WHERE txid = ?'''
        self.cursor.execute(sql, [txid])
        results = self.cursor.fetchall()[0]

        tx = Transaction(results[0], None, results[1], None, blockchain=self.blockchain)
        tx.txid = results[2]
        tx.timestamp = results[3]

        sql = '''SELECT * FROM Inputs WHERE txid = ?'''
        self.cursor.execute(sql, [txid])
        results = self.cursor.fetchall()
        for i in results:
            try:
                value = eval(i[3])
            except Exception as e:
                value = i[3]

            inputs.append({'txid': i[1], 'index': i[2], 'value': value, 'recipient': i[4], 'sig': i[5], 'type': i[6]})

        sql = '''SELECT * FROM Outputs WHERE txid = ? ORDER BY ind '''
        self.cursor.execute(sql, [txid])
        results = self.cursor.fetchall()
        addresses = []
        for o in results:
            try:
                value = eval(o[2])
            except Exception as e:

                value = o[2]
            outputs.append({'txid': o[0], 'index': o[1], 'value': value, 'recipient': o[3], 'sig': o[4], 'type': o[6]})


            if o[3] not in addresses:
                addresses.append(o[3])
        tx.to_address = addresses
        tx.value = outputs[0]['value']

        tx.inputs = inputs
        tx.outputs = outputs
        return tx

    def create_block(self, ph):
        """
        Creates a block from the database.
        :param ph: string
        :return: Block
        """
        txs = []

        sql = '''
        SELECT Transactions.txid FROM Transactions
        INNER JOIN Blocks ON Blocks.hash = Transactions.block_hash
        WHERE previous_hash = ?
        '''

        self.cursor.execute(sql, [ph])
        results = self.cursor.fetchall()

        for txid in results:
            txs.append(self.create_transaction(txid[0]))

        sql = '''SELECT difficulty, nonce, hash, timestamp, height FROM Blocks WHERE previous_hash = ?'''

        self.cursor.execute(sql, [ph])
        results = self.cursor.fetchall()[0]

        b = Block(ph, txs, results[3], results[4])
        b.nonce = results[1]
        b.hash = results[2]
        b.timestamp = results[3]
        return b

    def create_recent_chain(self):  # Returns chain of 16 previous blocks
        """
        Creates the chain to be stored in memory by the Blockchain object.
        :return: List of Blocks
        """
        ch = []

        height = self.get_block_height()

        if height >= 16:
            self.cursor.execute('SELECT previous_hash FROM Blocks WHERE height = ?', [height-15])
            ph = self.cursor.fetchall()[0][0]
            for n in range(16):  # Block-height is 0 only when genesis block is added
                b = self.create_block(ph)
                ch.append(b)
                ph = b.hash
        else:
            ph = "0" * 64
            for n in range(height+1):  # Block-height is 0 only when genesis block is added
                b = self.create_block(ph)
                ch.append(b)
                ph = b.hash

        return ch

    def add_token(self, tk, txid, ind):
        """
        Adds a token of type 1 to the database.
        :param tk: dict
        :param txid: string
        :param ind: int
        :return: None
        """
        sql = '''
        INSERT INTO Serialised_Tokens VALUES (?,?,?,?,?,?,?,?,?,?,?)
        '''
        self.cursor.execute(sql, [tk['tkid'], tk['poll_address'], tk['voter_address'], tk['timestamp'], tk['question'],
                                  str(tk['options']), tk['ans'], tk['sig'], txid, ind, False])
        self.db.commit()

    def update_token(self, tk, txid, ind):
        """
        Updates the state of a token of type 1 in the database and adds the version of the token when it is of type 2.
        :param tk: dict
        :param txid: string
        :param ind: int
        :return: None
        """
        sql = '''
        UPDATE Serialised_Tokens
        SET locked = TRUE
        WHERE tkid = ?
        '''

        self.cursor.execute(sql, [tk['tkid']])
        self.db.commit()

        sql = '''
        INSERT INTO Locked_Tokens VALUES (?,?,?,?,?,?,?,?,?,?)
        '''
        self.cursor.execute(sql, [tk['tkid'], tk['poll_address'], tk['voter_address'], tk['timestamp'], tk['question'],
                                  str(tk['options']), tk['ans'], tk['sig'], txid, ind])
        self.db.commit()

    def get_block_height(self):
        """
        Gets the number of blocks that are stored in the database.
        :return: int
        """
        self.cursor.execute('SELECT hash FROM Blocks')
        r = self.cursor.fetchall()
        return len(r) - 1  # -1 is key because of genesis block

    def block_from_height(self,h):
        """
        Creates a Block from the database based on its height.
        :param h: int
        :return: Block
        """
        txs = []

        sql = '''
                SELECT Transactions.txid FROM Transactions
                INNER JOIN Blocks ON Blocks.hash = Transactions.block_hash
                WHERE height = ?
                '''

        self.cursor.execute(sql, [h])
        results = self.cursor.fetchall()

        for txid in results:
            txs.append(self.create_transaction(txid[0]))

        sql = '''SELECT difficulty, nonce, hash, timestamp, previous_hash FROM Blocks WHERE height = ?'''

        self.cursor.execute(sql, [h])
        results = self.cursor.fetchall()[0]

        b = Block(results[4], txs, results[0], h)
        b.nonce = results[1]
        b.hash = results[2]
        b.timestamp = results[3]
        return b

    def get_serialized_votes(self,addr):
        """
        Gets the number of votes that a poll has serialized.
        :param addr: string
        :return: Tuple
        """
        sql = '''
        SELECT txid From Transactions WHERE from_address = ? AND type = 1
        '''

        self.cursor.execute(sql, [addr])
        r = self.cursor.fetchall()
        return r

    def get_confirmed_votes(self, addr):
        """
        Gets the number of votes that a user has stored on the database.
        :param addr: string
        :return: Tuple
        """
        sql = '''
        SELECT txid FROM Transactions WHERE from_address = ? AND type = 2
        '''
        self.cursor.execute(sql, [addr])
        r = self.cursor.fetchall()
        return r
