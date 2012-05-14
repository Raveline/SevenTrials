# * Should store a reference to the root Object on components so sub components dont need to use things like self.owner.owner
# * Seperate code into files
# * Move data into data files
# * Starting town
# * Character creation screen (name for now)

import libtcodpy as libtcod
import math
import os
import shelve
import textwrap

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

BAR_WIDTH = 20
PANEL_HEIGHT = 8
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

CHARACTER_SCREEN_WIDTH = 30
INVENTORY_WIDTH = 50
LEVEL_SCREEN_WIDTH = 40
EQUIPMENT_WIDTH = 50

MAP_WIDTH = 80
MAP_HEIGHT = 43
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

color_dark_wall = libtcod.Color(0, 0, 100)
color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(50, 50, 150)
color_light_ground = libtcod.Color(200, 180, 50)

LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_DAMAGE = 25
FIREBALL_RADIUS = 3
HEAL_AMOUNT = 40
LIGHTNING_RANGE = 5
LIGHTNING_DAMAGE = 40


def handle_keys():
	global fov_recompute, key, mouse
 
	# key = libtcod.console_check_for_keypress(libtcod.KEY_PRESSED)
	libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
	if key.vk == libtcod.KEY_ESCAPE:
		return 'exit'

	if game_state == 'playing':
		if key.vk == libtcod.KEY_UP:
			player_move_or_attack(0, -1)
		elif key.vk == libtcod.KEY_DOWN:
			player_move_or_attack(0, 1)
		elif key.vk == libtcod.KEY_LEFT:
			player_move_or_attack(-1, 0)
		elif key.vk == libtcod.KEY_RIGHT:
			player_move_or_attack(1, 0)
		elif key.vk == libtcod.KEY_ENTER and key.lalt:
			libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
		else:
			key_char = chr(key.c)

			if key_char == 'g':
				for object in objects:
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break;

			if key_char == 'i':
				libtcod.console_flush()
				chosen_item = inventory_menu('Press the key next to an item to use it, or an other to cancel.\n')
				if chosen_item is not None:
					chosen_item.use()

			if key_char == 'e':
				print "e!"
				libtcod.console_flush()
				chosen_equippable = equipment_menu('Press the key next to an equipped item to remove it.\n')
				if chosen_equippable is not None:
					player.fighter.equipment.unequip(chosen_equippable)

			if key_char == 'd':
				chosen_item = inventory_menu('Press the key next to an item to drop it, or an other to cancel.\n')
				if chosen_item is not None:
					chosen_item.drop()

			if key_char == '>':
				if stairs.x == player.x and stairs.y == player.y:
					next_level()

			if key_char == 'c':
				level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
				libtcod.console_flush()
				msgbox('Character Information\n'+
					'\nLevel: ' + str(player.level) +
					'\nExperience: ' + str(player.fighter.xp) +
					'\nExperience to level up: ' + str(level_up_xp) +
					'\n\nMaximum HP: ' + str(player.fighter.max_hp) + 
					'\nAttack: ' + str(player.fighter.get_score('power')) + 
					'\nDefense: ' + str(player.fighter.get_score('defense')), CHARACTER_SCREEN_WIDTH)

			return 'didnt-take-turn'

def player_move_or_attack(dx, dy):
	global fov_recompute

	x = player.x + dx
	y = player.y + dy

	target = None
	for object in objects:
		if object.fighter and object.x == x and object.y == y:
			target = object
			break

	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(dx, dy)
		fov_recompute = True


def check_level_up():
	level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
	if player.fighter.xp >= level_up_xp:
		player.level += 1
		player.fighter.xp -= level_up_xp
		message('Your battle skills grow stringer! You reached level ' + str(player.level) + '!', libtcod.yellow)

		choice = None
		while choice == None:
			choice = menu('lLevel up! Choose a stat to raise:\n',
				['Constitution (+20 HP, from ' + str(player.fighter.max_hp) + ')'],
				['Strength (+1 attack, from ' + str(player.fighter.power) + ')'],
				['Agility (+1 defense, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)

		if choice == 0:
			player.fighter.max_hp += 20
			player.fighter.hp += 20
		elif choice == 1:
			player.fighter.power += 1
		elif choice == 2:
			player.fighter.defense += 1



class Object:
	def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None):
		self.x = x
		self.y = y
		self.char = char
		self.name = name
		self.color = color
		self.blocks = blocks
		self.always_visible = always_visible
		self.fighter = fighter
		if self.fighter:
			self.fighter.owner = self
		self.ai = ai
		if self.ai:
			self.ai.owner = self
		self.item = item
		if self.item:
			self.item.owner = self

	def move(self, dx, dy):
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy 

	def move_towards(self, target_x, target_y):
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)
		dx = int(round(dx / distance))
		dy = int(round(dy / distance))
		self.move(dx, dy)

	def distance(self, x, y):
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

	def distance_to(self, other):
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)

	def draw(self):
		if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or
			(self.always_visible and map[self.x][self.y].explored)):
			libtcod.console_set_default_foreground(con, self.color)
			libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

	def clear(self):
		libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

	def send_to_back(self):
		global objects
		objects.remove(self)
		objects.insert(0, self)


class Fighter:
	def __init__(self, hp, defense, power, xp, death_function=None, equipment=None):
		self.max_hp = hp
		self.hp = hp
		self.defense = defense
		self.power = power
		self.xp = xp
		if isinstance(death_function, str):
			self.death_function = globals()[death_function]
		else:
			self.death_function = death_function
		self.equipment = equipment;
		if self.equipment:
			self.equipment.owner = self;

	def get_score(self, value_name):
		score = 0
		if hasattr(self, value_name):
			score = getattr(self, value_name)

		# TODO: this is also where you would want to factor in bonuses from equipment and effects and such
		# Factor in bonuses from equipment
		if self.equipment:
			for slot_name in self.equipment.slots:
				equippable = self.equipment.slots[slot_name]
				eq_bonus = equippable.score_bonuses.get(value_name)
				if eq_bonus is not None:
					score += eq_bonus

		return score

	def take_damage(self, damage):
		if damage > 0:
			self.hp -= damage

		if self.hp <= 0:
			function = self.death_function
			if function is not None:
				function(self.owner)

		if self.owner != player:
			player.fighter.xp != self.xp

	def attack(self, target):
		damage = self.get_score('power') - target.fighter.get_score('defense')

		if damage > 0:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
			target.fighter.take_damage(damage)
		else:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')

	def heal(self, amount):
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp

# A component of Fighter
class Equipment:
	def __init__(self, equip_slots=None):
		self.equip_slots = equip_slots
		self.slots = {}

	def equip(self, equippable):
		global inventory

		if equippable.equip_slot not in self.equip_slots:
			if self.owner.owner == player:
				print 'You do not have the ' + equippable.equip_slot + ' equip slot.'
			return False

		equippable.fighter = self.owner

		if self.owner.owner == player:
			message('You equip the '+equippable.owner.owner.name+' to your '+equippable.equip_slot)
			inventory.remove(equippable.owner.owner)

		self.slots[equippable.equip_slot] = equippable

	def unequip(self, equippable):
		global inventory
		message('You remove the '+equippable.owner.owner.name+' from your '+equippable.equip_slot)
		del self.slots[equippable.equip_slot]
		if not equippable.owner.pick_up():
			equippable.owner.drop()

class BasicMonster:
	def take_turn(self):
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)


class ConfusedMonster:
	def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns

	def take_turn(self):
		if self.num_turns > 0:
			self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
			self.num_turns -= 1
		else:
			self.owner.ai = self.old_ai
			message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)

class Item:
	def __init__(self, use_function=None, equippable=None):
		self.use_function = use_function
		self.equippable = equippable
		if self.equippable:
			self.equippable.owner = self

	def pick_up(self):
		if len(inventory) >= 26:
			message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
			return False
		else:
			inventory.append(self.owner)
			if self.owner in objects:
				objects.remove(self.owner)
			message('You picked up a ' + self.owner.name + '!', libtcod.green)
			return True

	def drop(self):
		objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.x = player.x
		self.owner.y = player.y
		message('You dropped a ' + self.owner.name + '.', libtcod.yellow)

	def use(self):
		global player

		if self.use_function is None:
			if self.equippable:
				player.fighter.equipment.equip(self.equippable)
			else:
				message('The ' + self.owner.name + ' cannot be used.')
		else:
			if self.use_function() != 'cancelled':
				inventory.remove(self.owner)

class Equippable:
	def __init__(self, equip_slot=None, score_bonuses=None):
		self.equip_slot = equip_slot
		self.score_bonuses = score_bonuses

def player_death(player):
	global game_state
	message('You died!', libtcod.red)
	game_state = 'dead'
	player.char = '%'
	player.color = libtcod.dark_red


def monster_death(monster):
	message(monster.name.capitalize() + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.', libtcod.orange)
	monster.char = '%'
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()


def cast_heal():
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health', libtcod.red)
		return 'cancelled'

	message('Your wounds start to feel better!', libtcod.light_violet)
	player.fighter.heal(HEAL_AMOUNT)


def cast_lightning():
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None:
		message('No enemy is close enough to strike.', libtcod.red)
		return 'cancelled'
	message('A lightning bolt strikes the ' + monster.name + ' with a loud thunder! the damage is ' + str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
	monster.fighter.take_damage(LIGHTNING_DAMAGE)	


def cast_confuse():
	message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
	monster = target_monster(CONFUSE_RANGE)
	if monster is None: return 'cancelled'

	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai)
	monster.ai.owner = monster
	message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)


def cast_fireball():
	message('Left-click a target tile for the fireball, or right-click to cancel.', libtcod.light_cyan)
	(x, y) = target_tile()
	if x is None: return 'cancelled'
	message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)

	for obj in objects:
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
			message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
			obj.fighter.take_damage(FIREBALL_DAMAGE)

def closest_monster(max_range):
	closest_enemy = None
	closest_dist = max_range + 1

	for object in objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
			dist = player.distance_to(object)
			if dist < closest_dist:
				closest_enemy = object
				closest_dist = dist

	return closest_enemy


def random_choice_index(chances):
	dice = libtcod.random_get_int(0, 1, sum(chances))
	running_sum = 0
	choice = 0
	for w in chances:
		running_sum += w
		if dice <= running_sum:
			return choice
		choice += 1


def random_choice(chances_dict):
	chances = chances_dict.values()
	strings = chances_dict.keys()
	return strings[random_choice_index(chances)]


class Tile:
	def __init__(self, blocked, block_sight=None, background_color=None, bgColorMap=None):
		self.blocked = blocked
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight
		self.explored = False
		self.background_color = background_color
		if bgColorMap is not None:
			random_index = libtcod.random_get_int(0, 0, 8)
			self.background_color = bgColorMap[random_index]

class Rect:
	def __init__(self, x, y, w, h):
		self.w = w
		self.h = h		
		self.x1 = x
		self.y1 = y		
		self.x2 = x + w
		self.y2 = y + h

	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)

	def intersect(self, other):
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
			    self.y1 <= other.y2 and self.y2 >= other.y1)


def next_level():
	global dungeon_level
	message('You take a moment to rest, and record your strength.', libtcod.light_violet)
	player.fighter.heal(player.fighter.max_hp / 2)

	message('After a rare moment of peace, you descend deeper into the heart of the dungeon...', libtcod.red)
	dungeon_level += 1
	make_map()
	initialize_fov()


def make_map():
	global map, objects, stairs

	floorBGColorMapIndexes = [0, 8]
	floorBGColorMapColors = [libtcod.Color(180, 134, 30), libtcod.Color(200, 180, 50)]
	tileBGColorMap = libtcod.color_gen_map(floorBGColorMapColors, floorBGColorMapIndexes)

	wallBGColorMapIndexes = [0, 8]
	wallBGColorMapColors = [libtcod.Color(83, 60, 25), libtcod.Color(112, 81, 34)]
	wallBGColorMap = libtcod.color_gen_map(wallBGColorMapColors, wallBGColorMapIndexes)

	objects = [player]

	map = [[ Tile(True, bgColorMap=wallBGColorMap)
		for y in range(MAP_HEIGHT) ]
			for x in range(MAP_WIDTH) ]

	rooms = []
	num_rooms = 0
	for r in range(MAX_ROOMS):
		w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
		y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
		new_room = Rect(x, y, w, h)
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break
		if not failed:
			create_room(new_room, tileBGColorMap)
			place_objects(new_room)
			(new_x, new_y) = new_room.center()

			if num_rooms == 0:
				player.x = new_x
				player.y = new_y
			else:
				(prev_x, prev_y) = rooms[num_rooms-1].center()
				if libtcod.random_get_int(0, 0, 1) == 1:
					create_h_tunnel(prev_x, new_x, prev_y, tileBGColorMap)
					create_v_tunnel(prev_y, new_y, new_x, tileBGColorMap)
				else:
					create_v_tunnel(prev_y, new_y, prev_x, tileBGColorMap)
					create_h_tunnel(prev_x, new_x, new_y, tileBGColorMap)
			rooms.append(new_room)
			num_rooms += 1

	stairs = Object(new_x, new_y, '>', 'stairs', libtcod.white, always_visible=True)
	objects.append(stairs)

def create_room(room, bgColorMap):
	global map
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False
			random_index = libtcod.random_get_int(0, 0, 8)
			map[x][y].background_color = bgColorMap[random_index]

def create_h_tunnel(x1, x2, y, bgColorMap):
	global map;
	for x in range(min(x1,x2), max(x1, x2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
		random_index = libtcod.random_get_int(0, 0, 8)
		map[x][y].background_color = bgColorMap[random_index]

def create_v_tunnel(y1, y2, x, bgColorMap):
	global map
	for y in range(min(y1,y2), max (y1,y2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False
		random_index = libtcod.random_get_int(0, 0, 8)
		map[x][y].background_color = bgColorMap[random_index]

def place_objects(room):
	max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6]])
	monster_chances = {}
	monster_chances['orc'] = 80
	monster_chances['troll'] = from_dungeon_level([[15, 3], [30, 5], [60, 7]])

	max_items = from_dungeon_level([[1, 1], [2, 4]])
	item_chances = {}
	item_chances['heal'] = 35
	item_chances['lightning'] = from_dungeon_level([[25, 4]])
	item_chances['fireball'] = from_dungeon_level([[25, 6]])
	item_chances['confuse'] = from_dungeon_level([[10, 2]])
	item_chances['helmet'] = 80

	num_monsters = libtcod.random_get_int(0, 0, max_monsters)

	for i in range(num_monsters):
		x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
		y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

		if not is_blocked(x, y):
			choice = random_choice(monster_chances)
			if choice == 'orc':
				tmpData = monster_data[choice]
				fighter_component = Fighter(xp=tmpData['xp'], hp=tmpData['hp'], defense=tmpData['defense'], power=tmpData['power'], death_function=tmpData['death_function'])
				ai_component = BasicMonster()
				monster = Object(x, y, tmpData['character'], tmpData['name'], libtcod.desaturated_green, blocks=True, fighter=fighter_component, ai=ai_component)
			elif choice == 'troll':
				tmpData = monster_data[choice]
				fighter_component = Fighter(xp=tmpData['xp'], hp=tmpData['hp'], defense=tmpData['defense'], power=tmpData['power'], death_function=tmpData['death_function'])
				ai_component = BasicMonster()
				monster = Object(x, y, tmpData['character'], tmpData['name'], libtcod.darker_green, blocks=True, fighter=fighter_component, ai=ai_component)
			objects.append(monster)

	num_items = libtcod.random_get_int(0, 0, max_items)

	for i in range(num_items):
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

		if not is_blocked(x, y):
			choice = random_choice(item_chances)
			if choice == 'heal':
				item_component = Item(use_function=cast_heal)
				item = Object(x, y, '!', 'healing potion', libtcod.violet, item=item_component)
			elif choice == 'lightning':
				item_component = Item(use_function=cast_lightning)
				item = Object(x, y, '#', 'scroll of lightning bolt', libtcod.light_yellow, item=item_component)
			elif choice == 'fireball':
				item_component = Item(use_function=cast_fireball)
				item = Object(x, y, '#', 'scroll of fireball', libtcod.light_yellow, item=item_component)
			elif choice == 'confuse':
				item_component = Item(use_function=cast_confuse)
				item = Object(x, y, '#', 'scroll of confusion', libtcod.light_yellow, item=item_component)
			elif choice == 'helmet':
				score_bonuses = {'defense': 5}
				equippable_component = Equippable(equip_slot="head", score_bonuses=score_bonuses)
				item_component = Item(equippable=equippable_component)
				item = Object(x, y, '[', 'helmet', libtcod.dark_sepia, item=item_component)
			item.always_visible = True
			objects.append(item)
			item.send_to_back()

def is_blocked(x, y):
	if map[x][y].blocked:
		return True

	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True

	return False

def from_dungeon_level(table):
	for (value, level) in reversed(table):
		if dungeon_level >= level:
			return value
	return 0

def render_all():
	global fov_map, fov_recompute
	global color_dark_wall, color_dark_ground, color_light_wall, color_light_ground
	if fov_recompute:
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

	for object in objects:
		if object != player:
			object.draw()
	player.draw()

	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			visible = libtcod.map_is_in_fov(fov_map, x, y)
			wall = map[x][y].block_sight
			if not visible:
				if map[x][y].explored:
					if wall:
						libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
					else:
						libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
			else:
				if wall:
					if map[x][y].background_color:
						libtcod.console_set_char_background(con, x, y, map[x][y].background_color, libtcod.BKGND_SET)
					else:
						libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
				else:
					if map[x][y].background_color:
						libtcod.console_set_char_background(con, x, y, map[x][y].background_color, libtcod.BKGND_SET)
					else:
						libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
				map[x][y].explored = True

	libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)

	y = 1
	libtcod.console_set_background_flag(panel, libtcod.BKGND_NONE)
	libtcod.console_set_alignment(panel, libtcod.LEFT)
	for (line, color) in game_msgs:
		libtcod.console_set_default_foreground(panel, color)
		libtcod.console_print(panel, MSG_X, y, line)
		y += 1

	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
		libtcod.light_red, libtcod.darker_red)

	libtcod.console_set_alignment(panel, libtcod.LEFT)
	libtcod.console_set_background_flag(panel, libtcod.BKGND_NONE)
	libtcod.console_print(panel, 1, 3, 'Dungeon level ' + str(dungeon_level))

	libtcod.console_set_default_foreground(panel, libtcod.light_gray)
	libtcod.console_set_alignment(panel, libtcod.LEFT)
	libtcod.console_print(panel, 1, 0, get_names_under_mouse())

	libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	bar_width = int(float(value) / maximum * total_width)
	libtcod.console_set_background_flag(panel, libtcod.BKGND_SET)
	libtcod.console_set_default_background(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False)

	libtcod.console_set_default_background(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False)

	libtcod.console_set_background_flag(panel, libtcod.BKGND_NONE)
	libtcod.console_set_default_foreground(panel, libtcod.white)
	libtcod.console_set_alignment(panel, libtcod.CENTER)
	libtcod.console_print(panel, x + total_width / 2, y,
		name + ': ' + str(value) + '/' + str(maximum))


def message(new_msg, color=libtcod.white):
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

	for line in new_msg_lines:
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]
		game_msgs.append( (line, color) )


def get_names_under_mouse():
	#mouse = libtcod.mouse_get_status()
	(x, y) = (mouse.cx, mouse.cy)

	#print str(x) + ', ' + str(y)

	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
	names = ', '.join(names)
	return names.capitalize()


def menu(header, options, width):
	if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')
	libtcod.console_set_alignment(0, libtcod.LEFT)
	libtcod.console_set_alignment(con, libtcod.LEFT)
	header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == '':
		header_height = 0
	height = len(options) + header_height

	window = libtcod.console_new(width, height)
	libtcod.console_set_default_foreground(window, libtcod.white)
	libtcod.console_set_background_flag(window, libtcod.BKGND_NONE)
	
	libtcod.console_print_rect(window, 0, 0, width, height, header)

	y = header_height
	letter_index = ord('a')
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		libtcod.console_print(window, 0, y, text)
		y += 1
		letter_index += 1

	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)

	if key.vk == libtcod.KEY_ENTER and key.lalt:
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None


def target_tile(max_range=None):
	while True:
		render_all()
		libtcod.console_flush()

		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)

		(x, y) = (mouse.cx, mouse.cy)

		if mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y):
			if max_range is None or player.distance(x, y) <= max_range:
				return (x, y)

		if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
			return (None, None)


def target_monster(max_range=None):
	while True:
		(x, y) = target_tile(max_range)
		if x is None:
			return None

		for obj in objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player:
				return obj

def inventory_menu(header):
	if len(inventory) == 0:
		options = ['Inventory is empty.']
	else:
		options = [item.name for item in inventory]

	index = menu(header, options, INVENTORY_WIDTH)

	if index is None or len(inventory) == 0: return None
	return inventory[index].item

def equipment_menu(header):
	keys = None
	if len(player.fighter.equipment.slots) == 0:
		print "Nothing equipped!"
		options =['You have nothing equipped']
	else:
		options = []
		keys = []
		for slot_name in player.fighter.equipment.slots:
			equippable = player.fighter.equipment.slots[slot_name]
			options.append("("+slot_name+") "+equippable.owner.owner.name)
			keys.append(slot_name)

	index = menu(header, options, EQUIPMENT_WIDTH)

	if index is None or len(player.fighter.equipment.slots) == 0: return None
	if keys is None:
		return player.fighter.equipment.slots[index]
	else:
		return player.fighter.equipment.slots[keys[index]]

def msgbox(text, width=50):
	menu(text, [], width)

def main_menu():
	img = libtcod.image_load('menu_background.png')

	while not libtcod.console_is_window_closed():
		libtcod.image_blit_2x(img, 0, 0, 0)

		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_set_background_flag(0, libtcod.BKGND_NONE)
		libtcod.console_set_alignment(0, libtcod.CENTER)
		libtcod.console_print(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, 'SEVEN TRIALS')
		libtcod.console_print(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, 'By nefD')

		choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)

		if choice == 0:
			new_game()
			play_game()
		elif choice == 1:
			try:
				load_game()
			except:
				libtcod.console_flush()
				msgbox('\n No saved games to load.\n', 24)
				continue
			play_game()
		elif choice == 2:
			break

def new_game():
	global player, inventory, game_msgs, game_state, dungeon_level

	dungeon_level = 1
	game_msgs = []
	inventory = []
	player_equip_slots = ["head", "torso"]
	player_equipment_component = Equipment(equip_slots=player_equip_slots)
	player_fighter_component = Fighter(xp=0, hp=100, defense=1, power=4, death_function=player_death, equipment=player_equipment_component)
	player = Object(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=player_fighter_component)
	player.level = 1
	game_state = 'playing'
	make_map()
	initialize_fov()

	message('Welcome stranger! Prepare to perish in the Tombs of the Ancient Kings.', libtcod.red)


def initialize_fov():
	global fov_recompute, fov_map
	fov_recompute = True
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
	libtcod.console_clear(con)


def play_game():
	player_action = None

	while not libtcod.console_is_window_closed():
		render_all()

		libtcod.console_flush()

		check_level_up()

		for object in objects:
			object.clear()

		player_action = handle_keys()
		if player_action == 'exit':
			break

		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in objects:
				if object.ai:
					object.ai.take_turn()

	save_game()	


def save_game():
	file = shelve.open('savegame', 'n')
	file['map'] = map
	file['objects'] = objects
	file['player_index'] = objects.index(player)
	file['stairs_index'] = objects.index(stairs)
	file['dungeon_level'] = dungeon_level
	file['inventory'] = inventory
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file.close()

def load_game():
	global map, objects, player, inventory, game_msgs, game_state, stairs, dungeon_level

	file = shelve.open('savegame', 'r')
	map = file['map']
	objects = file['objects']
	player = objects[file['player_index']]
	stairs = objects[file['stairs_index']]
	dungeon_level = file['dungeon_level']
	inventory = file['inventory']
	game_msgs = file['game_msgs']
	game_state = file['game_state']
	file.close()

	initialize_fov()

def load_data():
	parser = libtcod.parser_new()
	monsterStruct = libtcod.parser_new_struct(parser, 'monster')
	libtcod.struct_add_property(monsterStruct, 'name', libtcod.TYPE_STRING, True)
	libtcod.struct_add_property(monsterStruct, 'character', libtcod.TYPE_STRING, True)
	libtcod.struct_add_property(monsterStruct, 'xp', libtcod.TYPE_INT, True)
	libtcod.struct_add_property(monsterStruct, 'hp', libtcod.TYPE_INT, True)
	libtcod.struct_add_property(monsterStruct, 'defense', libtcod.TYPE_INT, True)
	libtcod.struct_add_property(monsterStruct, 'power', libtcod.TYPE_INT, True)
	libtcod.struct_add_property(monsterStruct, 'death_function', libtcod.TYPE_STRING, True)
	libtcod.parser_run(parser, os.path.join('data', 'monster_data.cfg'), MonsterDataListener())

class MonsterDataListener:
    def new_struct(self, struct, name):
    	global monster_data
        self.current_name = name
        monster_data[name] = {}
        return True

    def new_flag(self, name):
        monster_data[self.current_name][name] = True
        return True

    def new_property(self,name, typ, value):
    	global monster_data
        monster_data[self.current_name][name] = value
        return True

    def end_struct(self, struct, name):
    	self.current_name = None
        return True

    def error(self,msg):
        print 'Monster data parser error : ', msg
        if self.current_name is not None:
        	del monster_data[self.current_name]
        	self.current_name = None
        return True

libtcod.console_set_custom_font("arial10x10.png", libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'FirstRL', False)
libtcod.sys_set_fps(LIMIT_FPS)
key=libtcod.Key()
mouse=libtcod.Mouse()
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

monster_data = {}
load_data()
main_menu()