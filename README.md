SevenTrials
===========

Roguelike game made with python and libtcod.

Story
-----
The Gods have selected you to be a champion of the mortal realm, tasked with ridding the world of a vile corruption. You must travel the towns and villages of the land, performing in each seven tasks. Once this is done, the Gods, appeased with your devotion, will spare that area from its otherwise inevitable destruction.


**Most recent changes:**
* Now placing stair features in buildings in the town
* Stairs in the town are now usable

**Todo:** *(in no particular order)*
* Seperate code into multiple files
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
* Message log
* Masteries
	* Each level of a mastery awards score bonuses and/or an ability
* Generalized function for drawing a framed, optionally titled window to a given console
* Effects (enchantments, curses, etc.)
* Only display the ! flashing symbol if an npc is a quest giver
* Tiles containing items should have some kind of background color highlight
* Stair objects should dictate where the user goes when they are traversed