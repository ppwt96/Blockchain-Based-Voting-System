from kivy.config import Config
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.properties import NumericProperty, ObjectProperty, StringProperty, ColorProperty, BooleanProperty
from kivy.uix.screenmanager import Screen, ScreenManager, NoTransition

from wallet import Wallet
from handler import NodeHandler
from transaction import Transaction
from Token import Token
import time

# Sets the minimum size of the window, so widgets don't overlap with each other.
Config.set('graphics', 'minimum_height', 600)
Config.set('graphics', 'minimum_width', 800)


class RoundedButton(Button):  # Custom class that represents all buttons used in the project
    colour = ColorProperty()
    t_size = NumericProperty(1)


class SeparationLine(Widget):
    pass


class Banner(Widget):  # Class for the banner at the top of the screen
    text = StringProperty()
    btn = StringProperty()
    btn_colour = ColorProperty()
    b = RoundedButton()
    method = ObjectProperty()


class Footer(Widget):  # Class for the footer at the bottom of the screen
    pass


class NodePopup(Popup):  # Popup that displays information about a Node (connection)
    heading = StringProperty()


class LoginPopup(Popup):
    msg = StringProperty()


class TransactionPopup(Popup):  # Popup that displays information about a transaction
    heading = StringProperty()
    method = None
    txt = StringProperty('BACK')

    def button(self):
        self.dismiss()
        if self.method is not None:
            self.method()


class ErrorPopup(Popup):
    heading = StringProperty()


class Option(BoxLayout):
    label = StringProperty()
    index = StringProperty()


class DynamicLabel(Label):
    pass


class LoginScreen(Screen):  # Screen that handles the login of the user
    def __init__(self, n):
        super(LoginScreen, self).__init__()
        self.app = App.get_running_app()
        self.name = n

    def create_new_user(self):
        self.app.manager.current = 'create'

    def login(self, username, password):
        self.app.wallet.username = username
        self.app.wallet.hash_password(password)
        if self.app.wallet.login():
            self.app.manager.current = 'dash'
            self.app.logon()
        else:
            popup = LoginPopup(msg='Invalid Username or Password')
            popup.open()

        self.clear_inputs()

    def clear_inputs(self):
        self.ids.username.text = ''
        self.ids.password.text = ''

    def method(self):  # Needed for when the 'invisible' button is pressed
        pass


class CreateUser(Screen):  # screen that handles the creation of a user
    def __init__(self, n):
        super(CreateUser, self).__init__()
        self.app = App.get_running_app()
        self.name = n

    def method(self):
        self.app.manager.current = 'login'

    def submit(self, username, password, confirm):
        if len(username) == 0 and len(password) == 0:
            msg = 'Please Enter a Username and Password'
        elif password == confirm:
            self.app.wallet.username = username
            self.app.wallet.hash_password(password)
            msg = self.app.wallet.new_user()
        else:
            msg = 'Passwords Do Not Match'

        popup = LoginPopup(msg=msg)
        popup.open()
        self.clear_inputs()
        if msg == 'User Successfully Added':
            self.app.manager.current = 'dash'
            self.app.logon()

    def clear_inputs(self):  # Clears the input boxes, so when screen is revisited, past inputs aren't visible.
        self.ids.username.text = ''
        self.ids.password.text = ''
        self.ids.confirm.text = ''


class Dashboard(Screen):  # Screen that provides an overview for the user and is used for navigation through the app
    def __init__(self, n):
        super(Dashboard, self).__init__()
        self.app = App.get_running_app()
        self.name = n

    def method(self):  # Called when the user wants to log out.
        del self.app.wallet
        self.app.wallet = Wallet(self.app.path)  # Deletes old wallet for security
        self.app.manager.current = 'login'
        self.app.logoff()

    def network(self):
        self.app.manager.current = 'network'

    def transactions(self):
        self.app.manager.current = 'wallet'

    def explorer(self):
        self.app.manager.current = 'explorer'

    def console(self):
        self.app.manager.current = 'console'

    def settings(self):
        self.app.manager.current = 'settings'


class Network(Screen): # Screen that displays the network information
    def __init__(self, n):
        super(Network, self).__init__()
        self.app = App.get_running_app()
        self.name = n

    def on_enter(self, *args):
        self.update_nodes()

    def update_nodes(self):
        self.ids.inbound_grid.clear_widgets()
        self.ids.outbound_grid.clear_widgets()
        for i in self.app.inbound:
            self.ids.inbound_grid.add_widget(
                RoundedButton(colour=(0.17, 0.37, 0.55), text=i, on_release=self.display_node, t_size=2))
        for i in self.app.outbound:
            self.ids.outbound_grid.add_widget(
                RoundedButton(colour=(0.17, 0.37, 0.55), text=i, on_release=self.display_node, t_size=2))

    def display_node(self, n):
        node = self.app.handler.get_node(n.text[9:17])
        popup = NodePopup()
        popup.ids.port.text = str(node.port)
        popup.ids.version.text = node.version
        popup.ids.services.text = str(node.services)
        popup.ids.last_send.text = time.ctime(node.last_send/1e9)
        popup.ids.last_recv.text = time.ctime(node.last_recv/1e9)
        popup.ids.n_blockheight.text = str(node.blockheight)
        popup.heading = n.text
        popup.open()

    def method(self):
        self.app.manager.current = 'dash'


class WalletOverview(Screen): # Screen that displays information about the user's wallet
    def __init__(self, n):
        super(WalletOverview, self).__init__()
        self.app = App.get_running_app()
        self.name = n

    def method(self):
        self.app.manager.current = 'dash'

    def on_enter(self, *args):
        self.update_info()

    def create_poll(self):
        self.app.manager.current = 'create_poll'

    def update_info(self):
        self.ids.polls_grid.clear_widgets()
        self.ids.pending_grid.clear_widgets()
        for title in self.app.wallet.polls:
            self.ids.polls_grid.add_widget(
                RoundedButton(colour=(0.17, 0.37, 0.55), text=title, on_release=self.poll, t_size=2))
        for i in range(1, int(self.app.my_pending_votes)+1):
            self.ids.pending_grid.add_widget(
                RoundedButton(colour=(0.17, 0.37, 0.55), text=str(i), on_release=self.pending, t_size=2))

    def poll(self, p):
        self.app.manager.get_screen('poll').title = p.text
        self.app.manager.current = 'poll'

    def pending(self, p):
        sv = self.app.manager.get_screen('sv')
        p = self.app.wallet.pending_tokens[int(p.text) - 1]['value']
        sv.question = p['question']
        sv.options = p['options']
        sv.tk = Token.from_dictionary(p)
        self.app.manager.current = 'sv'

    def create_tx(self):
        self.app.manager.get_screen('tx').from_addr = self.app.address
        self.app.manager.get_screen('tx').to_addr = ''
        self.app.manager.get_screen('tx').poll = False
        self.manager.current = 'tx'


class CreatePoll(Screen):  # Screen that allows user to create poll.
    def __init__(self, n):
        super(CreatePoll, self).__init__()
        self.app = App.get_running_app()
        self.name = n

    def method(self):
        self.app.manager.current = 'wallet'

    def submit(self, title, question, options):
        try:
            n = int(options)
            if n > 10:
                self.open_popup('Maximum number of options is 10')
                return
            elif n <= 0:
                self.open_popup('Number of options must be positive')
                return
        except ValueError:
            self.open_popup('Invalid Number of Options')
            return
        if n == 0:
            self.open_popup('Cannot have 0 options')
        if len(title) > 16:
            self.open_popup('Title length has to be less than 16 characters')
            return
        elif len(title) <= 0:
            self.open_popup('Please Enter Title')
            return
        if len(question) <= 0:
            self.open_popup('Please Enter Question')
            return

        if self.app.wallet.valid_title(title):
            self.manager.get_screen('options').title = title
            self.manager.get_screen('options').number = n
            self.manager.get_screen('options').question = question
            self.app.manager.current = 'options'
            self.clear_inputs()
        else:
            self.open_popup('Title already used')

    @staticmethod
    def open_popup(msg):
        popup = ErrorPopup(heading='Error')
        popup.ids.msg.text = msg
        popup.open()

    def clear_inputs(self):  # Clears the inputs for when the screen is revisited
        self.ids.title.text = ''
        self.ids.question.text = ''
        self.ids.options.text = ''


class AddOptions(Screen): # This screen is part of the instantiation of the poll.
    title = StringProperty()
    number = 0
    question = ''

    def __init__(self, n):
        super(AddOptions, self).__init__()
        self.app = App.get_running_app()
        self.name = n

    def method(self):
        self.app.manager.current = 'wallet'

    def on_enter(self, *args):
        self.clear_inputs()
        for i in range(1, self.number+1):
            option = Option()
            option.label = 'Option ' + str(i) + ':'
            option.index = str(i)
            self.ids.options_grid.add_widget(option)

    def create_poll(self):
        o = []
        for option in self.ids.options_grid.children:
            text = option.ids.input.text
            if text != '':
                o.append([option.index, option.ids.input.text])
            else:
                popup = ErrorPopup(heading='Error')
                popup.ids.msg.text = 'Please Enter Poll Options'
                popup.open()
                return

        o.sort(key=lambda x: x[0])  # Sorts the options.

        self.app.wallet.create_poll(self.title, self.question, o)
        self.app.number_of_polls = str(len(self.app.wallet.polls))
        self.app.manager.current = 'wallet'
        self.clear_inputs()

    def clear_inputs(self):
        self.ids.options_grid.clear_widgets()


class Poll(Screen):  # Screen that displays overview of a poll
    title = StringProperty()
    question = StringProperty()
    funds = StringProperty()
    serialized = StringProperty()
    submitted = StringProperty()

    def __init__(self, n):
        super(Poll, self).__init__()
        self.app = App.get_running_app()
        self.name = n
        self.poll_address = ''
        self.o = None

    def on_enter(self, *args):
        self.get_info()

    def on_leave(self, *args):
        self.clear_info()

    def method(self):
        self.app.manager.current = 'wallet'

    def get_funds(self):
        self.app.manager.get_screen('tx').from_addr = self.app.address
        self.app.manager.get_screen('tx').to_addr = self.poll_address
        self.app.manager.get_screen('tx').poll = True
        self.manager.current = 'tx'

    def sell_funds(self):
        self.app.manager.get_screen('tx').from_addr = self.poll_address
        self.app.manager.get_screen('tx').to_addr = self.app.address
        self.app.manager.get_screen('tx').poll = True
        self.manager.current = 'tx'

    def serialize_token(self):
        sc = self.app.manager.get_screen('cv')
        sc.question = self.question
        sc.poll_addr = self.poll_address
        sc.options = self.o
        self.app.manager.current = 'cv'

    def get_info(self):
        self.question, self.poll_address, self.o = self.app.wallet.get_poll_info(self.title)
        self.funds = str(self.app.handler.blockchain.get_actual_number_of_tokens(0, self.poll_address))
        self.submitted = str(self.app.handler.blockchain.get_actual_number_of_tokens(2, self.poll_address))
        results = self.app.handler.blockchain.get_results(self.poll_address)
        self.serialized = self.app.handler.blockchain.get_serialized_votes(self.poll_address)
        new_list = [[i,0] for i in self.o]
        for r in results:
            new_list[r][1] += 1

        for item in new_list:
            self.ids.polls_grid.add_widget(DynamicLabel(text=str(item[0]) + ':'))
            self.ids.polls_grid.add_widget(DynamicLabel(text=str(item[1])))

    def clear_info(self):
        self.ids.polls_grid.clear_widgets()


class CreateTransaction(Screen): # Screen that allows the user to create a poll
    from_addr = StringProperty()
    to_addr = StringProperty()
    poll = BooleanProperty()  # States whether the user can edit the to address

    def __init__(self, n):
        super(CreateTransaction, self).__init__()
        self.app = App.get_running_app()
        self.name = n
        self.tx = None

    def on_leave(self, *args):
        self.clear_inputs()
        self.poll = False
        self.tx = None

    def method(self):
        self.app.manager.current = 'wallet'

    def clear_inputs(self):
        self.from_addr = ''
        self.to_addr = ''
        self.ids.amount.text = ''

    def sign_tx(self, fr, to, amount):
        try:
            n = int(amount)
        except ValueError as e:
            self.open_popup('Invalid Number of Tokens')
            return

        if n <= 0:
            self.open_popup('Must send a Positive number of tokens')
            return

        if self.poll == False and len(to) != 66:
            self.open_popup('Invalid Send To Address')
            return

        self.tx = Transaction(0, n, fr, to, self.app.handler.blockchain)
        self.tx.get_inputs()
        self.app.wallet.sign_transaction(self.tx)
        p = TransactionPopup(auto_dismiss=True)
        p.heading = self.tx.txid
        p.ids.from_addr.text = self.tx.from_address
        for item in self.tx.to_address:
            p.ids.to_addr.text += item + '\n'
        p.ids.type.text = str(self.tx.type)
        p.ids.timestamp.text = time.ctime(self.tx.timestamp/1e9)
        for i in self.tx.inputs:
            p.ids.inputs.text += (str(i) + '\n')
        for o in self.tx.outputs:
            p.ids.outputs.text += (str(o) + '\n')
        p.method = self.confirm_tx
        p.txt = 'CONFIRM'
        p.open()

    def confirm_tx(self):
        p = ErrorPopup()
        p.heading = 'TRANSACTION'
        if self.app.handler.blockchain.add_transaction(self.tx):
            p.ids.msg.text = 'Transaction Successfully Added To Memory Pool\n   -Wallet Funds may not update until ' \
                             'the transaction is mined '
        else:
            p.ids.msg.text = "Transaction Not Valid"
        self.tx = None
        p.open()
        self.app.update_blockchain()
        self.app.manager.current = 'wallet'

    @staticmethod
    def open_popup(msg):
        popup = ErrorPopup(heading='Error')
        popup.ids.msg.text = msg
        popup.open()


class CreateVote(Screen):  # Screen that serializes a token.
    poll_addr = StringProperty()
    question = StringProperty()

    def __init__(self, n):
        super(CreateVote, self).__init__()
        self.app = App.get_running_app()
        self.name = n
        self.tx = None
        self.tk = None
        self.options = None

    def method(self):
        self.app.manager.current = 'wallet'

    def clear_inputs(self):
        self.ids.to_addr.text = ''
        self.poll_addr = ''
        self.tx = None
        self.tk = None
        self.options = None

    def on_leave(self, *args):
        self.clear_inputs()

    def sign_tx(self, fr, to):
        if len(to) != 66:
            popup = ErrorPopup(heading='Error')
            popup.ids.msg.text = 'Invalid Send To Address'
            popup.open()
        self.tk = Token(self.poll_addr, to, self.question, self.options)
        self.tx = Transaction(1, self.tk.get_dictionary_form(), fr, to, self.app.handler.blockchain)
        self.tx.get_inputs()
        self.app.wallet.sign_transaction(self.tx)
        p = TransactionPopup(auto_dismiss=True)
        p.heading = self.tx.txid
        p.ids.from_addr.text = self.tx.from_address
        for item in self.tx.to_address:
            p.ids.to_addr.text += item + '\n'
        p.ids.type.text = str(self.tx.type)
        p.ids.timestamp.text = time.ctime(self.tx.timestamp/1e9)
        for i in self.tx.inputs:
            p.ids.inputs.text += (str(i) + '\n')
        for o in self.tx.outputs:
            p.ids.outputs.text += (str(o) + '\n')
        p.method = self.confirm_tx
        p.txt = 'CONFIRM'
        p.open()

    def confirm_tx(self):
        p = ErrorPopup()
        p.heading = 'TRANSACTION'
        if self.app.handler.blockchain.add_transaction(self.tx):
            p.ids.msg.text = 'Transaction Successfully Added To Memory Pool\n   -Wallet Funds may not update until ' \
                             'the transaction is mined '
        else:
            p.ids.msg.text = "Transaction Not Valid"
        self.tx = None
        p.open()
        self.app.update_blockchain()
        self.app.manager.current = 'wallet'


class SubmitVote(Screen):  # Screen that allows user to submit a vote
    question = StringProperty('')

    def __init__(self, n):
        super(SubmitVote, self).__init__()
        self.app = App.get_running_app()
        self.name = n
        self.options = []
        self.choice = None
        self.tk = None
        self.tx = None

    def on_enter(self, *args):
        self.display_options()

    def on_leave(self, *args):
        self.clear_choices()
        self.tk = None

    def method(self):
        self.clear_choices()
        self.app.manager.current = 'wallet'

    def display_options(self):
        self.clear_choices()
        for i in self.options:
            btn = RoundedButton(colour=(0.17, 0.37, 0.55), text=i, on_release=self.update_choice, t_size=3)
            self.ids.options_grid.add_widget(btn)

    def update_choice(self, b):
        print(b.text)
        self.choice = self.options.index(b.text)
        for i in self.ids.options_grid.children:
            i.colour = (0.17, 0.37, 0.55)

        b.colour = (0.1, 0.6, 0.1)

    def submit(self):

        if self.choice is None:
            p = ErrorPopup()
            p.ids.msg.text = 'Please Submit a Choice'
            p.open()
            return

        self.tk.ans = self.choice
        self.app.wallet.sign_token(self.tk)
        self.tx = Transaction(2, self.tk.get_dictionary_form(), self.app.address, self.tk.poll_address, self.app.handler.blockchain)
        self.tx.get_inputs()
        self.app.wallet.sign_transaction(self.tx)
        p = TransactionPopup(auto_dismiss=True)
        p.heading = self.tx.txid
        p.ids.from_addr.text = self.tx.from_address
        for item in self.tx.to_address:
            p.ids.to_addr.text += item + '\n'
        p.ids.type.text = str(self.tx.type)
        p.ids.timestamp.text = time.ctime(self.tx.timestamp/1e9)
        for i in self.tx.inputs:
            p.ids.inputs.text += (str(i) + '\n')
        for o in self.tx.outputs:
            p.ids.outputs.text += (str(o) + '\n')
        p.method = self.confirm_tx
        p.txt = 'CONFIRM'
        p.open()

    def confirm_tx(self):
        p = ErrorPopup()
        p.heading = 'TRANSACTION'
        if self.app.handler.blockchain.add_transaction(self.tx):
            p.ids.msg.text = 'Transaction Successfully Added To Memory Pool\n   -Wallet Funds may not update until ' \
                             'the transaction is mined '
        else:
            p.ids.msg.text = "Transaction Not Valid"
        self.tx = None
        p.open()
        self.app.update_blockchain()
        self.app.manager.current = 'wallet'

    def clear_choices(self):
        self.ids.options_grid.clear_widgets()
        self.choice = None
        self.tx = None


class Explorer(Screen): # Screen that allows user to navigate through the blockchain
    def __init__(self, n):
        super(Explorer, self).__init__()
        self.app = App.get_running_app()
        self.name = n

    def method(self):
        self.app.manager.current = 'dash'

    def on_enter(self, *args):
        for i in range(int(self.app.blockheight)+1):
            self.ids.block_grid.add_widget(RoundedButton(colour=(0.17, 0.37, 0.55), text=str(i), on_release=self.display_block, t_size=3 ))

    def on_leave(self, *args):
        self.ids.block_grid.clear_widgets()

    def display_block(self, b):
        self.app.manager.get_screen('block').number = b.text
        self.app.manager.current = 'block'
        pass


class Block(Screen):  #Screen that provides an overview of the block.
    number = StringProperty()

    def __init__(self, n):
        super(Block, self).__init__()
        self.app = App.get_running_app()
        self.name = n
        self.block = None

    def on_enter(self, *args):
        self.block = self.app.handler.blockchain.database.block_from_height(int(self.number))
        for tx in self.block.transactions:
            self.ids.transactions_grid.add_widget(RoundedButton(colour=(0.17, 0.37, 0.55), text=tx.txid, on_release=self.display_tx, t_size=0 ))
        self.ids.hash.text = self.block.hash[0:32] + '\n' + self.block.hash[32:]
        self.ids.p_hash.text = self.block.previous_hash[0:32] + '\n' + self.block.previous_hash[32:]
        self.ids.difficulty.text = str(self.block.difficulty)
        self.ids.nonce.text = str(self.block.nonce)
        self.ids.timestamp.text = time.ctime(self.block.timestamp/1e9)
        self.ids.txs.text = str(len(self.block.transactions))

    def on_leave(self, *args):
        self.ids.transactions_grid.clear_widgets()

    def method(self):
        self.app.manager.current = 'explorer'

    def display_tx(self, b):
        popup = TransactionPopup()
        popup.heading = b.text
        i = 0
        while self.block.transactions[i].txid != b.text:
            i += 1

        tx = self.block.transactions[i]
        popup.ids.from_addr.text = tx.from_address
        for item in tx.to_address:
            popup.ids.to_addr.text += item
        popup.ids.type.text = str(tx.type)
        popup.ids.timestamp.text = time.ctime(tx.timestamp/1e9)
        for i in tx.inputs:
            popup.ids.inputs.text += (str(i) + '\n')
        for o in tx.outputs:
            popup.ids.outputs.text += (str(o) + '\n')
        popup.open()


class Console(Screen):  # Screen that logs all debug messages from the project.
    def __init__(self, n):
        super(Console, self).__init__()
        self.app = App.get_running_app()
        self.name = n

    def method(self):
        self.app.manager.current = 'dash'

    def clear(self):
        self.app.console = ''


class Settings(Screen): # Screen taht allows the user to change settings
    mining = StringProperty()
    root_node = StringProperty

    def __init__(self, n):
        super(Settings, self).__init__()
        self.app = App.get_running_app()
        self.name = n
        self.initial_node = ''

    def method(self):
        if self.ids.node.text != self.initial_node:  # This checks to see if the root node has changed
            flag = True # Identifies whether the new IP address is of a valid format
            popup = ErrorPopup()
            popup.title = 'Error'
            txt = self.ids.node.text
            parts = txt.split('.')
            if len(parts) != 4:
                flag = False

            for p in parts:
                try:
                    i = int(p)
                    if i > 255 or i < 0:
                        flag = False
                except:
                    flag = False

            if not flag:
                popup.ids.msg.text = 'Problem with new IP Address'
                popup.open()
                self.app.manager.current = 'dash'
                return

            if len(self.app.handler.peers) > 0 or self.app.handler.connecting_thread is not None:
                popup.ids.msg.text = 'Cannot change root node whilst connected to the network'
                popup.open()
                self.app.manager.current = 'dash'
                return

            self.app.handler.default_peer = self.ids.node.text
            self.app.handler.known_peers = [self.ids.node.text]
            self.app.handler.establish_connection_with_network()
            self.app.status = 'Connecting'

        self.app.manager.current = 'dash'

    def on_enter(self, *args):
        self.initial_node = self.app.handler.default_peer
        self.ids.node.text = self.initial_node
        self.mining = str(self.app.mining)

    def change_mining(self):
        if self.mining == 'False' and self.app.status == 'Connected':
            self.app.mining = True
            self.app.mining_txt = 'True'
            self.app.handler.blockchain.mine_block()
            self.mining = 'True'
        elif self.mining == 'False':
            p = ErrorPopup()
            p.ids.msg.text = 'Cannot commence mining as you are not connected to the network'
            p.open()
        else:
            self.app.mining = False
            self.app.handler.blockchain.stop_mining()
            self.mining = 'False'
            self.app.mining_txt = 'False'


class VoterApp(App):  # Class that represents the overall application
    # Footer attributes
    device_id = StringProperty()
    status = StringProperty('Connecting')
    connections = StringProperty('0')
    blockheight = StringProperty('10')
    mining_txt = StringProperty()

    # Network attributes
    ip = StringProperty()
    default_node = StringProperty()
    max_peers = StringProperty()
    sent = StringProperty()
    received = StringProperty()
    last_node = StringProperty()

    # Dashboard attributes
    address = StringProperty()
    empty_tokens = StringProperty()
    number_of_polls = StringProperty('0')
    my_pending_votes = StringProperty()
    blocks_mined = StringProperty()
    last_block = StringProperty()

    # Extra wallet attributes
    spendable_tokens = StringProperty()
    submitted_votes = StringProperty()
    confirmed_votes = StringProperty()

    console = StringProperty()

    def __init__(self, path):
        super(VoterApp, self).__init__()
        self.path = path
        self.manager = ScreenManager()
        self.wallet = Wallet(path)
        self.handler = NodeHandler(path, self)

        self.inbound = []
        self.outbound = []

        self.blockheight = str(self.handler.blockchain.block_height)
        self.handler.blockchain.mining = False
        self.mining = False
        self.mining_txt = 'False'
        self.received = time.ctime(self.handler.node.last_recv/1e9)[11:-4]
        self.sent = time.ctime(self.handler.node.last_send/1e9)[11:-4]

    def build(self):  # Instantiates all of the screens
        self.manager.transition = NoTransition()
        self.manager.add_widget(LoginScreen('login'))
        self.manager.add_widget(CreateUser('create'))
        self.manager.add_widget(Dashboard('dash'))
        self.manager.add_widget(Network('network'))
        self.manager.add_widget(WalletOverview('wallet'))
        self.manager.add_widget(CreatePoll('create_poll'))
        self.manager.add_widget(AddOptions('options'))
        self.manager.add_widget(Poll('poll'))
        self.manager.add_widget(CreateTransaction('tx'))
        self.manager.add_widget(CreateVote('cv'))
        self.manager.add_widget(SubmitVote('sv'))
        self.manager.add_widget(Explorer('explorer'))
        self.manager.add_widget(Block('block'))
        self.manager.add_widget(Console('console'))
        self.manager.add_widget(Settings('settings'))

        return self.manager

    def on_start(self):
        self.handler.start_node()

    def on_stop(self):
        self.mining = False
        self.mining_txt = 'False'
        if self.handler.blockchain.mining:  # Stops the device from mining
            self.handler.blockchain.stop_mining()
        if self.handler is not None:
            self.handler.stop_node()  # Closes all sockets

    def print(self, line):  # Where all debug print messages are sent.
        self.console += line + '\n'
        print(line)

    def logon(self):
        self.handler.blockchain.wallet = self.wallet

        self.address = self.wallet.address
        self.blocks_mined = str(self.handler.blocks_mined)
        self.last_block = str(self.handler.blockchain.get_last_block().hash)
        self.handler.blockchain.update_wallet()
        self.update_wallet()

    def update_network(self):
        self.received = time.ctime(self.handler.node.last_recv/1e9)
        self.sent = time.ctime(self.handler.node.last_send/1e9)
        self.last_node = self.handler.last_connection
        self.manager.get_screen('network').update_nodes()

    def update_blockchain(self):
        self.blockheight = str(self.handler.blockchain.block_height)
        self.blocks_mined = str(self.handler.blocks_mined)
        self.last_block = str(self.handler.blockchain.get_last_block().hash)
        self.update_wallet()

    def update_wallet(self):
        if self.handler.blockchain.wallet is not None:
            self.empty_tokens = str(self.wallet.empty_tks)
            self.spendable_tokens = str(self.handler.blockchain.get_actual_number_of_tokens(0))
            self.number_of_polls = str(len(self.wallet.polls))
            self.wallet.pending_tokens = self.handler.blockchain.get_pending_votes(self.address)
            self.my_pending_votes = str(len(self.wallet.pending_tokens))
            self.submitted_votes = str(self.handler.blockchain.get_submitted_votes())
            self.confirmed_votes = str(self.handler.blockchain.get_confirmed_votes())
            self.manager.get_screen('wallet').update_info()

    def logoff(self):
        self.handler.blockchain.wallet = None