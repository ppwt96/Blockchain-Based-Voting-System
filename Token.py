# Token Object
from time import time_ns
from hashlib import sha256
import ecdsa
import base64


class Token(object):
    def __init__(self, p_a=None, v_a=None, q=None, o=None, a='', s='', t=None):
        self.poll_address = p_a
        self.voter_address = v_a
        if t is None:
            self.timestamp = time_ns()
        else:
            self.timestamp = t
        self.question = q
        self.options = o
        self.id = self.generate_hash()[0:16]
        self.ans = a
        self.sig = s

    @classmethod
    def from_dictionary(cls, d):
        """
        Instantiates a Token object from the items in a dictionary.
        :param d: dict
        :return: Token
        """
        return cls(p_a=d['poll_address'], v_a=d['voter_address'], q=d['question'], o=d['options'], s=d['sig'],
                   a=d['ans'], t=d['timestamp'])

    def generate_hash(self):
        """
        Used for generating the id of a Token. Anything used in the hash isn't changed over the course of a token being
        serialized to being submitted as a vote.
        :return: string
        """
        return sha256((str(self.poll_address) + str(self.voter_address) + str(self.timestamp) + str(self.question) +
                       str(self.options)).encode()).hexdigest()

    def get_signing_data(self):
        """
        Gets the data that needs to be signed by the user.
        :return: String
        """
        if self.ans != '':
            string = str(self.poll_address) + str(self.voter_address) + str(self.question) \
                    + str(self.options) + str(self.ans)
            return string

    def get_dictionary_form(self):
        """
        Returns the dictionary form of a Token.
        :return: dict
        """
        d = {'tkid': self.id, 'poll_address': self.poll_address, 'voter_address': self.voter_address,
             'question': self.question, 'options': self.options, 'ans': self.ans, 'sig': self.sig,
             'timestamp': self.timestamp}
        return d

    def get_sending_form(self):
        """
        Returns the dictionary form of the Token that can be transmitted to other devices.
        Extra formatting needs to be done for signatures.
        :return:
        """
        if self.sig == '':
            return self.get_dictionary_form()
        else:
            d = {'tkid': self.id, 'poll_address': self.poll_address, 'voter_address': self.voter_address,
                 'question': self.question, 'options': self.options, 'ans': self.ans,
                 'sig': self.sig.decode('utf-8').replace("'", '"'), 'timestamp': self.timestamp}
            return d

    def verify(self):
        """
        Verifies the Token
        :return: Bool
        """
        if self.ans == '':  # Checks that there is a vote
            return False
        if self.sig == '':  # Checks that there is a signature
            return False
        vk = ecdsa.VerifyingKey.from_string((bytes.fromhex(self.voter_address)), curve=ecdsa.SECP256k1)

        try:
            vk.verify(base64.b64decode(self.sig), self.get_signing_data().encode())
            print('Token Valid')
            return True
        except ecdsa.BadSignatureError:
            print('Invalid Token Signature')
            return False
