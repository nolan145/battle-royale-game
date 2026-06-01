from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import math
import json
from datetime import datetime
from enum import Enum

app = Flask(__name__)
app.config['SECRET_KEY'] = 'battle-royale-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Constants
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
PLAYER_SIZE = 15
PLAYER_SPEED = 4
MAX_HEALTH = 100
HEALTH_REGEN_RATE = 0.3
RESPAWN_TIME = 30
GAME_TICK_RATE = 60

class WeaponType(Enum):
    ASSAULT_RIFLE = 1
    PISTOL = 2
    KNIFE = 3

class GameState:
    def __init__(self):
        self.players = {}
        self.next_player_id = 0
        self.game_map = self._generate_city()
        self.tick = 0
    
    def _generate_city(self):
        buildings = []
        building_size = 80
        spacing = 20
        
        for row in range(3):
            for col in range(4):
                x = 100 + col * (building_size + spacing)
                y = 100 + row * (building_size + spacing)
                
                if x + building_size < SCREEN_WIDTH and y + building_size < SCREEN_HEIGHT:
                    buildings.append({
                        'x': x,
                        'y': y,
                        'width': building_size,
                        'height': building_size
                    })
        
        return buildings
    
    def add_player(self, sid):
        player_id = self.next_player_id
        self.next_player_id += 1
        
        # Random spawn position
        valid = False
        while not valid:
            x = random.uniform(PLAYER_SIZE + 50, SCREEN_WIDTH - PLAYER_SIZE - 50)
            y = random.uniform(PLAYER_SIZE + 50, SCREEN_HEIGHT - PLAYER_SIZE - 50)
            
            valid = True
            for building in self.game_map:
                if (x - PLAYER_SIZE < building['x'] + building['width'] and
                    x + PLAYER_SIZE > building['x'] and
                    y - PLAYER_SIZE < building['y'] + building['height'] and
                    y + PLAYER_SIZE > building['y']):
                    valid = False
                    break
        
        self.players[sid] = {
            'id': player_id,
            'x': x,
            'y': y,
            'vx': 0,
            'vy': 0,
            'health': MAX_HEALTH,
            'is_alive': True,
            'respawn_timer': 0,
            'current_weapon': 0,
            'weapons': [
                {'type': 'assault_rifle', 'ammo': 34, 'max_ammo': 34, 'reload_time': 1.5, 'is_reloading': False, 'reload_timer': 0},
                {'type': 'pistol', 'ammo': 6, 'max_ammo': 6, 'reload_time': 1.0, 'is_reloading': False, 'reload_timer': 0},
                {'type': 'knife', 'ammo': float('inf'), 'max_ammo': float('inf'), 'reload_time': 0, 'is_reloading': False, 'reload_timer': 0}
            ],
            'last_direction': [1, 0]
        }
    
    def remove_player(self, sid):
        if sid in self.players:
            del self.players[sid]
    
    def update_player_movement(self, sid, keys):
        if sid not in self.players:
            return
        
        player = self.players[sid]
        player['vx'] = 0
        player['vy'] = 0
        
        if keys.get('z'):
            player['vy'] = -PLAYER_SPEED
        if keys.get('s'):
            player['vy'] = PLAYER_SPEED
        if keys.get('q'):
            player['vx'] = -PLAYER_SPEED
        if keys.get('d'):
            player['vx'] = PLAYER_SPEED
        
        if player['vx'] != 0 or player['vy'] != 0:
            player['last_direction'] = [player['vx'], player['vy']]
    
    def update(self, dt):
        for sid, player in list(self.players.items()):
            if not player['is_alive']:
                player['respawn_timer'] -= dt
                if player['respawn_timer'] <= 0:
                    self.respawn_player(sid)
                continue
            
            # Health regen
            if player['health'] < MAX_HEALTH:
                player['health'] += HEALTH_REGEN_RATE * dt
                player['health'] = min(player['health'], MAX_HEALTH)
            
            # Movement
            player['x'] += player['vx']
            player['y'] += player['vy']
            
            # Boundary check
            player['x'] = max(PLAYER_SIZE, min(SCREEN_WIDTH - PLAYER_SIZE, player['x']))
            player['y'] = max(PLAYER_SIZE, min(SCREEN_HEIGHT - PLAYER_SIZE, player['y']))
            
            # Building collision
            for building in self.game_map:
                if (player['x'] - PLAYER_SIZE < building['x'] + building['width'] and
                    player['x'] + PLAYER_SIZE > building['x'] and
                    player['y'] - PLAYER_SIZE < building['y'] + building['height'] and
                    player['y'] + PLAYER_SIZE > building['y']):
                    player['x'] -= player['vx']
                    player['y'] -= player['vy']
            
            # Update weapons
            weapon = player['weapons'][player['current_weapon']]
            if weapon['is_reloading']:
                weapon['reload_timer'] -= dt
                if weapon['reload_timer'] <= 0:
                    weapon['is_reloading'] = False
                    weapon['ammo'] = weapon['max_ammo']
    
    def respawn_player(self, sid):
        if sid not in self.players:
            return
        
        player = self.players[sid]
        player['health'] = MAX_HEALTH
        player['is_alive'] = True
        
        valid = False
        while not valid:
            player['x'] = random.uniform(PLAYER_SIZE + 50, SCREEN_WIDTH - PLAYER_SIZE - 50)
            player['y'] = random.uniform(PLAYER_SIZE + 50, SCREEN_HEIGHT - PLAYER_SIZE - 50)
            
            valid = True
            for building in self.game_map:
                if (player['x'] - PLAYER_SIZE < building['x'] + building['width'] and
                    player['x'] + PLAYER_SIZE > building['x'] and
                    player['y'] - PLAYER_SIZE < building['y'] + building['height'] and
                    player['y'] + PLAYER_SIZE > building['y']):
                    valid = False
                    break
        
        player['vx'] = 0
        player['vy'] = 0
        for weapon in player['weapons']:
            weapon['ammo'] = weapon['max_ammo']
            weapon['is_reloading'] = False
    
    def get_state(self):
        return {
            'players': self.players,
            'map': self.game_map,
            'width': SCREEN_WIDTH,
            'height': SCREEN_HEIGHT
        }

game_state = GameState()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    game_state.add_player(request.sid)
    emit('player_id', {'id': game_state.players[request.sid]['id']})
    socketio.emit('game_state', game_state.get_state())

@socketio.on('disconnect')
def handle_disconnect():
    game_state.remove_player(request.sid)
    socketio.emit('game_state', game_state.get_state())

@socketio.on('movement')
def handle_movement(data):
    game_state.update_player_movement(request.sid, data)

@socketio.on('shoot')
def handle_shoot(data):
    if request.sid in game_state.players:
        player = game_state.players[request.sid]
        weapon = player['weapons'][player['current_weapon']]
        
        if weapon['ammo'] > 0 and not weapon['is_reloading']:
            weapon['ammo'] -= 1
            
            # Broadcast shot
            socketio.emit('shot', {
                'player_id': player['id'],
                'x': player['x'],
                'y': player['y'],
                'direction': player['last_direction']
            })

@socketio.on('switch_weapon')
def handle_switch_weapon(data):
    if request.sid in game_state.players:
        weapon_idx = data.get('weapon', 0)
        game_state.players[request.sid]['current_weapon'] = max(0, min(2, weapon_idx))

@socketio.on('reload')
def handle_reload(data):
    if request.sid in game_state.players:
        player = game_state.players[request.sid]
        weapon = player['weapons'][player['current_weapon']]
        if weapon['ammo'] < weapon['max_ammo'] and not weapon['is_reloading']:
            weapon['is_reloading'] = True
            weapon['reload_timer'] = weapon['reload_time']

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
