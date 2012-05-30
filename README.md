SevenTrials
===========

Roguelike game made with python and libtcod.

Story
-----
The Gods have selected you to be a champion of the mortal realm, tasked with ridding the world of a vile corruption. You must travel the towns and villages of the land, performing in each seven tasks. Once this is done, the Gods, appeased with your devotion, will spare that area from its otherwise inevitable destruction.

**Most recent changes:**
* fov_map and pathfinder now stored on Map objects
* Fixed a major bug which caused a hard crash on entering a new map and having a hostile enemy try to path to you
* Map is no longer being rendered every frame, only when it is marked dirty (huge increase in performance)
* Mouse can now be used to set movement paths for the player (warning: player does not yet stop on hostile sightings)

**Todo:** *(in no particular order)*
* Allow user to select a single skill during character creation
* Mark map cells as not being walkable when inhabited by an actor, and mark the cell back to walkable when the actor moves 
* Item stacking
* Move item and monster placement chances into data files, will have to use a delimited string (no support for lists of lists)
* Menu should allow use of arrow keys
* Action menus (have multiple 'actions' in horizontal line at top.. you select an action from these to perform on the menu option you select)
* Time Management; Actors queue an action. Once enough world time has passed, the action occurs
	* timePasses()
	* retrieve action from queue with lowest amount of time left on it
	* action occurs and is processed
	* time action had remaining is subtracted from all queued actions
	* wash, rinse, repeat
* Improve lighting support; should be able to define an arbitrary number of lights, maybe attach them to objects
	* Lights should use fov
* NPC's occaisionally wander into their doorways in the town map
* Masteries
	* Each level of a mastery awards score bonuses and/or an ability
* Generalized function for drawing a framed, optionally titled window to a given console
* Effects (enchantments, curses, etc.)
* Only display the ! flashing symbol if an npc is a quest giver
* Tiles containing items should have some kind of background color highlight
* Should be able to scroll through the message log
* Instead of wandering randomly, townspeople should pick a target spot in their defined wander area, walk to it, stand idle for a random for amount of time, and then repeat this process.
* Hostile alert effect should not be assigned, but should be automatic based on an Actors reactions and feelings toward the player
* The Map class should probably have a get_path function that returns a list of tuples representing the coordinates for each step of the computed path
* Create a Debug panel that can be toggled on and off
* auto explore

# player should stop following path if hostile creature comes into fov
# corpses continue to flash as hostile even after death
# objects and effects need to be on their own console layer, and rendered differently.. as is, rendering an updated effect would mean needing to re-render the entire map.. not cool
	# move global con into Camera
	# Map console
	# Objects console
	# Effects console