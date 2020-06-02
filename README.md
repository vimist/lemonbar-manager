Lemonbar Manager
================

A couple of simple Python classes to manage reading from and writing to
[Lemonbar][lemonbar].

Modules can be either, **time** based (i.e. update every N seconds), **select**
based (i.e. update when a file descriptor (or anything that [select][select] can
handle) becomes readable) or **event** based (i.e. when something on the bar is
clicked).

**This allows us to do away with polling in a lot of cases!**

No modules included, they're simple to write, so get to it ;)

Installation
------------

Install with:
`pip3 install lemonbar-manager`

A Basic Bar
-----------

```python
from lemonbar_manager import Manager, Module

# Create a simple "Hello World" module
class HelloWorld(Module):
	def output(self):
		"""Output a constant string to the bar.
		"""
		return 'Hello World'

# Define the modules to put on the bar (in order)
modules = (
	HelloWorld(),
)

# The command used to launch lemonbar
command = (
	'lemonbar',
	'-b',  # Dock at the bottom of the screen
	'-g', 'x25',  # Set the height of the bar
	'-u', '2',  # Set the underline thickness
)

# Run the bar with the given modules
with Manager(command, modules) as mgr:
	mgr.loop()
```

Take a look through the [examples directory][examples] for a more in-depth look
at what's possible.

[select]: https://docs.python.org/3.7/library/select.html#select.select
[lemonbar]: https://github.com/LemonBoy/bar
[examples]: examples
