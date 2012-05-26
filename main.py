import libtcodpy as libtcod
import math
import os
import pprint
import random
import shelve
import string
import textwrap
import uuid

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
MENU_SELECTED_COLOR = libtcod.black
MENU_SELECTED_BACKGROUND_COLOR = libtcod.white
MENU_HEADER_TEXT_COLOR = libtcod.white
MENU_HEADER_BACKGROUND_COLOR = libtcod.darker_sepia
MENU_FRAME_COLOR = libtcod.Color(219, 209, 158)
ABILITIES_WIDTH = 50
CHARACTER_SCREEN_WIDTH = 30
INVENTORY_WIDTH = 50
LEVEL_SCREEN_WIDTH = 40
EQUIPMENT_WIDTH = 50

POSITIVE_BONUS_TEXT_COLOR = libtcod.Color(58, 228, 64)
NEGATIVE_BONUS_TEXT_COLOR = libtcod.Color(255, 12, 16)

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

DIR_NORTH = 0
DIR_EAST = 1
DIR_SOUTH = 2
DIR_WEST = 3

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
				for object in map.objects:
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
				for stairs_obj in map.stairs:
					if stairs_obj.x == player.x and stairs_obj.y == player.y:
						stairs_obj.use()

			if key_char == 'c':
				level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
				libtcod.console_flush()
				msgbox('Character Information\n'+
					'\nLevel: ' + str(player.level) +
					'\nExperience: ' + str(player.actor.xp) +
					'\nExperience to level up: ' + str(level_up_xp) +
					'\n\nMaximum HP: ' + str(player.actor.max_hp) + 
					'\nAttack: ' + str(player.actor.get_rating('power')) + 
					'\nDefense: ' + str(player.actor.get_rating('defense')), CHARACTER_SCREEN_WIDTH)

			if key_char == 'M':
				message_log()

			return 'didnt-take-turn'

def player_move_or_attack(dx, dy):
	global fov_recompute

	x = player.x + dx
	y = player.y + dy

	attack_target = None
	interact_target = None
	for object in map.objects:
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

class World:
	def __init__(self):
		self.maps = []

	def add_map(self, new_map):
		#self.maps[new_map.uid] = new_map
		self.maps.append(new_map)

class Map:
	def __init__(self, width, height, name="Unknown", filled=True, ambient_light=0.0, full_bright=False, uid=None, objects=None):
		self.uid = uid
		if self.uid is None:
			self.uid = str(uuid.uuid4())
		self.width = width
		self.height = height
		self.ambient_light = ambient_light
		self.full_bright = full_bright
		self.name = name
		self.stairs = []
		self.objects = []
		self.grid = [[ Tile(filled)
			for y in range(height) ]
				for x in range(width) ]

class Stairs:
	def __init__(self, x, y, obj_index=None, target_map_index=None):
		self.x = x
		self.y = y
		self.obj_index = obj_index
		self.target_map_index = target_map_index
		self.target_stair_index = 0

	def use(self):
		global world, map, player
		if self.target_map_index is None:
			current_map_index = world.maps.index(map)
			my_stair_index = map.stairs.index(self)
			make_dungeon_map()
			world.add_map(map)
			self.target_map_index = len(world.maps) - 1
			stair_obj = map.stairs[self.target_stair_index]
			stair_obj.target_map_index = current_map_index
			stair_obj.target_stair_index = my_stair_index
		else:
			map = world.maps[self.target_map_index]
		stair_obj = map.stairs[self.target_stair_index]
		player.x = stair_obj.x
		player.y = stair_obj.y
		initialize_fov()		

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

		self.do_flash = False
		self.do_hostile_bg = False

	def flash_character(self, char=None, color=None):
		if char is None:
			self.do_flash = False
			return
		self.do_flash = True
		self.flash_char = char
		self.flash_color = color
		self.flash_counter = 0.0
		self.flash_rate = 0.5

	def hostile_bg_effect(self, toggle):
		if toggle is False:
			self.do_hostile_bg = False
			return
		self.do_hostile_bg = True
		self.hostile_bg_color = libtcod.Color(202, 42, 33)
		self.hostile_bg_counter = 0.0
		self.hostile_bg_rate = 0.5

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
			elif self.do_hostile_bg is True:
				value = (math.sin(self.hostile_bg_counter) + 1.0) / 2
				libtcod.console_set_default_background(con, libtcod.color_lerp(map.grid[self.x][self.y].background_color, self.hostile_bg_color, value))
				libtcod.console_set_background_flag(con, libtcod.BKGND_SET)
				self.hostile_bg_counter += self.hostile_bg_rate
				if self.hostile_bg_counter > (math.pi * 2):
					self.hostile_bg_counter -= (math.pi * 2)
			else:
				libtcod.console_set_background_flag(con, libtcod.BKGND_NONE)
			libtcod.console_put_char(con, draw_x, draw_y, self.char)

		if self.do_flash is True:
			value = math.sin(self.flash_counter)
			if value > 0.0:
				libtcod.console_set_default_foreground(con, self.flash_color)
				libtcod.console_put_char(con, draw_x, draw_y-1, self.flash_char)
			self.flash_counter += self.flash_rate
			if self.flash_counter > (math.pi * 2):
				self.flash_counter -= (math.pi * 2)

	def clear(self):
		libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

	def send_to_back(self):
		map.objects.remove(self)
		map.objects.insert(0, self)

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
	def __init__(self, hp, defense, power, xp, death_function=None, equipment=None, abilities=[]):
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

	def add_rating(self, rating_name, amount):
		if hasattr(self, rating_name):
			rating = getattr(self, rating_name)
			if rating is None:
				rating = 0
			setattr(self, rating_name, rating + amount)
		else:
			setattr(self, rating_name, amount)

	def get_rating(self, rating_name):
		rating = 0
		if hasattr(self, rating_name):
			rating = getattr(self, rating_name)

		# TODO: this is also where you would want to factor in bonuses from equipment and effects and such
		# Factor in bonuses from equipment
		if self.equipment:
			for slot_name in self.equipment.slots:
				equippable = self.equipment.slots[slot_name]
				eq_bonus = equippable.rating_bonuses.get(rating_name)
				if eq_bonus is not None:
					rating += eq_bonus

		return rating

	def take_damage(self, damage):
		if damage > 0:
			self.hp -= damage

		if self.hp <= 0:
			self.owner.do_flash = False
			function = self.death_function
			if function is not None:
				function(self.owner)

		if self.owner != player:
			player.actor.xp != self.xp

	def attack(self, target):
		damage = self.get_rating('power') - target.actor.get_rating('defense')

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
			if self.owner in map.objects:
				map.objects.remove(self.owner)
			message('You picked up a ' + self.owner.name + '!', libtcod.green)
			return True

	def drop(self):
		map.objects.append(self.owner)
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
	def __init__(self, equip_slot=None, rating_bonuses=None):
		self.equip_slot = equip_slot
		self.rating_bonuses = rating_bonuses

def player_death(player):
	global game_state
	message('You died!', libtcod.red)
	game_state = 'dead'
	player.char = '%'
	player.color = libtcod.dark_red

def player_add_skill(skillObj):
	global player
	hasSkillObj = player.skills.get(skillObj['name'], None)
	if hasSkillObj is not None:
		player.skills[skillObj['name']] += 1
	else:
		player.skills[skillObj['name']] = 1

	# fetch the skillRank which matches our new level in this skill
	rankObj = skillObj['ranks'].get(player.skills[skillObj['name']], None)
	if rankObj is not None:
		# apply any rating bonuses attached to the skillRank
		rating_bonuses = rankObj.get('rating_bonuses', None)
		if rating_bonuses is not None and len(rating_bonuses) > 0:
			for bonusObj in rating_bonuses:
				player.actor.add_rating(bonusObj['rating'], bonusObj['bonus'])
		# add any new abilities attached to the skillRank
		abilities = rankObj.get('gives_abilities', None)
		if abilities is not None and len(abilities) > 0:
			for abilityObj in abilities:
				tmpData = ability_data[abilityObj['name']]
				ability = Ability(tmpData['name'], use_function=tmpData['use_function'])
				player.actor.add_ability(ability)

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

	for obj in map.objects:
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.actor:
			message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
			obj.actor.take_damage(FIREBALL_DAMAGE)

def closest_monster(max_range):
	closest_enemy = None
	closest_dist = max_range + 1

	for object in map.objects:
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

def random_direction():
	dirs = [DIR_NORTH, DIR_EAST, DIR_SOUTH, DIR_WEST]
	chances = [1,1,1,1]
	return dirs[random_choice_index(chances)]

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
	make_dungeon_map()
	# make_town_map()

class Building:
	def __init__(self, worksite=None, rooms=None, floorplan=None):
		self.worksite = worksite
		self.rooms = rooms
		self.floorplan = floorplan

	def random_get_floor(self):
		while True:
			x = libtcod.random_get_int(0, self.worksite.x1, self.worksite.x2)
			y = libtcod.random_get_int(0, self.worksite.y1, self.worksite.y2)
			if self.floorplan[x-self.worksite.x1][y-self.worksite.y1] == 2:
				return (x,y)

def make_building(buildings, wall_colors, floor_colors):
	global map
	worksite_width_min = 10
	worksite_width_max = 20
	worksite_height_min = 10
	worksite_height_max = 20
	room_width_min = 3
	room_width_max = 9
	room_height_min = 3
	room_height_max = 9
	worksite_rect = None
	while worksite_rect is None:
		worksite_width = libtcod.random_get_int(0, worksite_width_min, worksite_width_max)
		worksite_height = libtcod.random_get_int(0, worksite_height_min, worksite_height_max)
		worksite_x1 = libtcod.random_get_int(0, 1, (map.width-2-worksite_width))
		worksite_y1 = libtcod.random_get_int(0, 1, (map.height-2-worksite_height))
		checkRect = Rect(worksite_x1-1, worksite_y1-1, worksite_width+2, worksite_height+2)
		checkPass = True
		for otherBuilding in buildings:
			if otherBuilding.worksite.intersect(checkRect):
				checkPass = False
				break;
		if not checkPass:
			continue

		worksite = Rect(worksite_x1, worksite_y1, worksite_width, worksite_height)

		rooms = []
		new_room = make_room_in_area(worksite, room_width_min, room_width_max, room_height_min, room_height_max)
		rooms.append(new_room)

		min_num_rooms = libtcod.random_get_int(0, 1, 4)
		num_rooms = 0
		while num_rooms < min_num_rooms:
			new_room = None
			while new_room is None:
				new_room = make_room_in_area(worksite, room_width_min, room_width_max, room_height_min, room_height_max)
				checkRect = Rect(new_room.x1+1, new_room.y1+1, new_room.w-2, new_room.h-2)
				for room in rooms:
					if not room.intersect(checkRect):
						new_room = None
						break
			#rooms.append(Rect(new_room.x1, new_room.y1, new_room.w, new_room.h))
			rooms.append(new_room)
			num_rooms += 1

		floorplan = [[ 0
			for y in range(worksite_height+1) ]
				for x in range(worksite_width+1)]

		# build walls for each room
		for room in rooms:
			for x in range(room.x1, room.x2+1):
				for y in range(room.y1, room.y2+1):
					if x == room.x1 or x == room.x2 or y == room.y1 or y == room.y2:
						map.grid[x][y].blocked = True
						map.grid[x][y].block_sight = True
						map.grid[x][y].background_color = libtcod.color_lerp(wall_colors[0], wall_colors[1], libtcod.random_get_float(0, 0, 1.0))
						floorplan[x-worksite.x1][y-worksite.y1] = 1

		# build floor for each room
		for room in rooms:
			for x in range(room.x1, room.x2+1):
				for y in range(room.y1, room.y2+1):
					if x == room.x1 or x == room.x2 or y == room.y1 or y == room.y2:
						continue
					map.grid[x][y].blocked = False
					map.grid[x][y].block_sight = False
					map.grid[x][y].background_color = libtcod.color_lerp(floor_colors[0], floor_colors[1], libtcod.random_get_float(0, 0, 1.0))
					floorplan[x-worksite.x1][y-worksite.y1] = 2

		# assign wall characters according to neighbors
		door_sites = []
		for y in range(worksite_height+1):
			for x in range(worksite_width+1):
				if floorplan[x][y] == 1:
					char = '+'
					if y > 0 and y < worksite_height and floorplan[x][y-1] == 1 and floorplan[x][y+1] == 1:
						char = chr(179)
						door_sites.append( (x,y) )
					elif x > 0 and x < worksite_width and floorplan[x-1][y] == 1 and floorplan[x+1][y] == 1:
						char = chr(196)
						door_sites.append( (x,y) )
					elif x < worksite_width and y < worksite_height and floorplan[x+1][y] == 1 and floorplan[x][y+1] == 1:
						char = chr(218)
					elif x > 0 and y < worksite_height and floorplan[x-1][y] == 1 and floorplan[x][y+1] == 1:
						char = chr(191)
					elif x > 0 and y > 0 and floorplan[x-1][y] == 1 and floorplan[x][y-1] == 1:
						char = chr(217)
					elif x < worksite_width and y > 0 and floorplan[x][y-1] == 1 and floorplan[x+1][y] == 1:
						char = chr(192)

					draw_x = worksite.x1+x
					draw_y = worksite.y1+y	

					map.grid[draw_x][draw_y].background_character = char
					map.grid[draw_x][draw_y].background_character_color = libtcod.yellow

		# make doors by choosing randomly from our list of eligible cells
		random.shuffle(door_sites)
		max_num_doors = min(libtcod.random_get_int(0, 1, 3), len(door_sites))
		num_doors = 0
		doors = []
		while num_doors < max_num_doors:
			if len(door_sites) == 0:
				break
			(door_x, door_y) = door_sites.pop()
			door_x += worksite.x1
			door_y += worksite.y1
			checkPass = True
			for (old_x, old_y) in doors:
				if abs(old_x - door_x) <= 1 and abs(old_y - door_y) <= 1:
					checkPass = False
					break
			if checkPass is False:
				continue
			map.grid[door_x][door_y].blocked = False
			map.grid[door_x][door_y].block_sight = False
			map.grid[door_x][door_y].background_color = floor_colors[0]
			door_interactive = InteractiveDoor()
			door = Object(door_x, door_y, chr(197), 'door', libtcod.Color(98, 62, 9), background_color=libtcod.Color(163, 117, 49), blocks=True, interactive=door_interactive)
			map.objects.append(door)					
			doors.append( (door_x, door_y) )
			num_doors += 1

		break

	return Building(worksite=worksite, rooms=rooms, floorplan=floorplan)


def make_room_in_area(area, min_width, max_width, min_height, max_height):
	width = libtcod.random_get_int(0, min_width, max_width)
	height = libtcod.random_get_int(0, min_height, max_height)
	x = libtcod.random_get_int(0, area.x1, area.x2-width)
	y = libtcod.random_get_int(0, area.y1, area.y2-height)
	return Rect(x, y, width, height)

def make_town_map():
	global map, player

	map = Map(width=150, height=100, filled=False, ambient_light=0.6, full_bright=True)
	map.objects = [player]

	noise2d = libtcod.noise_new(2)
	noise_octaves = 8.0
	noise_zoom = 10.0
	grassBGColorMapIndexes = [0, 64]
	grassBGColorMapColors = [libtcod.Color(47, 92, 41), libtcod.Color(75, 148, 66)]
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

	building_min_width = 8
	building_min_height = 8
	building_max_width = 18
	building_max_height = 12
	building_floor_colors = [libtcod.Color(42, 52, 65), libtcod.Color(44, 59, 80)]
	building_wall_colors = [libtcod.Color(53, 71, 95), libtcod.Color(58, 83, 116)]
	min_buildings = 10
	num_buildings = 0
	buildings = []
	while num_buildings < min_buildings:
		building = make_building(buildings, building_wall_colors, building_floor_colors)
		buildings.append(building)
		num_buildings += 1

		# place an npc
		(npc_x, npc_y) = building.random_get_floor()
		npc_ai = BasicAI(wander_rect=building.worksite)
		npc_obj = Object(npc_x, npc_y, chr(2), 'Yizzt', libtcod.light_green, blocks=True, ai=npc_ai)
		npc_obj.flash_character('!', libtcod.yellow)
		map.objects.append(npc_obj)

	# place a few dungeon entrances
	min_num_entrances = libtcod.random_get_int(0, 3, 7)
	num_entrances = 0
	entrances = []
	while num_entrances < min_num_entrances:
		rand_x = libtcod.random_get_int(0, 1, map.width-7)
		rand_y = libtcod.random_get_int(0, 1, map.height-7)
		entrance_rect = Rect(rand_x, rand_y, 5, 5)
		checkPass = True
		for building in buildings:
			if building.worksite.intersect(entrance_rect):
				checkPass = False
				break
		if checkPass is False:
			continue
		map_add_dungeon_entrace(rand_x, rand_y)
		entrances.append(entrance_rect)
		num_entrances += 1

	# place grass
	for x in range(map.width):
		for y in range(map.height):
			grass_chance = 5

			if map.grid[x][y].background_character is not None:
				grass_chance += 80

			if libtcod.random_get_int(0, 0, 100) < grass_chance:
				passCheck = True
				for building in buildings:
					if building.worksite.intersect_point(x, y):
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
						if building.worksite.intersect_point(new_x, new_y):
							passCheck = False
							break
					if passCheck is False:
						continue										

					rand_color = libtcod.random_get_int(0, 0, 12)
					map.grid[new_x][new_y].background_character_color = grassFGColorMap[rand_color]
					map.grid[new_x][new_y].background_character = random_choice(grassFGCharacterChances)					

	# place the player
	player.x = map.width / 2
	player.y = map.height / 2

	# generate and assign a name for our town
	map.name = libtcod.namegen_generate("Mingos town")

def map_add_dungeon_entrace(pos_x, pos_y):
	global map
	rand_dir = random_direction()

	cell_queue = []

	if rand_dir is DIR_SOUTH:
		cell_queue = [(pos_x, pos_y), (pos_x+1, pos_y), (pos_x+2, pos_y), (pos_x, pos_y+1), (pos_x+2, pos_y+1), (pos_x, pos_y+2), (pos_x+2, pos_y+2)]
	elif rand_dir is DIR_NORTH:
		cell_queue = [(pos_x, pos_y), (pos_x+2, pos_y), (pos_x, pos_y+1), (pos_x+2, pos_y+1), (pos_x, pos_y+2), (pos_x+1, pos_y+2), (pos_x+2, pos_y+2)]
	elif rand_dir is DIR_WEST:
		cell_queue = [(pos_x, pos_y), (pos_x, pos_y+2), (pos_x+1, pos_y), (pos_x+1, pos_y+2), (pos_x+2, pos_y), (pos_x+2, pos_y+1), (pos_x+2, pos_y+2)]
	elif rand_dir is DIR_EAST:
		cell_queue = [(pos_x, pos_y), (pos_x, pos_y+1), (pos_x, pos_y+2), (pos_x+1, pos_y), (pos_x+1, pos_y+2), (pos_x+2, pos_y), (pos_x+2, pos_y+2)]

	stair_x = pos_x + 1
	stair_y = pos_y + 1
	fill_char = chr(176)
	fill_char = chr(240)

	for (cell_x, cell_y) in cell_queue:
		map.grid[cell_x][cell_y].background_character = fill_char
		map.grid[cell_x][cell_y].background_color = libtcod.Color(133, 133, 133)
		map.grid[cell_x][cell_y].background_character_color = libtcod.Color(83, 83, 83)
		map.grid[cell_x][cell_y].blocked = True

	stairs_obj = Object(stair_x, stair_y, '>', 'stairs', libtcod.white, always_visible=True)
	map.objects.append(stairs_obj)
	map.stairs.append(Stairs(stair_x, stair_y))	

def make_dungeon_map():
	global map, player

	floorBGColorMapIndexes = [0, 8]
	floorBGColorMapColors = [libtcod.Color(180, 134, 30), libtcod.Color(200, 180, 50)]
	tileBGColorMap = libtcod.color_gen_map(floorBGColorMapColors, floorBGColorMapIndexes)

	wallBGColorMapIndexes = [0, 8]
	wallBGColorMapColors = [libtcod.Color(83, 60, 25), libtcod.Color(112, 81, 34)]
	wallBGColorMap = libtcod.color_gen_map(wallBGColorMapColors, wallBGColorMapIndexes)
	
	map = Map(width=150, height=100, filled=True, ambient_light=0.08, full_bright=False)
	map.objects = [player]

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

	stairs_obj = Object(new_x, new_y, '>', 'stairs', libtcod.white, always_visible=True)
	map.objects.append(stairs_obj)
	map.stairs.append(Stairs(new_x, new_y))


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

	# Place monsters
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
			monster.hostile_bg_effect(True)
			map.objects.append(monster)

	# Place items
	num_items = libtcod.random_get_int(0, 0, max_items)
	for i in range(num_items):
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

		if not is_blocked(x, y):
			choice = random_choice(item_chances)
			tmpData = item_data[choice]
			if 'equip_slot' in tmpData:
				equippable_component = Equippable(equip_slot=tmpData['equip_slot'], rating_bonuses=tmpData['equip_rating_bonuses'])
			else:
				equippable_component = None
			if 'use_function' in tmpData:
				use_function = tmpData['use_function']
			else:
				use_function = None
			item_component = Item(equippable=equippable_component, use_function=use_function)
			item = Object(x, y, tmpData['character'], tmpData['name'], tmpData['character_color'], item=item_component)
			item.always_visible = True
			map.objects.append(item)
			item.send_to_back()

def is_blocked(x, y):
	if map.grid[x][y].blocked:
		return True

	for object in map.objects:
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
	libtcod.console_set_default_background(con, libtcod.black)
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

	for object in map.objects:
		if object != player:
			if camera.is_visible(object.x, object.y):
				object.draw(camera=camera)
	player.draw(camera=camera)

	libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

	libtcod.console_set_default_background(panel, libtcod.black)
	libtcod.console_clear(panel)

	# TODO: Why is this being rendered every frame?
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
	libtcod.console_print(panel, 1, 3, map.name)

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
	global game_msgs, log_msgs
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

	for line in new_msg_lines:
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]
		game_msgs.append( (line, color) )
		log_msgs.append( (line, color) )

def get_names_under_mouse():
	(x, y) = (mouse.cx, mouse.cy)
	names = [obj.name for obj in map.objects
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

	(x, y) = draw_menu_panel(window, width, height, header_text=header)

	letter_index = ord('a')
	libtcod.console_set_default_foreground(window, MENU_TEXT_COLOR)
	libtcod.console_set_background_flag(window, libtcod.BKGND_NONE)
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		libtcod.console_print(window, x, y, text)
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

		for obj in map.objects:
			if obj.x == x and obj.y == y and obj.actor and obj != player:
				return obj

def abilities_menu(header):
	if player.actor.abilities is None or len(player.actor.abilities) == 0:
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
	# img = libtcod.image_load('menu_background.png')

	while not libtcod.console_is_window_closed():
		# libtcod.image_blit_2x(img, 0, 0, 0)

		libtcod.console_set_default_foreground(0, libtcod.light_yellow)
		libtcod.console_set_background_flag(0, libtcod.BKGND_SET)
		libtcod.console_set_default_background(0, libtcod.darker_sepia)
		libtcod.console_clear(0)
		libtcod.console_set_background_flag(0, libtcod.BKGND_NONE)
		libtcod.console_set_alignment(0, libtcod.CENTER)
		libtcod.console_print(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, 'SEVEN TRIALS')
		libtcod.console_print(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, 'By nefD')

		choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 30)

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

	create_state = 'name'

	name_prompt_con = libtcod.console_new(30, 6)
	name_input = ''
	name_prompt(name_prompt_con, name_input, width=30)

	skill_prompt_con = libtcod.console_new(80, 40)
	skillPrompt = SkillPrompt(con=skill_prompt_con)

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
		if create_state == "name":
			libtcod.console_blit(name_prompt_con, 0, 0, 30, 6, 0, (SCREEN_WIDTH/2)-(30/2), (SCREEN_HEIGHT/2)-(6/2), 1.0, 0.7)
		elif create_state == "skill":
			#skillPrompt.render(skill_prompt_con)
			libtcod.console_blit(skillPrompt.con, 0, 0, 80, 40, 0, (SCREEN_WIDTH/2)-(80/2), (SCREEN_HEIGHT/2)-(40/2), 1.0, 0.7)
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)

		skillPrompt.update()

		if key.vk == libtcod.KEY_ESCAPE:
			player.name = None
			break
		elif key.vk == libtcod.KEY_BACKSPACE:
			if create_state == "name":
				name_input = name_input[:-1]
				name_prompt(name_prompt_con, name_input, width=30)
		elif key.vk == libtcod.KEY_CHAR:
			if create_state == "name":
				name_input += chr(key.c)
				name_prompt(name_prompt_con, name_input, width=30)
		elif key.vk == libtcod.KEY_ENTER:
			if create_state == 'name':
				create_state = 'skill'
				player.name = name_input
				#skill_prompt(skill_prompt_con, skill_highlight_index)
				skillPrompt.render()
			elif create_state == 'skill':
				player_add_skill(skillPrompt.get_highlighted())
				return

def name_prompt(window, name_input, width=30):
	header = "Enter A Name"
	name_input += "_"
	header_height = 3
	height = 3 + header_height

	(draw_x, draw_y) = draw_menu_panel(window, width, 6, header_text=header)

	# render text box
	libtcod.console_set_default_background(window, libtcod.black)
	libtcod.console_rect(window, draw_x, draw_y, width-4, 1, True, libtcod.BKGND_SET)
	libtcod.console_print_ex(window, draw_x, draw_y, libtcod.BKGND_NONE, libtcod.LEFT, name_input)

class SkillPrompt:
	def __init__(self, width=80, height=40, header_text="Select A Skill", con=None):
		self.width = width
		self.height = height
		self.header_text = header_text
		self.highlight_index = 0
		self.con = con
		self.skill_obj = skill_data.get(skill_data.keys()[self.highlight_index])
		self.rank_obj = self.skill_obj['ranks'][1]

	def update(self):
		global key, mouse

		if key.vk == libtcod.KEY_UP:
			self.highlight_index -= 1
			if self.highlight_index < 0:
				self.highlight_index = len(skill_data) - 1
			self.skill_obj = skill_data.get(skill_data.keys()[self.highlight_index])
			self.rank_obj = self.skill_obj['ranks'][1]
			self.render()
		elif key.vk == libtcod.KEY_DOWN:
			self.highlight_index += 1
			if self.highlight_index >= len(skill_data):
				self.highlight_index = 0
			self.skill_obj = skill_data.get(skill_data.keys()[self.highlight_index])
			self.rank_obj = self.skill_obj['ranks'][1]
			self.render()

	def get_highlighted(self):
		list_index = 0
		for skill_name in skill_data:
			if self.highlight_index == list_index:
				return self.skill_obj
			list_index += 1

	def render(self):
		(draw_x, draw_y) = draw_menu_panel(self.con, self.width, self.height, self.header_text)

		# render list of skills
		list_width = 20
		list_x = draw_x
		list_y = draw_y
		list_index = 0
		libtcod.console_set_alignment(self.con, libtcod.LEFT)
		libtcod.console_set_default_foreground(self.con, MENU_TEXT_COLOR)
		for skill_name in skill_data:
			if self.highlight_index == list_index:
				libtcod.console_set_default_background(self.con, MENU_SELECTED_BACKGROUND_COLOR)
				libtcod.console_rect(self.con, list_x, list_y, list_width, 1, True, libtcod.BKGND_SET)
				libtcod.console_set_default_foreground(self.con, MENU_SELECTED_COLOR)
				libtcod.console_print(self.con, list_x, list_y, skill_name.capitalize())
				libtcod.console_set_default_foreground(self.con, MENU_TEXT_COLOR)
			else:
				libtcod.console_print(self.con, list_x, list_y, skill_name.capitalize())
			list_y += 1
			list_index += 1

		# render next rank of highlighted skill
		info_x = draw_x + list_width + 2
		info_w = self.width - 3 - list_width
		info_y = draw_y
		libtcod.console_set_default_foreground(self.con, MENU_TEXT_COLOR)
		libtcod.console_print(self.con, info_x, info_y, "Skill: " + self.skill_obj.get('name', '(Missing skill name!)'))
		info_y += 2
		libtcod.console_print(self.con, info_x, info_y, "Next Rank: Level 1 - " + self.rank_obj['name'])
		info_y += 2

		# output description
		rank_desc = self.rank_obj.get('description', None)
		if rank_desc is not None:
			desc_height = libtcod.console_get_height_rect(self.con, info_x, info_y, info_w, self.height-3-info_y, rank_desc)
			libtcod.console_print_rect(self.con, info_x, info_y, info_w, self.height-3-info_y, rank_desc)
			info_y += desc_height + 1

		# output rating bonuses
		rating_bonuses = self.rank_obj.get('rating_bonuses', None)
		if rating_bonuses is not None and len(rating_bonuses) > 0:
			libtcod.console_print(self.con, info_x, info_y, "Rating Bonuses:")
			info_y += 1
			for rating in rating_bonuses:
				bonus_str = ""
				str_color = MENU_TEXT_COLOR
				if rating['bonus'] > 0:
					str_color = POSITIVE_BONUS_TEXT_COLOR
					bonus_str += "+"
				elif rating['bonus'] < 0:
					str_color = NEGATIVE_BONUS_TEXT_COLOR
					bonus_str += "-"
				bonus_str += str(rating['bonus']) + " " + rating['rating'].capitalize()
				libtcod.console_set_default_foreground(self.con, str_color)
				libtcod.console_print(self.con, info_x + 4, info_y, bonus_str)
				info_y += 1

		# output new abilities
		gives_abilities = self.rank_obj.get("gives_abilities", None)
		if gives_abilities is not None and len(gives_abilities) > 0:
			info_y += 1
			libtcod.console_set_default_foreground(self.con, MENU_TEXT_COLOR)
			if len(gives_abilities) > 1:
				libtcod.console_print(self.con, info_x, info_y, "New Ability:")
			else:
				libtcod.console_print(self.con, info_x, info_y, "New Abilities:")
			info_y += 1
			for ability in gives_abilities:
				libtcod.console_set_default_foreground(self.con, libtcod.yellow)
				libtcod.console_print(self.con, info_x + 4, info_y, string.capwords(ability['name']))
				info_y += 1

def skill_prompt(window, highlight_index):
	header = "Select a Skill"
	header_height = 3
	width = 80
	height = 3 + header_height
	height = 40 + header_height
	height = 40

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

	list_width = 20
	draw_x = 2
	draw_y = header_height
	list_x = draw_x
	list_y = draw_y
	list_index = 0

	# render list of skills
	libtcod.console_set_alignment(window, libtcod.LEFT)
	libtcod.console_set_default_foreground(window, MENU_TEXT_COLOR)
	for skill_name in skill_data:
		if highlight_index == list_index:
			libtcod.console_set_default_background(window, MENU_SELECTED_BACKGROUND_COLOR)
			libtcod.console_rect(window, list_x, list_y, list_width, 1, True, libtcod.BKGND_SET)
			libtcod.console_set_default_foreground(window, MENU_SELECTED_COLOR)
			libtcod.console_print(window, list_x, list_y, skill_name.capitalize())
			libtcod.console_set_default_foreground(window, MENU_TEXT_COLOR)
		else:
			libtcod.console_print(window, list_x, list_y, skill_name.capitalize())
		list_y += 1
		list_index += 1

def draw_menu_panel(window, width, height, header_text=None):
	# render background and frame
	libtcod.console_set_default_background(window, MENU_BACKGROUND_COLOR)
	libtcod.console_set_default_foreground(window, MENU_FRAME_COLOR)
	libtcod.console_print_frame(window, 0, 0, width, height, clear=True, flag=libtcod.BKGND_SET)
	libtcod.console_set_default_foreground(window, MENU_TEXT_COLOR)
	if header_text is None or header_text == "":
		return (2, 1)

	# reder header text
	libtcod.console_set_alignment(window, libtcod.CENTER)
	libtcod.console_set_default_background(window, MENU_HEADER_BACKGROUND_COLOR)
	libtcod.console_set_default_foreground(window, MENU_HEADER_TEXT_COLOR)
	libtcod.console_rect(window, 1, 1, width-2, 1, True, libtcod.BKGND_SET)
	libtcod.console_print_rect(window, width/2, 1, width-2, height, header_text)
	libtcod.console_set_alignment(window, libtcod.LEFT)
	return (2, 3)

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
	max_lines = (height - 3) - y

	# TODO: Display actual message log contents
	start_msg = 0
	end_msg = start_msg + max_lines
	if end_msg > len(log_msgs):
		end_msg = len(log_msgs)
	for (line, color) in log_msgs[start_msg:end_msg]:
		libtcod.console_set_default_foreground(window, color)
		libtcod.console_print(window, x, y, line)
		y += 1

	while True:
		render_all()
		libtcod.console_blit(window, 0, 0, width, height, 0, 5, 5, 1.0, 0.7)
		libtcod.console_flush()
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)

		if key.vk == libtcod.KEY_ESCAPE:
			return

def new_game():
	global player, world, inventory, game_msgs, log_msgs, game_state, dungeon_level, pathfinder, camera, con

	player_equip_slots = ["head", "torso"]
	player_equipment_component = Equipment(equip_slots=player_equip_slots)
	#tmpData = ability_data['lightning strike']
	#use_function = None
	#if 'use_function' in tmpData:
	#	use_function = tmpData['use_function']
	#lightning_ability = Ability(tmpData['name'], use_function=use_function)
	#player_abilities = []
	player_actor_component = Actor(xp=0, hp=100, defense=1, power=4, death_function=player_death, equipment=player_equipment_component)
	player = Object(0, 0, '@', 'Unknown', libtcod.white, blocks=True, actor=player_actor_component)
	player.level = 1
	player.skills = {}
	create_player()
	if player.name is None:
		game_state = 'cancelled'
		return


	world = World()
	dungeon_level = 1
	log_msgs = []
	game_msgs = []
	inventory = []
	game_state = 'playing'

	camera = Camera(0, 0, width=SCREEN_WIDTH, height=43)
	con = libtcod.console_new(camera.width, camera.height)	
	make_town_map()
	world.add_map(map)
	camera.update_position(player.x, player.y)

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

		for object in map.objects:
			object.clear()

		player_action = handle_keys()
		if player_action == 'exit':
			break

		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in map.objects:
				if object.ai:
					object.ai.take_turn()

	save_game()	


def save_game():
	file = shelve.open('savegame', 'n')
	file['world'] = world
	file['map_index'] = world.maps.index(map)
	file['camera'] = camera
	file['player_index'] = map.objects.index(player)
	file['dungeon_level'] = dungeon_level
	file['inventory'] = inventory
	file['game_msgs'] = game_msgs
	file['log_msgs'] = log_msgs
	file['game_state'] = game_state
	file.close()

def load_game():
	global map, world, camera, player, inventory, game_msgs, log_msgs, game_state, dungeon_level, con, pathfinder, fov_map

	file = shelve.open('savegame', 'r')
	world = file['world']
	map = world.maps[file['map_index']]
	camera = file['camera']
	player = map.objects[file['player_index']]
	dungeon_level = file['dungeon_level']
	inventory = file['inventory']
	game_msgs = file['game_msgs']
	log_msgs = file['log_msgs']
	game_state = file['game_state']
	file.close()

	con = libtcod.console_new(camera.width, camera.height)
	initialize_fov()
	if pathfinder is not None:
		libtcod.path_delete(pathfinder)
	pathfinder = libtcod.path_new_using_map(fov_map)

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
	libtcod.struct_add_list_property(itemStruct, 'equip_rating_bonuses', libtcod.TYPE_STRING, False)
	libtcod.parser_run(parser, os.path.join('data', 'item_data.cfg'), ItemDataListener())

	# load abilities data
	abilityStruct = libtcod.parser_new_struct(parser, 'ability')
	libtcod.struct_add_property(abilityStruct, 'name', libtcod.TYPE_STRING, True)
	libtcod.struct_add_property(abilityStruct, 'use_function', libtcod.TYPE_STRING, False)
	libtcod.parser_run(parser, os.path.join('data', 'ability_data.cfg'), AbilityDataListener())

	# load skills data
	ratingBonusStruct = libtcod.parser_new_struct(parser, 'ratingBonus')
	libtcod.struct_add_property(ratingBonusStruct, 'bonus', libtcod.TYPE_INT, True)

	giveAbilityStruct = libtcod.parser_new_struct(parser, 'giveAbility')

	skillRankStruct = libtcod.parser_new_struct(parser, 'skillRank')
	libtcod.struct_add_property(skillRankStruct, 'rankLevel', libtcod.TYPE_INT, True)
	libtcod.struct_add_property(skillRankStruct, 'description', libtcod.TYPE_STRING, False)
	libtcod.struct_add_structure(skillRankStruct, ratingBonusStruct)
	libtcod.struct_add_structure(skillRankStruct, giveAbilityStruct)

	skillStruct = libtcod.parser_new_struct(parser, 'skill')
	libtcod.struct_add_property(skillStruct, 'description', libtcod.TYPE_STRING, False)
	libtcod.struct_add_structure(skillStruct, skillRankStruct)
	libtcod.parser_run(parser, os.path.join('data', 'skill_data.cfg'), SkillDataListener())

	libtcod.parser_delete(parser)

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
		if name == "equip_rating_bonuses":
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

class SkillDataListener:
	def __init__(self):
		self.skill_obj = None
		self.rank_obj = None
		self.ratingBonus_obj = None
		self.ability_obj = None

	def new_struct(self, struct, name):
		struct_name = libtcod.struct_get_name(struct)
		if struct_name == "skill":
			self.skill_obj = { 
				'name': name,
				'ranks': {}
			}
		elif struct_name == "skillRank":
			self.rank_obj = {
				'name': name,
				'rating_bonuses': [],
				'gives_abilities': []
			}
		elif struct_name == "ratingBonus":
			self.ratingBonus_obj = {
				'rating': name
			}
		elif struct_name == "giveAbility":
			self.ability_obj = {
				'name': name
			}
		return True

	def new_flag(self, name):
		#ability_data[self.current_name][name] = True
		return True

	def new_property(self, name, typ, value):
		if self.ratingBonus_obj is not None:
			self.ratingBonus_obj[name] = value
		elif self.ability_obj is not None:
			self.ability_obj[name] = value
		elif self.rank_obj is not None:
			self.rank_obj[name] = value
		else:
			self.skill_obj[name] = value
		return True

	def end_struct(self, struct, name):
		struct_name = libtcod.struct_get_name(struct)
		if struct_name == "ratingBonus":
			self.rank_obj['rating_bonuses'].append(self.ratingBonus_obj)
			self.ratingBonus_obj = None
		elif struct_name == "giveAbility":
			self.rank_obj['gives_abilities'].append(self.ability_obj)
			self.ability_obj = None
		elif struct_name == "skillRank":
			self.skill_obj['ranks'][self.rank_obj['rankLevel']] = self.rank_obj
			self.rank_obj = None
		elif struct_name == "skill":
			skill_data[self.skill_obj['name']] = self.skill_obj;
		return True

	def error(self,msg):
		print "skill data struct error: " + msg
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

		if abs(self.x - center_x) > self.track_threshold:
			self.x = center_x

		if abs(self.y - center_y) > self.track_threshold:
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
skill_data = {}
namegen_sets = None
load_data()
main_menu()