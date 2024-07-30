import asyncio
import websockets
import json
import random
import time
import curses
import colorama
from colorama import Fore, Style
from hashlib import sha256

colorama.init()

uri = 'wss://tongame-service-roy7ocqnoq-ew.a.run.app/socket.io/?EIO=4&transport=websocket'
log_lines = {}

def get_random_color():
    colors = [
        Fore.RED,
        Fore.GREEN,
        Fore.YELLOW,
        Fore.BLUE,
        Fore.MAGENTA,
        Fore.CYAN
    ]
    return random.choice(colors)

def log_message(account_number, message):
    durability_color = get_random_color()
    gold_color = get_random_color()
    progress_color = get_random_color()
    rank_color = get_random_color()
    per_hour_color = get_random_color()
    dogs_color = get_random_color()
    reset_color = Style.RESET_ALL

    message = message.replace('Durability: ', f'{durability_color}Durability: {reset_color}')
    message = message.replace('Gold: ', f'{gold_color}Gold: {reset_color}')
    message = message.replace('Progress: ', f'{progress_color}Progress: {reset_color}')
    message = message.replace('Rank: ', f'{rank_color}Rank: {reset_color}')
    message = message.replace('Per Hour: ', f'{per_hour_color}Per Hour: {reset_color}')
    message = message.replace('Dogs: ', f'{dogs_color}Dogs: {reset_color}')

    log_lines[account_number] = message
    update_console()

def update_console():
    for account_number in log_lines:
        print(log_lines[account_number])

async def read_tokens():
    with open('tokens.txt', 'r') as file:
        tokens = file.read().strip().split('\n')
    return [token.strip() for token in tokens if token.strip()]

async def connect(access_token, account_number):
    event_type_number = 0
    total_coins_earned = 0
    current_round = 5
    game_started = False
    home_data_sent = False
    is_sending_message = False
    should_send_in_game_messages = True

    user_rank_data = {}

    async def send_home_data(ws):
        nonlocal event_type_number
        await ws.send(f'42{event_type_number}["homeData"]')
        event_type_number += 1

    async def start_game(ws):
        nonlocal event_type_number, game_started
        if not game_started:
            log_message(account_number, f'Account #{account_number} | Sending startGame message...')
            await ws.send(f'42{event_type_number}["startGame"]')
            event_type_number += 1
            game_started = True
        else:
            log_message(account_number, f'Account #{account_number} | Game already started, not sending startGame message.')

    async def send_in_game_message(ws, game_data):
        nonlocal is_sending_message, should_send_in_game_messages, event_type_number
        if is_sending_message or not should_send_in_game_messages:
            return

        is_sending_message = True
        timestamp = int(time.time() * 1000)
        message = f'42{event_type_number}["inGame",{{"round":{current_round},"time":{timestamp},"gameover":false}}]'
        await ws.send(message)
        event_type_number += 1

        if not game_data.get('gameover') and game_data.get('durability', 0) > 0:
            await asyncio.sleep(0.5)
            is_sending_message = False
            await send_in_game_message(ws, game_data)
        else:
            is_sending_message = False

    async def handle_message(ws, message):
        nonlocal home_data_sent, event_type_number, game_started, total_coins_earned, current_round

        if message.startswith('40'):
            if not home_data_sent:
                await send_home_data(ws)
                home_data_sent = True
        else:
            try:
                data = json.loads(message[message.find('['):])
                if isinstance(data, list) and data:
                    data = data[0]
                    if 'userRank' in data:
                        user_rank_data['rank'] = data['userRank']['role']
                        user_rank_data['profitPerHour'] = data['userRank']['profitPerHour']
                        user_rank_data['gold'] = data['gold']
                        user_rank_data['dogs'] = data['dogs']
                        log_message(account_number, f'Account #{account_number} | Rank: {user_rank_data["rank"]} | Per Hour: {user_rank_data["profitPerHour"]} | Gold: {user_rank_data["gold"] / 1000:.3f} | Dogs: {user_rank_data["dogs"]}')
                        if not game_started:
                            log_message(account_number, f'Account #{account_number} | Starting game...')
                            await start_game(ws)
                            game_started = True
                    if 'duration' in data:
                        log_message(account_number, f'Account #{account_number} | Durability: {data["durability"]} | Gold: {data["gold"]} | Rank: {user_rank_data["rank"]} | Per Hour: {user_rank_data["profitPerHour"]} | Dogs: {user_rank_data["dogs"]}')
                        if data['durability'] == 0 and data.get('gameover'):
                            log_message(account_number, f'Account #{account_number} | Game Selesai | Coin: {data["gold"]}')
                            total_coins_earned += data['gold']
                            current_round = 5
                            event_type_number = 0
                            game_started = False
                            await start_game(ws)
                        elif data['durability'] >= 0:
                            await send_in_game_message(ws, data)
            except json.JSONDecodeError as e:
                log_message(account_number, f'Account #{account_number} | Failed to parse JSON: {e}')

    async def run():
        reconnect_attempts = 0
        max_reconnect_attempts = 5
        ws = await websockets.connect(uri, extra_headers={
            'Authorization': f'Bearer {access_token}',
            'Origin': 'https://netcoin.layernet.ai',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; M2012K11AG Build/TKQ1.220829.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.6478.134 Mobile Safari/537.36',
            'Sec-WebSocket-Key': sha256(str(random.random()).encode()).hexdigest(),
            'Sec-WebSocket-Version': '13'
        })
        log_message(account_number, f'Account #{account_number} | WebSocket connection opened for token: {access_token}')

        try:
            async for message in ws:
                await handle_message(ws, message)
        except websockets.ConnectionClosed as e:
            log_message(account_number, f'Account #{account_number} | WebSocket connection closed: {e.code} - {e.reason}')
            if reconnect_attempts < max_reconnect_attempts:
                reconnect_attempts += 1
                await asyncio.sleep(5)
                await run()
            else:
                log_message(account_number, f'Account #{account_number} | Max reconnect attempts reached. Giving up.')

    await run()

async def main():
    tokens = await read_tokens()
    await asyncio.gather(*(connect(token, index + 1) for index, token in enumerate(tokens)))

if __name__ == '__main__':
    asyncio.run(main())
