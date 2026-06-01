import pygame
import random
import math
import time
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60
PLAYER_SIZE = 15
PLAYER_SPEED = 4
MAX_HEALTH = 100
HEALTH_REGEN_RATE = 0.3  # HP per second
RESPAWN_TIME = 30  # seconds

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 100, 255)
GRAY = (100, 100, 100)
YELLOW = (255, 255, 0)
LIGHT_GRAY = (200, 200, 200)
DARK_GREEN = (34, 139, 34)
BROWN = (139, 69, 19)

class WeaponType(Enum):
    ASSAULT_RIFLE = 1  # 34 bullets, 1.5s reload
    PISTOL = 2         # 6 bullets, 1s reload
    KNIFE = 3          # Melee

@dataclass
class Weapon:
    weapon_type: WeaponType
    ammo: int
    max_ammo: int
    reload_time: float
    is_reloading: bool = False
    reload_timer: float = 0.0
    
    def get_damage(self) -> int:
        if self.weapon_type == WeaponType.ASSAULT_RIFLE:
            return 15
        elif self.weapon_type == WeaponType.PISTOL:
            return 20
        elif self.weapon_type == WeaponType.KNIFE:
            return 25
        return 0
    
    def get_range(self) -> float:
        if self.weapon_type == WeaponType.ASSAULT_RIFLE:
            return 300
        elif self.weapon_type == WeaponType.PISTOL:
            return 200
        elif self.weapon_type == WeaponType.KNIFE:
            return 40
        return 0
    
    def shoot(self) -> bool:
        if self.ammo > 0 and not self.is_reloading:
            self.ammo -= 1
            return True
        elif self.ammo == 0 and not self.is_reloading:
            self.is_reloading = True
            self.reload_timer = self.reload_time
        return False
    
    def update(self, dt: float):
        if self.is_reloading:
            self.reload_timer -= dt
            if self.reload_timer <= 0:
                self.is_reloading = False
                self.ammo = self.max_ammo

class Player:
    def __init__(self, x: float, y: float, is_player: bool = False):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.health = MAX_HEALTH
        self.max_health = MAX_HEALTH
        self.is_player = is_player
        self.is_alive = True
        self.respawn_timer = 0.0
        self.last_shot_time = 0.0
        self.shot_cooldown = 0.1
        
        # Initialize with random weapon
        self.current_weapon_idx = 0
        self.weapons = [
            Weapon(WeaponType.ASSAULT_RIFLE, 34, 34, 1.5),
            Weapon(WeaponType.PISTOL, 6, 6, 1.0),
            Weapon(WeaponType.KNIFE, float('inf'), float('inf'), 0.0)
        ]
        
        self.target_player = None
        self.last_direction = (1, 0)  # For bot direction
        self.ai_action_timer = 0.0
    
    def get_current_weapon(self) -> Weapon:
        return self.weapons[self.current_weapon_idx]
    
    def update(self, dt: float, players: List['Player'], game_map: 'GameMap'):
        if not self.is_alive:
            self.respawn_timer -= dt
            if self.respawn_timer <= 0:
                self.respawn(game_map)
            return
        
        # Update weapon
        self.get_current_weapon().update(dt)
        
        # Health regeneration
        if self.health < self.max_health:
            self.health += HEALTH_REGEN_RATE * dt
            self.health = min(self.health, self.max_health)
        
        # Movement
        self.x += self.vx
        self.y += self.vy
        
        # Collision with map boundaries
        self.x = max(PLAYER_SIZE, min(SCREEN_WIDTH - PLAYER_SIZE, self.x))
        self.y = max(PLAYER_SIZE, min(SCREEN_HEIGHT - PLAYER_SIZE, self.y))
        
        # Check collisions with buildings
        for building in game_map.buildings:
            if self.collides_with_building(building):
                self.x -= self.vx
                self.y -= self.vy
        
        # AI behavior
        if not self.is_player:
            self.update_ai(dt, players, game_map)
    
    def collides_with_building(self, building) -> bool:
        return (self.x - PLAYER_SIZE < building['x'] + building['width'] and
                self.x + PLAYER_SIZE > building['x'] and
                self.y - PLAYER_SIZE < building['y'] + building['height'] and
                self.y + PLAYER_SIZE > building['y'])
    
    def update_ai(self, dt: float, players: List['Player'], game_map: 'GameMap'):
        self.ai_action_timer -= dt
        
        # Find nearest enemy
        nearest_enemy = None
        nearest_distance = float('inf')
        
        for player in players:
            if player != self and player.is_alive:
                dist = self.distance_to(player)
                if dist < nearest_distance:
                    nearest_distance = dist
                    nearest_enemy = player
        
        if nearest_enemy:
            # Move towards enemy
            dx = nearest_enemy.x - self.x
            dy = nearest_enemy.y - self.y
            dist = math.sqrt(dx*dx + dy*dy)
            
            if dist > 0:
                self.vx = (dx / dist) * PLAYER_SPEED
                self.vy = (dy / dist) * PLAYER_SPEED
                self.last_direction = (self.vx, self.vy)
            
            # Shoot at enemy
            if nearest_distance < self.get_current_weapon().get_range():
                self.shoot_at(nearest_enemy)
            
            # Switch weapons occasionally
            if self.ai_action_timer <= 0:
                if random.random() < 0.3:
                    self.current_weapon_idx = random.randint(0, 2)
                self.ai_action_timer = random.uniform(1, 3)
        else:
            # Random movement
            if self.ai_action_timer <= 0:
                self.vx = random.uniform(-PLAYER_SPEED, PLAYER_SPEED)
                self.vy = random.uniform(-PLAYER_SPEED, PLAYER_SPEED)
                self.ai_action_timer = random.uniform(1, 3)
    
    def distance_to(self, other: 'Player') -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx*dx + dy*dy)
    
    def shoot(self):
        weapon = self.get_current_weapon()
        current_time = time.time()
        
        if current_time - self.last_shot_time > self.shot_cooldown:
            if weapon.shoot():
                self.last_shot_time = current_time
    
    def shoot_at(self, target: 'Player'):
        self.shoot()
        weapon = self.get_current_weapon()
        
        # Check if shot hits
        if weapon.ammo < weapon.max_ammo:  # Shot was fired
            dist = self.distance_to(target)
            if dist < weapon.get_range():
                # Hit chance decreases with distance
                hit_chance = 1.0 - (dist / weapon.get_range()) * 0.5
                if random.random() < hit_chance:
                    target.take_damage(weapon.get_damage())
    
    def take_damage(self, damage: int):
        if self.is_alive:
            self.health -= damage
            if self.health <= 0:
                self.die()
    
    def die(self):
        self.is_alive = False
        self.respawn_timer = RESPAWN_TIME
    
    def respawn(self, game_map: 'GameMap'):
        self.health = self.max_health
        self.is_alive = True
        
        # Random respawn location
        valid = False
        while not valid:
            self.x = random.uniform(PLAYER_SIZE + 50, SCREEN_WIDTH - PLAYER_SIZE - 50)
            self.y = random.uniform(PLAYER_SIZE + 50, SCREEN_HEIGHT - PLAYER_SIZE - 50)
            
            valid = True
            for building in game_map.buildings:
                if self.collides_with_building(building):
                    valid = False
                    break
        
        self.vx = 0
        self.vy = 0
        # Reset weapons
        for weapon in self.weapons:
            weapon.ammo = weapon.max_ammo
            weapon.is_reloading = False
    
    def draw(self, screen: pygame.Surface):
        if not self.is_alive:
            return
        
        # Draw player circle
        color = YELLOW if self.is_player else RED
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), PLAYER_SIZE)
        
        # Draw health bar
        bar_width = 30
        bar_height = 5
        bar_x = self.x - bar_width / 2
        bar_y = self.y - PLAYER_SIZE - 15
        
        pygame.draw.rect(screen, RED, (bar_x, bar_y, bar_width, bar_height))
        health_width = (self.health / self.max_health) * bar_width
        pygame.draw.rect(screen, GREEN, (bar_x, bar_y, health_width, bar_height))
        
        # Draw direction indicator
        if self.vx != 0 or self.vy != 0:
            end_x = self.x + self.last_direction[0] * 20
            end_y = self.y + self.last_direction[1] * 20
            pygame.draw.line(screen, WHITE, (self.x, self.y), (end_x, end_y), 2)

class GameMap:
    def __init__(self):
        self.buildings = self._generate_city()
    
    def _generate_city(self) -> List[dict]:
        buildings = []
        
        # Create a grid of buildings to represent a small city
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
                        'height': building_size,
                        'color': BROWN
                    })
        
        return buildings
    
    def draw(self, screen: pygame.Surface):
        # Draw grass background
        screen.fill(DARK_GREEN)
        
        # Draw buildings
        for building in self.buildings:
            pygame.draw.rect(screen, building['color'], 
                           (building['x'], building['y'], 
                            building['width'], building['height']))
            pygame.draw.rect(screen, LIGHT_GRAY,
                           (building['x'], building['y'],
                            building['width'], building['height']), 3)

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Battle Royale - 10 Players")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.large_font = pygame.font.Font(None, 36)
        
        self.game_map = GameMap()
        self.players = self._initialize_players()
        self.running = True
        self.player = self.players[0]
    
    def _initialize_players(self) -> List[Player]:
        players = []
        
        # Create player (you)
        player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, is_player=True)
        players.append(player)
        
        # Create 9 bot players
        for _ in range(9):
            valid = False
            while not valid:
                x = random.uniform(PLAYER_SIZE + 50, SCREEN_WIDTH - PLAYER_SIZE - 50)
                y = random.uniform(PLAYER_SIZE + 50, SCREEN_HEIGHT - PLAYER_SIZE - 50)
                
                valid = True
                for building in self.game_map.buildings:
                    if (x - PLAYER_SIZE < building['x'] + building['width'] and
                        x + PLAYER_SIZE > building['x'] and
                        y - PLAYER_SIZE < building['y'] + building['height'] and
                        y + PLAYER_SIZE > building['y']):
                        valid = False
                        break
            
            bot = Player(x, y, is_player=False)
            players.append(bot)
        
        return players
    
    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_1:
                    self.player.current_weapon_idx = 0
                elif event.key == pygame.K_2:
                    self.player.current_weapon_idx = 1
                elif event.key == pygame.K_3:
                    self.player.current_weapon_idx = 2
                elif event.key == pygame.K_r:
                    weapon = self.player.get_current_weapon()
                    if weapon.ammo < weapon.max_ammo and not weapon.is_reloading:
                        weapon.is_reloading = True
                        weapon.reload_timer = weapon.reload_time
        
        # Movement input
        keys = pygame.key.get_pressed()
        self.player.vx = 0
        self.player.vy = 0
        
        if keys[pygame.K_z]:  # Forward
            self.player.vy = -PLAYER_SPEED
        if keys[pygame.K_s]:  # Backward
            self.player.vy = PLAYER_SPEED
        if keys[pygame.K_q]:  # Left
            self.player.vx = -PLAYER_SPEED
        if keys[pygame.K_d]:  # Right
            self.player.vx = PLAYER_SPEED
        
        # Update last direction for drawing
        if self.player.vx != 0 or self.player.vy != 0:
            self.player.last_direction = (self.player.vx, self.player.vy)
        
        # Shooting
        if pygame.mouse.get_pressed()[0]:  # Left mouse button
            self.player.shoot()
    
    def update(self, dt: float):
        # Update all players
        for player in self.players:
            player.update(dt, self.players, self.game_map)
        
        # Check for melee damage (knife range)
        for i, player in enumerate(self.players):
            if not player.is_alive:
                continue
            
            weapon = player.get_current_weapon()
            if weapon.weapon_type == WeaponType.KNIFE:
                for j, other in enumerate(self.players):
                    if i != j and other.is_alive:
                        if player.distance_to(other) < weapon.get_range():
                            if player.is_player:
                                if pygame.mouse.get_pressed()[0]:
                                    other.take_damage(weapon.get_damage())
                            else:
                                other.take_damage(weapon.get_damage())
    
    def draw(self):
        self.game_map.draw(self.screen)
        
        # Draw players
        for player in self.players:
            player.draw(self.screen)
        
        # Draw HUD
        if self.player.is_alive:
            # Health
            health_text = self.font.render(f"Health: {int(self.player.health)}/{self.player.max_health}", True, WHITE)
            self.screen.blit(health_text, (10, 10))
            
            # Current weapon
            weapon = self.player.get_current_weapon()
            weapon_names = {WeaponType.ASSAULT_RIFLE: "Assault Rifle", 
                          WeaponType.PISTOL: "Pistol", 
                          WeaponType.KNIFE: "Knife"}
            weapon_name = weapon_names[weapon.weapon_type]
            
            if weapon.weapon_type != WeaponType.KNIFE:
                ammo_text = self.font.render(f"Weapon: {weapon_name} ({weapon.ammo}/{weapon.max_ammo})", True, WHITE)
                if weapon.is_reloading:
                    ammo_text = self.font.render(f"Weapon: {weapon_name} (RELOADING...)", True, RED)
            else:
                ammo_text = self.font.render(f"Weapon: {weapon_name}", True, WHITE)
            
            self.screen.blit(ammo_text, (10, 40))
            
            # Controls
            controls = self.font.render("Z/Q/S/D: Move | 1/2/3: Weapon | R: Reload | Click: Shoot", True, LIGHT_GRAY)
            self.screen.blit(controls, (10, SCREEN_HEIGHT - 30))
            
            # Alive players count
            alive_count = sum(1 for p in self.players if p.is_alive)
            alive_text = self.font.render(f"Players Alive: {alive_count}/10", True, YELLOW)
            self.screen.blit(alive_text, (SCREEN_WIDTH - 200, 10))
        else:
            # Death screen
            respawn_in = max(0, self.player.respawn_timer)
            death_text = self.large_font.render(f"YOU DIED!", True, RED)
            respawn_text = self.font.render(f"Respawning in: {respawn_in:.1f}s", True, WHITE)
            self.screen.blit(death_text, (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 50))
            self.screen.blit(respawn_text, (SCREEN_WIDTH // 2 - 80, SCREEN_HEIGHT // 2 + 20))
        
        pygame.display.flip()
    
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0  # Delta time in seconds
            
            self.handle_input()
            self.update(dt)
            self.draw()
        
        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()
