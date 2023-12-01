import asyncio
import websockets
import xml.etree.ElementTree as ET

# Store the connected players
players = []
players_lock = asyncio.Lock()

# Game board (initialize as an empty 3x3 grid)
board = [[' ' for _ in range(3)] for _ in range(3)]

# Turn variables
global current_turn, player_turn, game_waiting, victories_player1, victories_player2, draws
player_turn = 0  # Variable to track the current player's turn
current_turn = 1  # Player 1 starts
game_waiting = True  # Flag to indicate whether the game is waiting for the second player

# Estadísticas
victories_player1 = 0
victories_player2 = 0
draws = 0

# Function to handle each player's connection
async def handle_client(websocket, path):
    global current_turn, player_turn, game_waiting, victories_player1, victories_player2, draws

    player_number = len(players) + 1
    print(f"Player {player_number} connected.")

    async with players_lock:
        players.append(websocket)

        # If the first player connects, set them as the starting player
        if len(players) == 1:
            current_turn = 1
            player_turn = 1
            await websocket.send("<Chat> Bienvenido, Jugador 1. Esperando a Jugador 2.")

        # If the second player connects, start the game
        elif len(players) == 2:
            if game_waiting:
                game_waiting = False
                message_to_send = "<Chat> Jugador 2 se ha unido.\n¡El juego puede comenzar!\nEs Turno del Jugador 1"
                for player in players:
                    await player.send(message_to_send)
            else:
                player_number = 1
                current_turn = 1
                player_turn = 1
                await websocket.send("<Chat> Jugador 1 se ha unido.\n¡El juego puede comenzar!\nEs Turno del Jugador 1")

    # Send the player's number (1 or 2)
    await websocket.send(str(player_number))


    try:
        while True:
            data = await websocket.recv()
            if not data:
                break

            if data.startswith("/chat "):
                chat_message = data[len("/chat "):]
                await send_chat_message_to_players(player_number, chat_message)
            elif data == "/disconnect":
                await handle_disconnect(websocket, player_number)
            else:
                # Check if it's the player's turn for a game move
                if game_waiting:
                    await websocket.send("<Chat> Esperando a Jugador 2 para unirse. Por favor, ten paciencia.")
                    continue

                if player_turn != player_number:
                    await websocket.send("<Chat> No es tu turno. Por favor, espera tu turno.")
                    continue

                row, col = map(int, data.split(','))
                if board[row][col] == ' ':
                    board[row][col] = 'X' if player_number == 1 else 'O'
                    await send_board_to_players()
                    winner = check_winner()
                    if winner:
                        if winner == "X":
                            victories_player1 += 1
                        elif winner == "O":
                            victories_player2 += 1
                        await send_message_to_players(f"<Chat> ¡Jugador {winner} gana!")
                        await reset_game()  # Llama a la función para reiniciar el juego
                    elif is_board_full():
                        draws += 1
                        await send_message_to_players("<Chat> ¡Es un empate!")
                        await reset_game()  # Llama a la función para reiniciar el juego
                    else:
                        # Switch to the other player's turn
                        player_turn = 3 - player_turn  # Cambiar al otro jugador (1 <-> 2)
                        await send_message_to_players(f"<Chat> Es el turno de Jugador {player_turn}.")
                else:
                    await websocket.send("<Chat> Movimiento inválido. Celda ya ocupada. Inténtalo de nuevo.")

    except websockets.exceptions.ConnectionClosedOK:
        print(f"Jugador {player_number} desconectado.")
        async with players_lock:
            players.remove(websocket)
    except websockets.exceptions.ConnectionClosedError:
        print(f"Jugador {player_number} desconectado inesperadamente.")
        async with players_lock:
            players.remove(websocket)
        await websocket.close()

async def handle_disconnect(websocket, player_number):
    global game_waiting, player_turn, victories_player1, victories_player2, draws
    async with players_lock:
        players.remove(websocket)

        if player_number == 1:
            victories_player1 = 0
            victories_player2 = 0
            draws = 0
            # Player 1 disconnected, reset the game and reassign Player 2 as Player 1
            message_to_send = "<Chat> Jugador 1 se ha desconectado. Esperando a un nuevo jugador."
            for player in players:
                await player.send(message_to_send)
            game_waiting = False
        elif player_number == 2:
            victories_player1 = 0
            victories_player2 = 0
            draws = 0
            # Player 2 disconnected, notify and wait for a new player
            game_waiting = True
            player_turn = 1
            message_to_send = "<Chat> Jugador 2 se ha desconectado. Esperando a un nuevo jugador."
            for player in players:
                await player.send(message_to_send)
    await reset_game()

async def reset_game():
    global board, current_turn, player_turn, game_waiting, victories_player1, victories_player2, draws
    board = [[' ' for _ in range(3)] for _ in range(3)]
    
    # Alternar el jugador que comienza después de cada reinicio
    player_turn = 3 - player_turn if player_turn in [1, 2] else 1
    
    current_turn = 1
    await send_message_to_players("<Chat> Juego reiniciado")
    await send_board_to_players()
    await send_message_to_players(f"<Chat> Es el turno de Jugador {player_turn}.")
    await send_statistics_to_players()
    await asyncio.sleep(2)

# Function to send the current game board to both players
async def send_board_to_players():
    board_elem = ET.Element('Board')

    for row in board:
        row_elem = ET.SubElement(board_elem, 'Row')
        for cell in row:
            cell_elem = ET.SubElement(row_elem, 'Cell')
            cell_elem.text = cell

    board_xml = "<Board>" + ET.tostring(board_elem, encoding='unicode') + "</Board>"
    async with players_lock:
        for player in players:
            await player.send(board_xml)

# Function to send chat messages to both players
async def send_chat_message_to_players(player_number, message):
    message = f"<Chat> Player {player_number}: {message}"
    await send_message_to_players(message)

# Function to send a message to both players
async def send_message_to_players(message):
    async with players_lock:
        for player in players:
            await player.send(message)

# Function to send statistics to both players
async def send_statistics_to_players():
    statistics_message = f"<Statistics> Jugador 1 ({victories_player1} victorias) | Jugador 2 ({victories_player2} victorias) | Empates ({draws})"
    await send_message_to_players(statistics_message)

# Function to check for a winner
def check_winner():
    for i in range(3):
        if board[i][0] == board[i][1] == board[i][2] and board[i][0] != ' ':
            return board[i][0]
        if board[0][i] == board[1][i] == board[2][i] and board[0][i] != ' ':
            return board[0][i]
    if board[0][0] == board[1][1] == board[2][2] and board[0][0] != ' ':
        return board[0][0]
    if board[0][2] == board[1][1] == board[2][0] and board[0][2] != ' ':
        return board[0][2]
    return None

# Function to check if the board is full (a draw)
def is_board_full():
    return all(all(cell != ' ' for cell in row) for row in board)

# Start the WebSocket server
start_server = websockets.serve(handle_client, "0.0.0.0", 12345)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
