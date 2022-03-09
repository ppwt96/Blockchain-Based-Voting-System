import sqlite3
from hashlib import sha256
from ecdsa import SigningKey, SECP256k1
from cryptography.fernet import Fernet
import base64
import os


class Wallet:
    """
    The Wallet object assumes multiple tasks:
        -Manages the database that stores the user's data
        -Manages the user's private and public keys
        -Signs transactions
    """
    def __init__(self, path, username=None, password=None):

        with sqlite3.connect(path + '/Wallets.db') as self.db:
            self.cursor = self.db.cursor()
        self.database_setup()
        self.username = None
        self.userID = None
        self.password = None  # *Misleading Name* This is the hash of the actual password

        self.sk = None
        self.private_key = None
        self.public_key = None
        self.address = None
        self.iterations = None

        self.empty_tks = 0
        self.number_pending_votes = 0
        self.pending_tokens = []
        self.txs = []

        self.polls = []

    def login(self):
        """
        Method is called by GUI when the user attempts a login.
        It retrieves the private key of the user to create a SingingKey object, with is needed to sign transactions.
        :return: Bool - Whether the login details provided were valid or not.
        """
        self.cursor.execute('SELECT userID FROM Users WHERE username = ?', [self.username])
        results = self.cursor.fetchall()
        if len(results) == 1:
            self.userID = results[0][0]
            self.cursor.execute('SELECT password, private_key FROM passwords WHERE userID = ?', [self.userID])
            results = self.cursor.fetchall()[0]
            h = results[0]
            key = results[1]
            d = sha256(self.password).hexdigest()
            if d == h:
                self.private_key = key
                self.sk = self.get_key()
                self.address = self.sk.get_verifying_key().to_string('compressed').hex()
                self.iterations = self.get_max_iteration()
                self.get_titles()
                return True
            else:
                return False
        else:
            return False

    def new_user(self):
        """
        Called when the user attempts to create a new account.
        It creates a new private and public key pair for the user, and logs them on the database.
        :return: string - to be used by the GUI
        """
        self.cursor.execute('SELECT userID FROM Users WHERE username = ?', [self.username])
        if len(self.cursor.fetchall()) >= 1:
            return 'Username Already Exists'

        self.sk = SigningKey.generate(curve=SECP256k1)
        self.public_key = self.sk.get_verifying_key().to_string('compressed')
        self.address = self.public_key.hex()
        string = self.sk.to_string()
        checksum = sha256(string).digest()[0:8]  # Calculate and add checksum to the private key
        key = base64.b32encode(string + checksum)
        f = Fernet(base64.b64encode(self.password))

        self.private_key = f.encrypt(key)  # Encrypt private key

        self.cursor.execute('INSERT INTO Users (username) VALUES (?);', [self.username])
        self.cursor.execute('SELECT userID FROM Users WHERE username = ?', [self.username])
        self.userID = (self.cursor.fetchall()[0][0])
        self.cursor.execute('INSERT INTO Passwords (userID,password, private_key) VALUES (?,?,?)',
                            [self.userID, sha256(self.password).hexdigest(), self.private_key])
        self.db.commit()
        self.iterations = self.get_max_iteration()
        return 'User Successfully Added'

    def get_key(self, key=None):  # Key is encrypted
        """
        Method decrypts the private key stored in the database and then converts it into a SigningKey object.
        :param key: bytes
        :return: SigningKey
        """
        if key is None:
            key = self.private_key

        f = Fernet(base64.b64encode(self.password))

        sk = f.decrypt(key)  # Decrypts the private key

        sk = base64.b32decode(sk)

        if sha256(sk[0:32]).digest()[0:8] != sk[32:]:  # Checking Checksum
            return

        return SigningKey.from_string(sk[0:32], curve=SECP256k1)

    def create_next_signing_key(self):
        """
        Creates a deterministic SigningKey.
        Used for creating the key pair for the user's polls
        :return: SigningKey, int (Represents how many times we have created a deterministic key)
        """
        i = self.get_max_iteration()
        sk = SigningKey.from_string(sha256(i[1]).digest(), SECP256k1)
        return sk, i[0] + 1

    def insert_key(self, signing_key, n):
        """
        Encrypts and adds private keys to Keys table of the database.
        :param signing_key: SigningKey
        :param n: int
        :return: None
        """
        string = signing_key.to_string()
        checksum = sha256(string).digest()[0:8]
        k = base64.b32encode(string+checksum)
        f = Fernet(base64.b64encode(self.password))
        key = f.encrypt(k)

        sql = '''
        INSERT INTO Keys (userId, key, iteration) VALUES(?,?,?)
        '''
        self.cursor.execute(sql, [self.userID, key, n])
        self.db.commit()
        self.iterations = [self.iterations[0]+1, key]

    def hash_password(self, password):
        """
        Ensures that we only store the hash of the password in memory.
        :param password: string
        :return: None
        """
        self.password = sha256(password.encode()).digest()

    def sign_transaction(self, tx):
        """
        Method that signs transactions.
        :param tx: Transaction
        :return: None
        """
        if tx.from_address == self.address:  # Dynamically determines whether to use the master key or a poll key.
            sk = self.sk
        else:
            sk = self.get_key(self.get_key_from_address(tx.from_address))

        strings = tx.get_outputs()
        for output in tx.outputs:
            output['sig'] = base64.b64encode(sk.sign(strings[output['index']].encode()))

    def sign_token(self, tk):
        """
        Method that signs a token for the user.
        Only used for submitting a vote.
        When serializing a Token, they do not need to be signed.
        :param tk: Token
        :return: None
        """
        tk.sig = base64.b64encode(self.sk.sign(tk.get_signing_data().encode()))

    def database_setup(self):
        """
        Sets up the database that stores information about the users.
        :return: None
        """
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Users(
            userID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            username VARCHAR
            );
            """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Passwords(
            userID INTEGER NOT NULL PRIMARY KEY,
            password CHAR(64) NOT NULL,
            private_key CHAR(64) NOT NULL,
            FOREIGN KEY (userID) REFERENCES Users(userID)
            );
            """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Keys(
            keyID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            userID INTEGER NOT NULL,
            key CHAR(64) NOT NULL,
            iteration INTEGER NOT NULL,
            FOREIGN KEY (userID) REFERENCES Users(userID)
            );
            """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Polls(
            pollID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            title VARCHAR NOT NULL,
            question VARCHAR NOT NULL,
            address VARCHAR NOT NULL,
            keyID INTEGER,
            FOREIGN KEY (keyID) REFERENCES Keys(keyID)
            );
            """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Options(
            pollID NOT NULL,
            ind CHAR(1),
            answer VARCHAR NOT NULL,
            frequency INTEGER,
            PRIMARY KEY (pollID, ind),
            FOREIGN KEY (pollID) REFERENCES Polls(pollID)
            );
            """)

    def get_max_iteration(self):
        """
        Finds how many times a user has created a deterministic key
        :return: [int, SigningKey]
        """
        sql = '''
        SELECT MAX(iteration), key FROM KEYS
        WHERE userID = ?
        '''

        self.cursor.execute(sql, [self.userID])
        r = self.cursor.fetchall()[0]
        if r[0] == None:
            return [0, self.sk.to_string()]
        else:
            return [r[0], self.get_key(r[1]).to_string()]

    def get_key_id(self, iteration):
        """
        Gets the key ID from its iteration.
        :param iteration:
        :return:
        """
        self.cursor.execute('SELECT keyID FROM Keys WHERE iteration = ? AND userID = ?', [iteration, self.userID])
        return self.cursor.fetchall()[0][0]

    def get_key_from_db(self, id):
        """
        Retrieves the private key from the database via its KeyID
        :param id: int
        :return: bytes
        """
        self.cursor.execute('SELECT key FROM keys WHERE keyID = ?', [id])
        return self.cursor.fetchall()[0][0]

    def get_key_from_address(self, addr):
        """
        Retrieves the private key from the database via its public key
        :param addr:
        :return:
        """
        self.cursor.execute('SELECT key From Keys, Polls WHERE Keys.keyId = Polls.keyID AND Polls.address = ?', [addr])
        return self.cursor.fetchall()[0][0]

    def valid_title(self, title):
        """
        Checks that the title a user wants to use for their poll isn't already being stored in the database under their
        UserID.
        - Multiple users can have a poll that share a title, a single user cannot have polls that share a title.
        :param title: string
        :return: Bool
        """
        sql = '''
        SELECT Polls.title FROM Polls, Keys
        WHERE Polls.title = ? AND Keys.userID = ?
        '''
        self.cursor.execute(sql, [title, self.userID])
        if len(self.cursor.fetchall()) > 0:
            return False
        else:
            return True

    def create_poll(self, title, question, options):
        """
        Creates parameters for a new poll, and stores them in the database.
        :param title: string
        :param question: string
        :param options: 2D List
        :return: None
        """
        sk, n = self.create_next_signing_key()
        self.insert_key(sk, n)

        key_id = self.get_key_id(n)
        key = self.get_key(self.get_key_from_db(key_id))
        address = key.get_verifying_key().to_string('compressed').hex()

        sql = '''INSERT INTO Polls (title, question, address, keyID)
        VALUES (?,?,?,?)
        '''

        self.cursor.execute(sql, [title, question, address, key_id])
        self.db.commit()

        poll_id = self.get_poll_id(title)

        sql = '''
        INSERT INTO Options (pollID, ind, answer, frequency) VALUES (?,?,?,0)
        '''
        for option in options:
            self.cursor.execute(sql, [poll_id, str(option[0]), option[1]])
            self.db.commit()

        self.polls.append(title)

    def get_poll_id(self, title):
        """
        Gets the poll ID from its title.
        The UserID is stored in memory, and assigned when the user logs in.
        :param title:
        :return: int
        """
        self.cursor.execute('SELECT pollID FROM Polls, Keys WHERE title = ? AND userID = ? AND Keys.keyID = Polls.keyID', [title, self.userID])
        return self.cursor.fetchall()[0][0]

    def get_titles(self):
        """
        Gets all of the user's poll titles.
        Used for display in the GUI.
        :return: None
        """
        self.polls = []
        sql = 'SELECT title FROM Polls, Keys WHERE userID = ? AND Polls.keyID = Keys.keyID'
        self.cursor.execute(sql, [self.userID])

        r = self.cursor.fetchall()
        for i in r:
            self.polls.append(i[0])

    def get_poll_info(self, title):
        """
        Retrieves data about a poll from the database.
        :param title: string
        :return: string, string, List.
        """
        pollID = self.get_poll_id(title)
        sql = '''
        SELECT question, address FROM Polls where pollID = ?
        '''
        self.cursor.execute(sql, [pollID])
        r = self.cursor.fetchall()[0]

        q = r[0]
        a = r[1]

        sql = '''
        SELECT answer FROM Options where pollID = ?
        ORDER BY ind
        '''
        self.cursor.execute(sql, [pollID])
        r = self.cursor.fetchall()
        o = []
        for pair in r:
            o.append(pair[0])

        return q, a, o
