import random
import urllib2
import cookielib
from decimal import Decimal

from socketio import SocketIO

BASE_DOMAIN = 'just-dice.com'
BASE_URL = 'https://%s' % BASE_DOMAIN

cj = cookielib.CookieJar()
def load_justdice():
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    opener.addheaders.append(('Origin', BASE_URL))

    opener.open(BASE_URL)
    req = opener.open('%s/socket.io/1' % BASE_URL)
    response = req.read()
    return response


class JustDiceSocket(object):
    def __init__(self, response, login):
        self.login = login
        self._setup_sock(response)

    def _setup_sock(self, response):
        self.csrf = None
        self.user_id = None
        self.logged_in = False
        self.waiting_bet_result = False
        self.last_bet = None
        self.house_edge = 1 # %

        origin = BASE_URL
        self.sock = SocketIO(BASE_DOMAIN, origin, response, secure=True)

        self.sock.on('init', self.on_init)
        self.sock.on('set_hash', self.on_set_hash)
        self.sock.on('reload', self.on_reload)
        self.sock.on('result', self.on_result)
        self.sock.on('login_error', self.on_login_error)


    def bet(self, win_chance, amount, roll_hi):
        if self.waiting_bet_result:
            raise Exception("Still waiting for last bet result")
        which = 'hi' if roll_hi else 'lo'
        self.sock.emit('bet', self.csrf, {'chance': '%s' % str(win_chance),
            'bet': format(amount, '.8f'), 'which': '%s' % which})
        self.waiting_bet_result = True

    def randomize(self, user_seed=None):
        # user_seed must be a string.
        self.sock.emit('random', self.csrf)
        if user_seed is None:
            user_seed = str(random.randint(0, int('9' * 24)))
        self.sock.emit('seed', self.csrf, user_seed, True)

    def on_result(self, result):
        if result['uid'] == self.user_id:
            self.last_bet = {
                    'win': result['win'],
                    'roll_high': result['high'],
                    'lucky_number': Decimal(result['lucky']) / 10000}
            self.waiting_bet_result = False

    def on_reload(self):
        self.sock.emit('disconnect')
        response = load_justdice()
        self._setup_sock(response)

    def on_set_hash(self, new_cookie_hash):
        for cookie in cj:
            if cookie.name == 'hash':
                cookie.value = new_cookie_hash
                break

    def on_init(self, data):
        self.csrf = data[u'csrf']
        self.user_id = data[u'uid']
        self.house_edge = data[u'edge']

        if data['username'] is None and self.login:
            self.sock.emit('login', self.csrf,
                    self.login['user'], self.login['pwd'], '')
        else:
            self.logged_in = True

    def on_login_error(self, msg):
        msg = msg.lower()
        if msg.startswith('incorrect') or msg.endswith('no such user'):
            self.logged_in = None
            raise Exception("Invalid credentials")
