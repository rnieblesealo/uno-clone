import sys
import socket
import random
import pickle
import threading


# -- connectivity --

PORT = 5050
SERVER = socket.gethostbyname(socket.gethostname())  # get ipv4 from hostname
ADDRESS = (SERVER, PORT)
HEADER = 64
FORMAT = 'utf-8'

DISCONNECT_MESSAGE = '!DISCONNECT'

server = None
conns = []
queue = []


def init():
    """
    Initialize host server
    """

    global server

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(ADDRESS)


def handle_client(conn, addr):
    """
    Listen for messages from a given connection
    """

    connected = True
    while connected:
        # discard null messages
        msg_len = conn.recv(HEADER).decode(FORMAT)
        if not msg_len:
            continue

        # receive message
        msg_len = int(msg_len)
        msg = conn.recv(msg_len).decode(FORMAT)

        # add received message to queue
        if msg not in queue:
            queue.append(msg)

    conn.close()


def get_connections():
    """
    Listen for connections and store their info in conns
    """

    if server is None:
        return

    server.listen()
    while True:
        # store conn in arr
        conn, addr = server.accept()

        # begin new thread for this conn
        thread = threading.Thread(
            target=handle_client, args=(conn, addr)
        )

        # put all info into one tuple
        conns.append((
            conn,
            addr,
            thread
        ))

        # print(f'Accepted connection @ {str(addr)}, have {len(conns)} connections')

        thread.start()


def send(i, msg):
    """
    Send message to specified client connection
    """

    msg = msg.encode(FORMAT)

    len_msg = str(len(msg)).encode(FORMAT)
    len_msg += b' ' * (HEADER - len(len_msg))

    conns[i][0].send(len_msg)
    conns[i][0].send(msg)


def send_obj(i, obj):
    """
    Send object to specific client connection
    """

    obj = pickle.dumps(obj)

    len_msg = str(sys.getsizeof(obj)).encode(FORMAT)
    len_msg += b' ' * (HEADER - len(len_msg))

    conns[i][0].send(len_msg)
    conns[i][0].send(obj)

# -- game --


PLAYERS = 4
START_CARDS = 7

VALUES = (
    '1',
    '2',
    '3',
    '4',
    '5',
    '6',
    '7',
    '8',
    '9',
    'draw',
    'reverse',
    'skip',
    'wild'
)

KINDS = (
    'red',
    'green',
    'blue',
    'yellow',
    'wild',
)

card_pool = None
card_stack = None
player_turn = 0
player_decks = []


def make_card(kind, value) -> tuple[str, str]:
    return (
        kind,
        value
    )


def make_pool() -> list:
    """
    Generate every possible card into a list, shuffle, and return it
    """

    pool = []

    for kind in KINDS:
        if kind == 'wild':
            # there's only 2 wildcards, compensate for this case
            pool.append(make_card(kind, 'draw'))
            pool.append(make_card(kind, 'wild'))
            pass
        else:
            for value in VALUES:
                pool.append(make_card(kind, value))

    random.shuffle(pool)

    return pool


def move_card(src, dest, index=-1):
    """
    Move a card from a source to a destination
    May specifiy index, otherwise topmost is used
    """

    taken = src.pop() if index == -1 else src.pop(index)
    dest.append(taken)


def draw_cards(dest, amt):
    """
    Moves @amt cards from the top of the pool to the dest
    """

    for i in range(amt):
        dest.append(card_pool.pop())


def start_game():
    """
    Initializes all game data
    """

    global card_pool
    global card_stack
    global player_decks

    card_pool = make_pool()

    print(len(conns))

    # add 1 to len of conns to count the host
    for i in range(len(conns)):
        player_decks.append([])
        draw_cards(player_decks[i], START_CARDS)

    card_stack = [card_pool.pop()]

    print('\nCard pool:\n')
    for card in card_pool:
        print(card)

    print('\nPlayer decks:')
    for i in range(len(player_decks)):
        print(f'\nPlayer {i}:\n')
        for card in player_decks[i]:
            print(card)

    print('\nStack:\n')
    for card in card_stack:
        print(card)

    print('\n---')


def update_game():
    while True:
        handle_queue()


def is_valid_play(card):
    """
    Evaluates the stack top card against selected card
    Return True if card can be placed after top following UNO rules

    """

    top_kind = card_stack[-1][0]
    top_value = card_stack[-1][1]

    card_kind = card[0]
    card_value = card[1]

    conditions = [
        card_kind == 'wild',        # wilds are free game
        top_kind == card_kind,      # kinds (colors) match
        top_value == card_value     # values match
    ]

    return True in conditions


def get_playable_cards(deck):
    """
    Check all cards in deck against is_valid_play, adding playable indices to a list
    """

    playables = []
    for i in range(len(deck)):
        if is_valid_play(deck[i]):
            playables.append(i)
    return playables


def has_playable_card(deck):
    """
    Checks if there is at least 1 playable card that can be played against top
    More memory-efficient that using len(get_playable_cards)
    """

    for i in range(len(deck)):
        if (is_valid_play(deck[i])):
            return i
    return None


def show_deck(n):
    print(f"\nPlayer {n}'s deck: ")
    for card in player_decks[n]:
        print(card)


def move_turn():
    """
    Move turn to next player, resetting if reached last one
    """

    global player_turn

    old_turn = player_turn

    player_turn = (player_turn + 1) if (player_turn +
                                        1) < len(player_decks) else 0

    print(f'Moved from turn {str(old_turn)} to {str(player_turn)}; there are {str(len(player_decks))} decks')

    # send turn info to other clients
    for i in range(len(player_decks)):
        if i == player_turn:
            send(i, 'turn')
        else:
            send(i, 'not_turn')


def handle_queue():
    global queue
    global stack

    if queue:
        event = queue.pop(0)  # remove from base of the queue!

        # print(f'Processing event {event}; remaining queue: {str(queue)}')

        match(event):
            case 'give_first_turn':
                # tell the current player that it's their turn if they're NOT the host
                send(player_turn, 'turn')
                pass
            case 'give_deck':
                # send player their deck
                send_obj(
                    player_turn,
                    player_decks[player_turn]
                )
                pass
            case 'give_plays':
                # send player a list of cards they can play too
                send_obj(
                    player_turn,
                    get_playable_cards(player_decks[player_turn])
                )
                pass
            case 'no_playables':
                # give player one card
                draw_cards(player_decks[player_turn], 1)

                # play the new card if it's playable
                if has_playable_card(player_decks[player_turn]):
                    move_card(player_decks[player_turn], card_stack)

                move_turn()
                pass
            case 'card_play':
                # await selection from queue, not ideal!
                while True:
                    if queue:
                        sel = queue.pop()
                        break

                # move played card to stack and move turns
                move_card(player_decks[player_turn], card_stack, int(sel))
                move_turn()
                pass
            case '_':
                pass
