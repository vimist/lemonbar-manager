from collections import OrderedDict
import re
import subprocess as sp
from time import time, strftime

from lemonbar_manager import Module, Manager


class Const(Module):
    def __init__(self, value):
        """A constant value.

        Parameters:
            value (str): The value to output to the bar.
        """
        super().__init__()
        self._value = value

    def output(self):
        return self._value


class Launcher(Module):
    def __init__(self, label, command):
        """A simple clickable element to launch a program.

        Parameters:
            label (str): The string to write to the bar.
            command (list): The command to execute (with Popen)
        """
        super().__init__()

        self._label = label
        self._command = command
        self._event_name = '{}_click'.format(self._label)

    def output(self):
        return '%{A:' + self._event_name + ':}' + self._label + '%{A}'

    def handle_event(self, event):
        """Handle out click event.

        Parameters:
            event (str): The event name.
        """
        if event != self._event_name:  # Ignore the event if it's not ours
            return

        sp.Popen(self._command)


class Clock(Module):
    def __init__(self):
        """A simple clock.

        The clock can be clicked and will switch to the date for a period of
        time.
        """
        super().__init__()
        self.wait_time = 60  # How often to update this module
        self._toggled_at = 0  # When the clock was toggled

    def output(self):
        # If the clock has been toggled for more than a certain period of time
        if self._toggled_at and time() - self._toggled_at > 5:
            self._toggled_at = None  # Automatically toggle back to the clock

        if self._toggled_at:
            return '%{A:toggle_clock:}\uf0ee ' + strftime('%d/%m/%Y') + '%{A}'
        else:
            return '%{A:toggle_clock:}\uf150 ' + strftime('%H:%M') + '%{A}'

    def handle_event(self, event):
        if event != 'toggle_clock':
            return

        self._toggled_at = None if self._toggled_at else time()
        self.last_update = 0  # Invalidate the cache


class Volume(Module):
    def __init__(self, device):
        """A simple ALSA volume control.

        Parameters:
            device (str): The name of the ALSA device to control.
        """
        super().__init__()
        self._device = device

        self._regex = re.compile(r'(\d{1,3})%')  # For parsing ALSA output
        self._increments = 20  # The resolution of our volume control

        self._current_level = self._get_level()

    def _parse_amixer(self, data):
        """Parse the output from the amixer command.

        Parameters::
            data (str): The output from amixer.

        Returns:
            int: An integer between 0 and 100 (inclusive) representing the
                volume level.
        """
        levels = [int(level) for level in re.findall(self._regex, data)]
        return sum(levels) / (len(levels) * 100)

    def _get_level(self):
        """Get the current volume level for the device.

        Returns:
            int: An integer between 0 and 100 (inclusive) representing the
                volume level.
        """
        process = sp.run(
            ['amixer', 'get', self._device],
            stdout=sp.PIPE,
            encoding='UTF-8')

        return self._parse_amixer(process.stdout)

    def _set_level(self, percent):
        """Set the volume level for the device.

        Parameters:
            percent (int): An integer between 0 and 100 (inclusive).
        """
        process = sp.run(
            ['amixer', 'set', 'Master', '{:.0f}%'.format(percent)],
            stdout=sp.PIPE,
            encoding='UTF-8')

    def output(self):
        output = ['\uF57F']
        for i in range(self._increments + 1):
            output.append('%{{A:set_volume_{}_{}:}}'.format(self._device, i))

            if round(self._increments*self._current_level) >= i:
                output.append('--')
            else:
                output.append('  ')

            output.append('%{A}')

        output.append(' \uF57E')

        return ''.join(output)

    def handle_event(self, event):
        if not event.startswith('set_volume_{}_'.format(self._device)):
            return

        level = int(event[event.rindex('_')+1:])
        percent = (level / self._increments) * 100

        self._set_level(percent)
        self._current_level = percent
        self.last_update = 0  # Invalidate the cache to force a redraw


class BSPWM(Module):
    def __init__(self, monitor):
        """A BSPWM desktop indicator.

        Parameters:
            monitor (str): The name of the monitor to show the desktop status
                for.
        """
        super().__init__()

        # Subscribe to BSPWM events and make the `Manager` class wait on it's
        # stdout before updating the module.
        self._subscription_process = sp.Popen(
            ['bspc', 'subscribe'], stdout=sp.PIPE, encoding='UTF-8')
        self.readables = [self._subscription_process.stdout]

        self._monitor = monitor

        # The different format strings use to display the stauts of the desktops
        self._formats = {
            'O': '%{{+u}}%{{+o}}  {}  %{{-u}}%{{-o}}',  # Focused, Occupied
            'F': '%{{+u}}%{{+o}}  {}  %{{-u}}%{{-o}}',  # Focused, Free
            'U': '%{{B#CF6A4C}}  {}  %{{B-}}',     # Focused, Urgent

            'o': '%{{B#222}}  {}  %{{B-}}',  # Unfocused, Occupied
            'f': '  {}  ',                   # Unfocused, Free
            'u': '%{{B#F00}}  {}  %{{B-}}',  # Unfocused, Urgent
        }

    def _parse_event(self, event):
        """Parse a BSPWM event.

        Parameters:
            event (str): The BSPWM event.

        Returns:
            OrderedDict: Keys are desktop names, values are the status.
        """
        desktops = OrderedDict()

        event = event.lstrip('W')
        items = event.split(':')

        on_monitor = False

        for item in items:
            k, v = item[0], item[1:]

            if k in 'Mm':
                on_monitor = v == self._monitor
            elif on_monitor and k in 'OoFfUu':
                desktops[v] = k

        return desktops

    def output(self):
        event = self.readables[0].readline().strip()

        desktops = self._parse_event(event)

        output = []
        for desktop, state in desktops.items():
            output.append('%{{A:focus_desktop_{}:}}'.format(desktop))
            output.append(self._formats[state].format(desktop))
            output.append('%{A}')

        return ''.join(output)

    def handle_event(self, event):
        if not event.startswith('focus_desktop_'):
            return

        desktop = event[event.rindex('_')+1:]
        sp.Popen(['bspc', 'desktop', '--focus', desktop + '.local'])


# Define the modules to put on the bar (in order)
modules = (
    Const('%{Sf}%{l}'),
    BSPWM('DVI-D-0'),
    Const('%{r}'),
    Clock(),
    Const(' '),

    Const('%{Sl}%{l}'),
    BSPWM('DP-1'),
    Const('%{c}'),
    Volume('Master'),
    Const('%{r}'),
    Launcher(' \uF425 ', ['shutdown', '-h', 'now'])
)


# Lemonbar command
command = (
    'lemonbar',
    '-b',
    '-a', '40',
    '-g', 'x25',
    '-B', '#111111',
    '-F', '#B2B2B2',
    '-U', '#D8AD4C',
    '-u', '2',
    '-o', '1',  # Push Noto down 1px
    '-o', '-1', # Pull Material Desicn Icons up 1px
    '-f', 'Noto Sans Display,Noto Sans Disp ExtLt',
    '-f', 'Material Design Icons'
)

# Run the bar with the given modules
with Manager(command, modules) as mgr:
    mgr.loop()
