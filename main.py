# - Seperate code into multiple files
# - Mark map cells as not being walkable when inhabited by an actor, and mark the cell back to walkable when the actor moves 
# - Item stacking
# - Move item and monster placement chances into data files, will have to use a delimited string (no support for lists of lists)
# - Menu should allow use of arrow keys
# - Action menus (have multiple 'actions' in horizontal line at top.. you select an action from these to perform on the menu option you select)
# - Time Management; Actors queue an action. Once enough world time has passed, the action occurs
#     - timePasses()
#     - retrieve action from queue with lowest amount of time left on it
#     - action occurs and is processed
#     - time action had remaining is subtracted from all queued actions
#     - wash, rinse, repeat
# - Improve lighting support; should be able to define an arbitrary number of lights, maybe attach them to objects
#	- Lights should use fov
# - NPC's occaisionally wander into their doorways in the town map
# - Message log
# - Masteries
# 	- Each level of a mastery awards score bonuses and/or an ability
# - Generalized function for drawing a framed, optionally titled window to a given console
# - Effects (enchantments, curses, etc.)
# - Only display the ! flashing symbol if an npc is a quest giver
# - Place down stairs in an npc quest givers building
# - Tiles containing items should have some kind of background color highlight
# - include Psyco
# - Take stairs out of the global namespace, there needs to be a map.stairs[] list

import libtcodpy as libtcod
import math
import os
import shelve
import textwrap

SCREEN_WIDTH = 120
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

BAR_WIDTH = 20
PANEL_HEIGHT = 8
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

MENU_BACKGROUND_COLOR = libtcod.Color(160, 147, 106)
MENU_TEXT_COLOR = libtcod.white
MENU_HEADER_TEXT_COLOR = libtcod.white
MENU_HEADER_BACKGROUND_COLOR = libtcod.darker_sepia
ABILITIES_WIDTH = 50
CHARACTER_SCREEN_WIDTH = 30
INVENTORY_WIDTH = 50
LEVEL_SCREEN_WIDTH = 40
EQUIPMENT_WIDTH = 50

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10.0
TORCH_INTENSITY = 0.25
TORCH_COLOR = libtcod.Color(75, 75, 75)

color_dark_wall = libtcod.Color(15, 15, 30)
color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(10, 10, 10)
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

			if key_char == 'a':
				libtcod.console_flush()
				chosen_ability = abilities_menu('Abilities\n')
				if chosen_ability is not None:
					chosen_ability.use()

			if key_char == 'i':
				libtcod.console_flush()
				chosen_item = inventory_menu('Inventory\n')
				if chosen_item is not None:
					chosen_item.use()

			if key_char == 'e':
				libtcod.console_flush()
				chosen_equippable = equipment_menu('Equipment\n')
				if chosen_equippable is not None:
					player.actor.equipment.unequip(chosen_equippable)

			if key_char == 'd':
				chosen_item = inventory_menu('Drop Item\n')
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
					'\nExperience: ' + str(player.actor.xp) +
					'\nExperience to level up: ' + str(level_up_xp) +
					'\n\nMaximum HP: ' + str(player.actor.max_hp) + 
					'\nAttack: ' + str(player.actor.get_score('power')) + 
					'\nDefense: ' + str(player.actor.get_score('defense')), CHARACTER_SCREEN_WIDTH)

			if key_char == 'M':
				message_log()

			return 'didnt-take-turn'

def player_move_or_attack(dx, dy):
	global fov_recompute

	x = player.x + dx
	y = player.y + dy

	attack_target = None
	interact_target = None
	for object in objects:
		if object.x == x and object.y == y:
			if object.actor:
				attack_target = object
				break
			elif object.interactive:
				if object.interactive.use_on_bump is True:
					interact_target = object
					break

	if attack_target is not None:
		player.actor.attack(attack_target)
	elif interact_target is not None:
		interact_target.interactive.use()
	else:
		player.move(dx, dy)
		fov_recompute = True


def check_level_up():
	level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
	if player.actor.xp >= level_up_xp:
		player.level += 1
		player.actor.xp -= level_up_xp
		message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', libtcod.yellow)

		choice = None
		while choice == None:
			choice = menu('Level up! Choose a stat to raise:\n',
				['Constitution (+20 HP, from ' + str(player.actor.max_hp) + ')'],
				['Strength (+1 attack, from ' + str(player.actor.power) + ')'],
				['Agility (+1 defense, from ' + str(player.actor.defense) + ')'], LEVEL_SCREEN_WIDTH)

		if choice == 0:
			player.actor.max_hp += 20
			player.actor.hp += 20
		elif choice == 1:
			player.actor.power += 1
		elif choice == 2:
			player.actor.defense += 1

class Ability:
	def __init__(self, name, use_function=None):
		self.name = name
		if isinstance(use_function, str):
			self.use_function = globals()[use_function]
		else:
			self.use_function = use_function		

	def use(self):
		message('You use your '+self.name+' ability!', libtcod.yellow)
		if self.use_function:
			self.use_function()

class Map:
	def __init__(self, width, height, name=None, filled=True, ambient_light=0.0, full_bright=False):
		self.width = width
		self.height = height
		self.ambient_light = ambient_light
		self.full_bright = full_bright
		self.name = name

		self.grid = [[ Tile(filled)
			for y in range(height) ]
				for x in range(width) ]

class Object:
	def __init__(self, x, y, char, name, color, background_color=None, blocks=False, always_visible=False, actor=None, ai=None, item=None, interactive=None):
		self.x = x
		self.y = y
		self.char = char
		self.name = name
		self.color = color
		self.background_color = background_color
		self.blocks = blocks
		self.always_visible = always_visible
		self.actor = actor
		if self.actor:
			self.actor.owner = self
		self.ai = ai
		if self.ai:
			self.ai.owner = self
		self.item = item
		if self.item:
			self.item.owner = self
		self.interactive = interactive
		if self.interactive:
			self.interactive.owner = self

		self.flash_char = None
		self.flash_color = None
		self.flash_counter = None

	def flash_character(self, char=None, color=None):
		self.flash_char = char
		self.flash_color = color
		self.flash_counter = 0.0

	def move(self, dx, dy):
		target_x = self.x + dx
		target_y = self.y + dy
		if (target_x < 0 or target_y < 0 or
			target_x >= map.width or target_y >= map.height):
			return
		if not is_blocked(target_x, target_y):
			self.x = target_x
			self.y = target_y

	def move_towards(self, target_x, target_y):

		libtcod.path_compute(pathfinder, self.x, self.y, target_x, target_y)
		if not libtcod.path_is_empty(pathfinder):
			path_x, path_y = libtcod.path_get(pathfinder, 0)
			dx = path_x - self.x
			dy = path_y - self.y
		else:
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

	def draw(self, camera=None):
		draw_x = self.x
		draw_y = self.y
		if camera is not None:
			draw_x -= camera.x
			draw_y -= camera.y
		if map.full_bright or (libtcod.map_is_in_fov(fov_map, self.x, self.y) or
			(self.always_visible and map.grid[self.x][self.y].explored)):
			libtcod.console_set_default_foreground(con, self.color)
			if self.background_color:
				libtcod.console_set_default_background(con, self.background_color)
				libtcod.console_set_background_flag(con, libtcod.BKGND_SET)
			else:
				libtcod.console_set_background_flag(con, libtcod.BKGND_NONE)
			libtcod.console_put_char(con, draw_x, draw_y, self.char)

		if self.flash_char is not None:
			value = math.sin(self.flash_counter)
			if value > 0.0:
				libtcod.console_set_default_foreground(con, self.flash_color)
				libtcod.console_put_char(con, draw_x, draw_y-1, self.flash_char)
			self.flash_counter += 0.5

	def clear(self):
		libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

	def send_to_back(self):
		global objects
		objects.remove(self)
		objects.insert(0, self)

class Interactive:
	def __init__(self, use_function=None, use_on_bump=False):
		self.use_function = use_function
		self.use_on_bump = use_on_bump

	def use(self):
		if self.use_function is not None:
			self.use_function()
		else:
			message("You use the "+self.owner.name)

class InteractiveDoor:
	def __init__(self, closed=True):
		self.closed = closed
		self.use_on_bump = self.closed

	def use(self):
		if self.closed:
			self.closed = False
			message("You open the door")
			self.owner.char = '/'
			self.owner.blocks = False
			self.use_on_bump = False
		else:
			self.closed = True
			message("You close the door")
			self.owner.char = chr(197)
			self.owner.blocks = True
			self.use_on_bump = True

class Actor:
	def __init__(self, hp, defense, power, xp, death_function=None, equipment=None, abilities=None):
		self.max_hp = hp
		self.hp = hp
		self.defense = defense
		self.power = power
		self.xp = xp

		if isinstance(death_function, str):
			self.death_function = globals()[death_function]
		else:
			self.death_function = death_function

		self.equipment = equipment
		if self.equipment:
			self.equipment.owner = self

		self.abilities = abilities
		if self.abilities:
			for ability in abilities:
				ability.owner = self

	def add_ability(self, ability):
		ability.owner = self
		self.abilities.append(ability)

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
			player.actor.xp != self.xp

	def attack(self, target):
		damage = self.get_score('power') - target.actor.get_score('defense')

		if damage > 0:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
			target.actor.take_damage(damage)
		else:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')

	def heal(self, amount):
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp


# A component of Actor
class Equipment:
	def __init__(self, equip_slots=None):
		self.equip_slots = equip_slots
		self.slots = {}

	def equip(self, equippable):
		global inventory

		if equippable.equip_slot not in self.equip_slots:
			if self.owner.owner == player:
				message('You do not have the ' + equippable.equip_slot + ' equip slot.')
			return False

		equippable.actor = self.owner

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

class BasicAI:
	def __init__(self, wander_rect=None):
		self.wander_rect = wander_rect

	def take_turn(self):
		# wander randomly
		dx = libtcod.random_get_int(0, -1, 1)
		dy = libtcod.random_get_int(0, -1, 1)
		if dx == 0 and dy == 0:
			return

		# but stay within my wander area if one is defined
		if self.wander_rect is not None:
			fx = self.owner.x + dx
			fy = self.owner.y + dy
			if fx < self.wander_rect.x1 or fx > self.wander_rect.x2 or fy < self.wander_rect.y1 or fy > self.wander_rect.y2:
				return

		self.owner.move(dx, dy)

class BasicMonster:
	def take_turn(self):
		monster = self.owner
		if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)
			elif player.actor.hp > 0:
				monster.actor.attack(player)

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
		if isinstance(use_function, str):
			self.use_function = globals()[use_function]
		else:
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
				player.actor.equipment.equip(self.equippable)
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
	message(monster.name.capitalize() + ' is dead! You gain ' + str(monster.actor.xp) + ' experience points.', libtcod.orange)
	monster.char = '%'
	monster.blocks = False
	monster.actor = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()


def cast_heal():
	if player.actor.hp == player.actor.max_hp:
		message('You are already at full health', libtcod.red)
		return 'cancelled'

	message('Your wounds start to feel better!', libtcod.light_violet)
	player.actor.heal(HEAL_AMOUNT)


def cast_lightning():
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None:
		message('No enemy is close enough to strike.', libtcod.red)
		return 'cancelled'
	message('A lightning bolt strikes the ' + monster.name + ' with a loud thunder! the damage is ' + str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
	monster.actor.take_damage(LIGHTNING_DAMAGE)	


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
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.actor:
			message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
			obj.actor.take_damage(FIREBALL_DAMAGE)

def closest_monster(max_range):
	closest_enemy = None
	closest_dist = max_range + 1

	for object in objects:
		if object.actor and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
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
	def __init__(self, blocked, block_sight=None, background_color=None, bgColorMap=None, background_character=None, background_character_color=None):
		self.blocked = blocked
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight
		self.explored = False
		self.background_color = background_color
		if bgColorMap is not None:
			random_index = libtcod.random_get_int(0, 0, 8)
			self.background_color = bgColorMap[random_index]
		self.background_character_color = background_character_color
		self.background_character = background_character
		if self.background_character is not None and background_character_color is None:
			self.background_character_color = libtcod.white

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

	def intersect_point(self, x, y):
		return (x >= self.x1 and x <= self.x2 and y >= self.y1 and y <= self.y2)


def next_level():
	global dungeon_level
	message('You take a moment to rest, and record your strength.', libtcod.light_violet)
	player.actor.heal(player.actor.max_hp / 2)

	message('After a rare moment of peace, you descend deeper into the heart of the dungeon...', libtcod.red)
	dungeon_level += 1
	make_map()
	initialize_fov()


def make_map():
	# make_dungeon_map()
	make_town_map()

def make_town_map():
	global map, player, objects, stairs

	objects = [player]
	map = Map(width=150, height=100, filled=False, ambient_light=0.6, full_bright=True)

	noise2d = libtcod.noise_new(2)
	noise_octaves = 8.0
	noise_zoom = 10.0
	grassBGColorMapIndexes = [0, 24, 64]
	grassBGColorMapColors = [libtcod.Color(112, 81, 34), libtcod.Color(47, 92, 41), libtcod.Color(75, 148, 66)]
	grassBGColorMap = libtcod.color_gen_map(grassBGColorMapColors, grassBGColorMapIndexes)	

	grassFGColorMapIndexes = [0, 12]
	grassFGColorMapColors = [libtcod.Color(29, 89, 25), libtcod.Color(53, 200, 44)]

	grassFGColorMap = libtcod.color_gen_map(grassFGColorMapColors, grassFGColorMapIndexes)	
	grassFGCharacterChances = {
		"`": 1,
		"'": 1,
		",": 1,
		'"': 1
	}

	for x in range(map.width):
		for y in range(map.height):
			f = [noise_zoom * x / (2*map.width),
				 noise_zoom * y / (2*map.height)]
			value = libtcod.noise_get_turbulence(noise2d, f, noise_octaves, libtcod.NOISE_WAVELET)
			map.grid[x][y].background_color = grassBGColorMap[int(64 * value)]

	building_min_width = 4
	building_min_height = 4
	building_max_width = 12
	building_max_height = 12
	building_floor_colors = [libtcod.Color(42, 52, 65), libtcod.Color(44, 59, 80)]
	building_wall_colors = [libtcod.Color(53, 71, 95), libtcod.Color(58, 83, 116)]
	min_buildings = 10
	num_buildings = 0
	buildings = []
	while num_buildings < min_buildings:
		bw = libtcod.random_get_int(0, building_min_width, building_max_width)
		bh = libtcod.random_get_int(0, building_min_height, building_max_height)
		bx = libtcod.random_get_int(0, 0, map.width - bw - 1)
		by = libtcod.random_get_int(0, 0, map.height - bh - 1)
		rect = Rect(bx, by, bw, bh)
		checkRect = Rect(rect.x1-1, rect.y1-1, rect.w+2, rect.h+2)
		checkPass = True
		for otherRect in buildings:
			if otherRect.intersect(checkRect):
				checkPass = False
				break;
		if not checkPass:
			continue;

		for x in range(bx, bx+bw):
			for y in range(by, by+bh):
				if x == bx or x == (bx+bw-1) or y == by or y == (by+bh-1):
					map.grid[x][y].blocked = True
					map.grid[x][y].block_sight = True
					map.grid[x][y].background_color = libtcod.color_lerp(building_wall_colors[0], building_wall_colors[1], libtcod.random_get_float(0, 0, 1.0))
				else:
					map.grid[x][y].blocked = False
					map.grid[x][y].block_sight = False
					map.grid[x][y].background_color = libtcod.color_lerp(building_floor_colors[0], building_floor_colors[1], libtcod.random_get_float(0, 0, 1.0))
					if ((x+y) % 2) == 0:
						map.grid[x][y].background_color = map.grid[x][y].background_color * 0.85

		num_doors = libtcod.random_get_int(0, 1, 3)
		for i in range(num_doors):
			rand_dir = libtcod.random_get_int(0, 0, 3)
			if rand_dir == 0 or rand_dir == 2:
				# 0 north, 2 south
				door_x = libtcod.random_get_int(0, bx+1, (bx+bw-2))
				if rand_dir == 0:
					door_y = by
				else:
					door_y = by + bh - 1
			else:
				# 1 east, 3 west
				door_y = libtcod.random_get_int(0, by+1, (by+bh-2))
				if rand_dir == 1:
					door_x = bx + bw - 1
				else:
					door_x = bx
			map.grid[door_x][door_y].blocked = False
			map.grid[door_x][door_y].block_sight = False
			map.grid[door_x][door_y].background_color = building_floor_colors[0]
			door_interactive = InteractiveDoor()
			door = Object(door_x, door_y, chr(197), 'door', libtcod.Color(98, 62, 9), background_color=libtcod.Color(163, 117, 49), blocks=True, interactive=door_interactive)
			objects.append(door)

		npc_x = libtcod.random_get_int(0, rect.x1+1, rect.x2-2)
		npc_y = libtcod.random_get_int(0, rect.y1+1, rect.y2-2)
		wander_rect = Rect(rect.x1+1, rect.y1+1, rect.w-2, rect.h-2)
		npc_ai = BasicAI(wander_rect=wander_rect)
		npc_obj = Object(npc_x, npc_y, chr(2), 'Yizzt', libtcod.light_green, blocks=True, ai=npc_ai)
		npc_obj.flash_character('!', libtcod.yellow)
		objects.append(npc_obj)

		buildings.append(rect)
		num_buildings += 1

	for x in range(map.width):
		for y in range(map.height):
			grass_chance = 5

			if map.grid[x][y].background_character is not None:
				grass_chance += 80

			if libtcod.random_get_int(0, 0, 100) < grass_chance:
				passCheck = True
				for building in buildings:
					if building.intersect_point(x, y):
						passCheck = False
						break
				if passCheck is False:
					continue	

				rand_color = libtcod.random_get_int(0, 0, 12)
				map.grid[x][y].background_character_color = grassFGColorMap[rand_color]
				map.grid[x][y].background_character = random_choice(grassFGCharacterChances)

				if libtcod.random_get_int(0, 0, 100) < 75:
					new_x = x + libtcod.random_get_int(0, -1, 1)
					new_y = y + libtcod.random_get_int(0, -1, 1)

					if new_x < 0:
						new_x = 0
					elif new_x >= map.width:
						new_x = map.width - 1
					if new_y < 0:
						new_y = 0
					elif new_y >= map.height:
						new_y = map.height - 1

					passCheck = True
					for building in buildings:
						if building.intersect_point(new_x, new_y):
							passCheck = False
							break
					if passCheck is False:
						continue										

					rand_color = libtcod.random_get_int(0, 0, 12)
					map.grid[new_x][new_y].background_character_color = grassFGColorMap[rand_color]
					map.grid[new_x][new_y].background_character = random_choice(grassFGCharacterChances)					

	player.x = map.width / 2
	player.y = map.height / 2

	# generate and assign a name for our town
	map.name = libtcod.namegen_generate("Mingos town")

def make_dungeon_map():
	global map, player, objects, stairs

	floorBGColorMapIndexes = [0, 8]
	floorBGColorMapColors = [libtcod.Color(180, 134, 30), libtcod.Color(200, 180, 50)]
	tileBGColorMap = libtcod.color_gen_map(floorBGColorMapColors, floorBGColorMapIndexes)

	wallBGColorMapIndexes = [0, 8]
	wallBGColorMapColors = [libtcod.Color(83, 60, 25), libtcod.Color(112, 81, 34)]
	wallBGColorMap = libtcod.color_gen_map(wallBGColorMapColors, wallBGColorMapIndexes)

	objects = [player]
	map = Map(width=150, height=100, filled=True, ambient_light=0.08, full_bright=False)
	# map = [[ Tile(True, bgColorMap=wallBGColorMap)

	rooms = []
	num_rooms = 0
	for r in range(MAX_ROOMS):
		w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		x = libtcod.random_get_int(0, 0, map.width - w - 1)
		y = libtcod.random_get_int(0, 0, map.height - h - 1)
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

def create_room(room, bgColorMap=None):
	global map
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map.grid[x][y].blocked = False
			map.grid[x][y].block_sight = False
			random_index = libtcod.random_get_int(0, 0, 8)
			if bgColorMap is not None:
				map.grid[x][y].background_color = bgColorMap[random_index]
			else:
				map.grid[x][y].background_color = libtcod.dark_gray

def create_h_tunnel(x1, x2, y, bgColorMap=None):
	global map;
	for x in range(min(x1,x2), max(x1, x2) + 1):
		map.grid[x][y].blocked = False
		map.grid[x][y].block_sight = False
		random_index = libtcod.random_get_int(0, 0, 8)
		if bgColorMap is not None:
			map.grid[x][y].background_color = bgColorMap[random_index]
		else:
			map.grid[x][y].background_color = libtcod.dark_gray

def create_v_tunnel(y1, y2, x, bgColorMap=None):
	global map
	for y in range(min(y1,y2), max (y1,y2) + 1):
		map.grid[x][y].blocked = False
		map.grid[x][y].block_sight = False
		random_index = libtcod.random_get_int(0, 0, 8)
		if bgColorMap is not None:
			map.grid[x][y].background_color = bgColorMap[random_index]
		else:
			map.grid[x][y].background_color = libtcod.dark_gray

def place_objects(room):
	max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6]])
	monster_chances = {}
	monster_chances['orc'] = 80
	monster_chances['troll'] = from_dungeon_level([[15, 3], [30, 5], [60, 7]])

	max_items = from_dungeon_level([[1, 1], [2, 4]])
	item_chances = {}
	item_chances['healing potion'] = 35
	item_chances['lightning scroll'] = from_dungeon_level([[25, 4]])
	item_chances['fireball scroll'] = from_dungeon_level([[25, 6]])
	item_chances['confuse scroll'] = from_dungeon_level([[10, 2]])
	item_chances['helmet'] = 80

	num_monsters = libtcod.random_get_int(0, 0, max_monsters)

	for i in range(num_monsters):
		x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
		y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

		if not is_blocked(x, y):
			choice = random_choice(monster_chances)
			tmpData = monster_data[choice]
			actor_component = Actor(xp=tmpData['xp'], hp=tmpData['hp'], defense=tmpData['defense'], power=tmpData['power'], death_function=tmpData['death_function'])
			ai_component = BasicMonster()
			monster = Object(x, y, tmpData['character'], tmpData['name'], tmpData['character_color'], blocks=True, actor=actor_component, ai=ai_component)
			objects.append(monster)

	num_items = libtcod.random_get_int(0, 0, max_items)

	for i in range(num_items):
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

		if not is_blocked(x, y):
			choice = random_choice(item_chances)
			tmpData = item_data[choice]
			if 'equip_slot' in tmpData:
				equippable_component = Equippable(equip_slot=tmpData['equip_slot'], score_bonuses=tmpData['equip_score_bonuses'])
			else:
				equippable_component = None
			if 'use_function' in tmpData:
				use_function = tmpData['use_function']
			else:
				use_function = None
			item_component = Item(equippable=equippable_component, use_function=use_function)
			item = Object(x, y, tmpData['character'], tmpData['name'], tmpData['character_color'], item=item_component)
			item.always_visible = True
			objects.append(item)
			item.send_to_back()

def is_blocked(x, y):
	if map.grid[x][y].blocked:
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
	global fov_map, fov_recompute, camera
	global color_dark_wall, color_dark_ground, color_light_wall, color_light_ground
	if fov_recompute:
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, int(TORCH_RADIUS), FOV_LIGHT_WALLS, libtcod.FOV_PERMISSIVE_8)

	camera.update_position(player.x, player.y)
	libtcod.console_clear(con)

	for y in range(camera.y, (camera.y + camera.height)):
		if y < 0 or y >= map.height:
			continue
		draw_y = y - camera.y
		for x in range(camera.x, (camera.x + camera.width)):
			if x < 0 or x >= map.width:
				continue
			draw_x = x - camera.x
			visible = libtcod.map_is_in_fov(fov_map, x, y)
			wall = map.grid[x][y].block_sight
			if not visible and not map.full_bright:
				if map.grid[x][y].explored:
					if wall:
						libtcod.console_set_char_background(con, draw_x, draw_y, color_dark_wall, libtcod.BKGND_SET)
					else:
						libtcod.console_set_char_background(con, draw_x, draw_y, color_dark_ground, libtcod.BKGND_SET)
			else:
				if wall:
					use_color = color_light_wall
				else:
					use_color = color_light_ground
				if map.grid[x][y].background_color:
					use_color = map.grid[x][y].background_color

				final_value = map.ambient_light
				radius = TORCH_RADIUS * 1.0
				squared_radius = radius * radius;

				if abs(player.x - x) <= radius and abs(player.y - y) <= radius:
					squared_distance = float(x - player.x) * (x - player.x) + (y - player.y) * (y - player.y)
					if squared_distance <= squared_radius:
						#light_color = TORCH_COLOR# * 0.4
						coef1 = 1.0 / (1.0 + (squared_distance/20))
						coef2 = coef1 - 1.0 / (1.0+squared_radius)
						coef3 = coef2 / (1.0 - (1.0/(1.0+squared_radius)))
						final_value = coef3
						if final_value < map.ambient_light:
							final_value = map.ambient_light
						elif final_value > 1.0:
							final_value = 1.0

				final_color = use_color * final_value

				libtcod.console_set_char_background(con, draw_x, draw_y, final_color, libtcod.BKGND_SET)
				map.grid[x][y].explored = True

				if map.grid[x][y].background_character is not None:
					libtcod.console_set_default_foreground(con, map.grid[x][y].background_character_color * final_value)
					libtcod.console_put_char(con, draw_x, draw_y, map.grid[x][y].background_character, libtcod.BKGND_NONE)

	for object in objects:
		if object != player:
			if camera.is_visible(object.x, object.y):
				object.draw(camera=camera)
	player.draw(camera=camera)

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

	render_bar(1, 1, BAR_WIDTH, 'HP', player.actor.hp, player.actor.max_hp,
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
	(x, y) = (mouse.cx, mouse.cy)
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
	names = ', '.join(names)
	return names.capitalize()

def menu(header, options, width):
	if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')
	libtcod.console_set_alignment(0, libtcod.LEFT)
	libtcod.console_set_alignment(con, libtcod.LEFT)
	header_height = libtcod.console_get_height_rect(con, 0, 0, width-2, SCREEN_HEIGHT, header)
	if header == '':
		header_height = 0
	height = len(options) + 2 + header_height
	if header_height > 0:
		height = height + 1
	window = libtcod.console_new(width, height)
	libtcod.console_set_default_background(window, MENU_BACKGROUND_COLOR)
	libtcod.console_set_default_foreground(window, libtcod.Color(219, 209, 158))
	libtcod.console_print_frame(window, 0, 0, width, height, clear=True, flag=libtcod.BKGND_SET)
	libtcod.console_set_default_foreground(window, MENU_TEXT_COLOR)
	
	if header is not '':
		libtcod.console_set_alignment(window, libtcod.CENTER)
		libtcod.console_set_default_background(window, MENU_HEADER_BACKGROUND_COLOR)
		libtcod.console_set_default_foreground(window, MENU_HEADER_TEXT_COLOR)
		libtcod.console_rect(window, 1, 1, width-2, 1, True, libtcod.BKGND_SET)
		libtcod.console_print_rect(window, width/2, 1, width-2, height, header)
		libtcod.console_set_alignment(window, libtcod.LEFT)

	y = header_height + 1
	letter_index = ord('a')
	libtcod.console_set_default_foreground(window, MENU_TEXT_COLOR)
	libtcod.console_set_background_flag(window, libtcod.BKGND_NONE)
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		libtcod.console_print(window, 1, y, text)
		y += 1
		letter_index += 1

	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

	libtcod.console_flush()
	breakLoop = False
	while not breakLoop:
		key = libtcod.console_wait_for_keypress(True)

		if key.vk == libtcod.KEY_ENTER and key.lalt:
			libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

		breakLoop = True

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
			if obj.x == x and obj.y == y and obj.actor and obj != player:
				return obj

def abilities_menu(header):
	if len(player.actor.abilities) == 0:
		options = ['You have no abilities.']
	else:
		options = [ability.name for ability in player.actor.abilities]

	index = menu(header, options, ABILITIES_WIDTH)

	if index is None or len(player.actor.abilities) == 0: return None
	return player.actor.abilities[index]

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
	if len(player.actor.equipment.slots) == 0:
		options =['You have nothing equipped']
	else:
		options = []
		keys = []
		for slot_name in player.actor.equipment.slots:
			equippable = player.actor.equipment.slots[slot_name]
			options.append("("+slot_name+") "+equippable.owner.owner.name)
			keys.append(slot_name)

	index = menu(header, options, EQUIPMENT_WIDTH)

	if index is None or len(player.actor.equipment.slots) == 0: return None
	if keys is None:
		return player.actor.equipment.slots[index]
	else:
		return player.actor.equipment.slots[keys[index]]

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
			if game_state is 'playing':
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

def create_player():
	global player, key, mouse
	# con = libtcod.console_new(map_width, map_height)

	noise2d = libtcod.noise_new(2)
	noise_octaves = 8.0
	noise_zoom = 7.5
	noise_zoom2 = 10.0
	bg_color = libtcod.Color(23, 28, 36)
	noise_color = libtcod.Color(102, 108, 163)
	noise_dx = 0.0
	noise_dy = 0.0

	name_prompt_con = libtcod.console_new(30, 6)
	name_input = ''
	name_prompt(name_prompt_con, name_input, width=30)


	while True:
		libtcod.console_set_default_background(panel, bg_color)
		libtcod.console_clear(panel)	

		noise_dy += 0.01

		for y in range(SCREEN_HEIGHT):
			for x in range(SCREEN_WIDTH):
				f = [(noise_zoom * x / (2*SCREEN_WIDTH) + noise_dx), (noise_zoom * (y+(y*(y/(SCREEN_WIDTH/2)))) / (2*SCREEN_HEIGHT) + noise_dy)]
				value = libtcod.noise_get_fbm(noise2d, f, noise_octaves, libtcod.NOISE_PERLIN)
				color_index = (value + 1.0) / 2.0
				color_index = color_index * float(y) / (SCREEN_HEIGHT / 2)
				col = libtcod.color_lerp(bg_color, noise_color, color_index)

				libtcod.console_set_char_background(panel, x, y, col, libtcod.BKGND_SET)

		libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)	
		libtcod.console_blit(name_prompt_con, 0, 0, 30, 6, 0, (SCREEN_WIDTH/2)-(30/2), (SCREEN_HEIGHT/2)-(6/2), 1.0, 0.7)
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)

		if key.vk == libtcod.KEY_ESCAPE:
			break
		elif key.vk == libtcod.KEY_BACKSPACE:
			name_input = name_input[:-1]
			name_prompt(name_prompt_con, name_input, width=30)
		elif key.vk == libtcod.KEY_CHAR:
			name_input += chr(key.c)
			name_prompt(name_prompt_con, name_input, width=30)
		elif key.vk == libtcod.KEY_ENTER:
			return name_input

def name_prompt(window, name_input, width=30):
	header = "Enter A Name"
	name_input += "_"
	header_height = 3
	height = 3 + header_height

	# render bg and frame
	libtcod.console_set_default_background(window, MENU_BACKGROUND_COLOR)
	libtcod.console_set_default_foreground(window, libtcod.Color(219, 209, 158))
	libtcod.console_print_frame(window, 0, 0, width, height, clear=True, flag=libtcod.BKGND_SET)
	libtcod.console_set_default_foreground(window, MENU_TEXT_COLOR)

	# render header
	libtcod.console_set_alignment(window, libtcod.CENTER)
	libtcod.console_set_default_background(window, MENU_HEADER_BACKGROUND_COLOR)
	libtcod.console_set_default_foreground(window, MENU_HEADER_TEXT_COLOR)
	libtcod.console_rect(window, 1, 1, width-2, 1, True, libtcod.BKGND_SET)
	libtcod.console_print_rect(window, width/2, 1, width-2, height, header)
	libtcod.console_set_alignment(window, libtcod.LEFT)

	draw_x = 2
	draw_y = header_height

	# render text box
	libtcod.console_set_default_background(window, libtcod.black)
	libtcod.console_rect(window, draw_x, draw_y, width-4, 1, True, libtcod.BKGND_SET)
	libtcod.console_print_ex(window, draw_x, draw_y, libtcod.BKGND_NONE, libtcod.LEFT, name_input)

def message_log():
	global key, mouse
	header = "Message Log"
	header_height = 3
	width = SCREEN_WIDTH - 10
	height = (SCREEN_HEIGHT - 10)

	window = libtcod.console_new(width, height)	

	# render bg and frame
	libtcod.console_set_default_background(window, MENU_BACKGROUND_COLOR)
	libtcod.console_set_default_foreground(window, libtcod.Color(219, 209, 158))
	libtcod.console_print_frame(window, 0, 0, width, height, clear=True, flag=libtcod.BKGND_SET)
	libtcod.console_set_default_foreground(window, MENU_TEXT_COLOR)

	# render header
	libtcod.console_set_alignment(window, libtcod.CENTER)
	libtcod.console_set_default_background(window, MENU_HEADER_BACKGROUND_COLOR)
	libtcod.console_set_default_foreground(window, MENU_HEADER_TEXT_COLOR)
	libtcod.console_rect(window, 1, 1, width-2, 1, True, libtcod.BKGND_SET)
	libtcod.console_print_rect(window, width/2, 1, width-2, height, header)
	libtcod.console_set_alignment(window, libtcod.LEFT)

	x = 2
	y = 3

	# TODO: Display actual message log contents

	while True:
		render_all()
		libtcod.console_blit(window, 0, 0, width, height, 0, 5, 5, 1.0, 0.7)
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)

		if key.vk == libtcod.KEY_ESCAPE:
			return

def new_game():
	global player, inventory, game_msgs, game_state, dungeon_level, pathfinder, camera, con

	player_name = create_player()
	if player_name is None:
		game_state = 'cancelled'
		return

	player_equip_slots = ["head", "torso"]
	player_equipment_component = Equipment(equip_slots=player_equip_slots)
	tmpData = ability_data['lightning strike']
	use_function = None
	if 'use_function' in tmpData:
		use_function = tmpData['use_function']
	lightning_ability = Ability(tmpData['name'], use_function=use_function)
	player_abilities = [lightning_ability]
	player_actor_component = Actor(xp=0, hp=100, defense=1, power=4, death_function=player_death, equipment=player_equipment_component, abilities=player_abilities)
	player = Object(0, 0, '@', player_name, libtcod.white, blocks=True, actor=player_actor_component)
	player.level = 1

	dungeon_level = 1
	game_msgs = []
	inventory = []
	game_state = 'playing'

	camera = Camera(0, 0, width=SCREEN_WIDTH, height=43)
	camera.update_position(player.x, player.y)
	con = libtcod.console_new(camera.width, camera.height)	
	make_town_map()
	initialize_fov()
	if pathfinder is not None:
		libtcod.path_delete(pathfinder)
	pathfinder = libtcod.path_new_using_map(fov_map)

	message('Welcome stranger! Prepare to perish in the Tombs of the Ancient Kings.', libtcod.red)


def initialize_fov():
	global fov_recompute, fov_map
	fov_recompute = True
	fov_map = libtcod.map_new(map.width, map.height)
	for y in range(map.height):
		for x in range(map.width):
			libtcod.map_set_properties(fov_map, x, y, not map.grid[x][y].block_sight, not map.grid[x][y].blocked)
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

	# load monster data
	monsterStruct = libtcod.parser_new_struct(parser, 'monster')
	libtcod.struct_add_property(monsterStruct, 'name', libtcod.TYPE_STRING, True)
	libtcod.struct_add_property(monsterStruct, 'character', libtcod.TYPE_CHAR, True)
	libtcod.struct_add_property(monsterStruct, 'character_color', libtcod.TYPE_COLOR, True)
	libtcod.struct_add_property(monsterStruct, 'xp', libtcod.TYPE_INT, True)
	libtcod.struct_add_property(monsterStruct, 'hp', libtcod.TYPE_INT, True)
	libtcod.struct_add_property(monsterStruct, 'defense', libtcod.TYPE_INT, True)
	libtcod.struct_add_property(monsterStruct, 'power', libtcod.TYPE_INT, True)
	libtcod.struct_add_property(monsterStruct, 'death_function', libtcod.TYPE_STRING, True)
	libtcod.parser_run(parser, os.path.join('data', 'monster_data.cfg'), MonsterDataListener())

	# load item data
	itemStruct = libtcod.parser_new_struct(parser, 'item')
	libtcod.struct_add_property(itemStruct, 'name', libtcod.TYPE_STRING, True)
	libtcod.struct_add_property(itemStruct, 'character', libtcod.TYPE_CHAR, True)
	libtcod.struct_add_property(itemStruct, 'character_color', libtcod.TYPE_COLOR, True)
	libtcod.struct_add_property(itemStruct, 'use_function', libtcod.TYPE_STRING, False)
	libtcod.struct_add_property(itemStruct, 'equip_slot', libtcod.TYPE_STRING, False)
	libtcod.struct_add_list_property(itemStruct, 'equip_score_bonuses', libtcod.TYPE_STRING, False)
	libtcod.parser_run(parser, os.path.join('data', 'item_data.cfg'), ItemDataListener())

	# load abilities data
	abilityStruct = libtcod.parser_new_struct(parser, 'ability')
	libtcod.struct_add_property(abilityStruct, 'name', libtcod.TYPE_STRING, True)
	libtcod.struct_add_property(abilityStruct, 'use_function', libtcod.TYPE_STRING, False)
	libtcod.parser_run(parser, os.path.join('data', 'ability_data.cfg'), AbilityDataListener())

	# load name generation data
	for file in os.listdir('data/namegen'):
		if file.find('.cfg') > 0:
			libtcod.namegen_parse(os.path.join('data', 'namegen', file))
	namegen_sets = libtcod.namegen_get_sets()

class MonsterDataListener:
    def new_struct(self, struct, name):
    	global monster_data
        self.current_name = name
        monster_data[name] = {}
        return True

    def new_flag(self, name):
    	global monster_data
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
    	global monster_data
        print 'Monster data parser error : ', msg
        if self.current_name is not None:
        	del monster_data[self.current_name]
        	self.current_name = None
        return True

class ItemDataListener:
    def new_struct(self, struct, name):
    	global item_data
        self.current_name = name
        item_data[name] = {}
        return True

    def new_flag(self, name):
    	global item_data
        item_data[self.current_name][name] = True
        return True

    def new_property(self,name, typ, value):
		global item_data
		if name == "equip_score_bonuses":
			item_data[self.current_name][name] = {}
			for i in value:
				parts = i.split(":")
				item_data[self.current_name][name][parts[0]] = int(parts[1])
		else:
			item_data[self.current_name][name] = value
		return True

    def end_struct(self, struct, name):
    	self.current_name = None
        return True

    def error(self,msg):
    	global item_data
        print 'Item data parser error : ', msg
        if self.current_name is not None:
        	del item_data[self.current_name]
        	self.current_name = None
        return True

class AbilityDataListener:
    def new_struct(self, struct, name):
    	global ability_data
        self.current_name = name
        ability_data[name] = {}
        return True

    def new_flag(self, name):
    	global ability_data
        ability_data[self.current_name][name] = True
        return True

    def new_property(self,name, typ, value):
		global ability_data
		ability_data[self.current_name][name] = value
		return True

    def end_struct(self, struct, name):
    	self.current_name = None
        return True

    def error(self,msg):
    	global ability_data
        print 'Ability data parser error : ', msg
        if self.current_name is not None:
        	del ability_data[self.current_name]
        	self.current_name = None
        return True

class Camera:
	def __init__(self, x=0, y=0, width=None, height=None, track_threshold=10):
		if width is None:
			width = SCREEN_WIDTH
		if height is None:
			height = SCREEN_HEIGHT
		self.width = width
		self.height = height
		self.x = x
		self.y = y
		self.track_threshold = track_threshold

	def update_position(self, target_x, target_y):
		center_x = target_x - (self.width / 2)
		center_y = target_y - (self.height / 2)

		if abs(self.x - center_x) <= self.track_threshold and abs(self.y - center_y) <= self.track_threshold:
			return

		self.x = center_x
		self.y = center_y

		if self.x < 0:
			self.x = 0
		elif (self.x + self.width) > map.width:
			self.x = map.width - self.width
		if self.y < 0:
			self.y = 0
		elif (self.y + self.height) > map.height:
			self.y = map.height - self.height

	def is_visible(self, position_x, position_y):
		return (self.x <= position_x and (self.x + self.width) >= position_x and
				self.y <= position_y and (self.y + self.height) >= position_y)

libtcod.console_set_custom_font("terminal8x12_gs_ro.png", libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Seven Trials', False)
libtcod.sys_set_fps(LIMIT_FPS)
key=libtcod.Key()
mouse=libtcod.Mouse()

panel = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

pathfinder = None
camera = None
con = libtcod.console_new(5, 5)

ability_data = {}
item_data = {}
monster_data = {}
namegen_sets = None
load_data()

main_menu()