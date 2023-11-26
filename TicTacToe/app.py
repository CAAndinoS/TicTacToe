import asyncio
import websockets
import xml.etree.ElementTree as ET

# Store the connected players
players = []

# Game board (initialize as an empty 3x3 grid)
board = [[' ' for _ in range(3)] for _ in range(3)]

# Function to handle each player's connection
async def handle_client(websocket, path):
    player_number = len(players) + 1
    print(f"Player {player_number} connected.")

    # Add the player to the list
    players.append(websocket)

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
            else:
                row, col = map(int, data.split(','))
                if board[row][col] == ' ':
                    board[row][col] = 'X' if player_number == 1 else 'O'
                    await send_board_to_players()
                    winner = check_winner()
                    if winner:
                        await send_message_to_players(f"<Chat> Player {winner} wins!")
                        break
                    if is_board_full():
                        await send_message_to_players("<Chat> It's a draw!")
                        break
    except websockets.exceptions.ConnectionClosedError:
        # Handle player disconnection
        print(f"Player {player_number} disconnected.")
        players.remove(websocket)

# Function to send the current game board to both players
async def send_board_to_players():
    board_elem = ET.Element('Board')

    for row in board:
        row_elem = ET.SubElement(board_elem, 'Row')
        for cell in row:
            cell_elem = ET.SubElement(row_elem, 'Cell')
            cell_elem.text = cell

    board_xml = "<Board>" + ET.tostring(board_elem, encoding='unicode') + "</Board>"
    for player in players:
        await player.send(board_xml)

# Function to send chat messages to both players
async def send_chat_message_to_players(player_number, message):
    message = f"<Chat> Player {player_number}: {message}"
    await send_message_to_players(message)

# Function to send a message to both players
async def send_message_to_players(message):
    for player in players:
        await player.send(message)

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
start_server = websockets.serve(handle_client, "localhost", 12345)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
