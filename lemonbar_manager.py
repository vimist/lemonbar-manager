import io
import logging
import subprocess as sp
from select import select
import time


LOGGER = logging.getLogger(__name__)


class Module:
    def __init__(self):
        """The base class each module should inherit from.

        You should override either `self.readable` or `self.wait_time`.

        If you want to wait for a file handle to become readable, set
        `self.readable` to said file handle.

        If you want to update regularly (time based), set `self.wait_time` to
        the interval (in seconds) to waid between updates.
        """
        self.readable = None
        self.wait_time = 86400  # Default, 1 day
        self.last_update = 0
        self.cache = None

    def handle_event(self, event):
        """This will be called when events are fired.

        This recieved events from ALL modules, so you need to check the `event`
        parameter to ensure it's the event you want to handle.

        Parameters:
            event (str): The name of the event that was fired.
        """

    def output(self):
        """The main output method of the module.

        This is what will be output onto the bar.

        Returns:
            str: The data to send to the bar.
        """
        return ''


class Manager:
    def __init__(self, args, modules):
        """Run lemonbar with the specified modules.

        The process is launched with the input piped and with the correct
        encoding automatically set.

        Parameters:
            args (list): The full command used to launch lemonbar.
            modules (list): A list of generators.

        Returns:
            subprocess.Popen: An object representing the lemonbar process.
        """
        LOGGER.debug('Starting Process')
        self._lemonbar = sp.Popen(
            args, stdin=sp.PIPE, stdout=sp.PIPE, encoding='UTF-8')

        self._modules = modules

    def __enter__(self):
        LOGGER.debug('Entering context manager')
        return self

    def __exit__(self, *args, **kwargs):
        LOGGER.debug('Killing process and exiting context manager')
        self._lemonbar.kill()

    def _wait(self, rlist, wait_time):
        """Wait until an object in `rlist` is readable or `wait_time` is up.

        Parameter:
            rlist (list): A list of readables for `select` to monitor.
            wait_time (float): The maximum amount of time to wait.

        Returns:
            list: A list of readables that are ready to read.
        """
        early_execution = False

        LOGGER.info('Waiting {} seconds'.format(wait_time))

        if len(rlist) > 0:
            readables, _, _ = select(rlist, [], [], wait_time)
            LOGGER.info('{} readables ready for reading'.format(len(readables)))
        else:
            LOGGER.info('There are no readables to wait for')
            readables = []
            time.sleep(wait_time)

        return readables

    def _run_modules(self, readables):
        """Run the modules ready for updating.

        Parameters:
            readables (list): A list of readables returned by `select` that are
                ready for reading.
        """
        LOGGER.debug('Updating modules')

        now = time.time()
        for module in self._modules:
            time_delta = now - module.last_update

            if module.readable in readables:
                LOGGER.info('Updating readable module "{}"'.format(module))
                value = module.output()
                module.last_update = now  # Update the last updated time
            elif module.wait_time and (
                    module.last_update == 0 or time_delta > module.wait_time):
                LOGGER.info('Updating time based module "{}"'.format(module))
                value = module.output()
                module.last_update = now  # Update the last updated time
            else:
                LOGGER.info('Using cached value for module "{}"'.format(module))
                value = module.cache

            LOGGER.debug('Sending "{}" to lemonbar'.format(value))
            self._lemonbar.stdin.write(value)
            module.cache = value  # Update the cached value

        self._lemonbar.stdin.write('\n')
        self._lemonbar.stdin.flush()

    def _calculate_wait(self, last_loop_time, interrupted):
        min_wait_time = min([
            module.wait_time for module in self._modules if module.wait_time])

        LOGGER.debug('Minimum wait time is {}'.format(min_wait_time))

        invalidated = any([
            module.last_update == 0 for module in self._modules])

        if invalidated:
            wait_time = 0
        elif interrupted:
            wait_time = min_wait_time - last_loop_time
        else:
            wait_time = min_wait_time

        wait_time = max(0, wait_time)

        LOGGER.debug('Wait time is {}'.format(wait_time))
        return wait_time

    def loop(self):
        """The main program loop.

        Invoke this method when you want to start updating the bar.
        """
        event_pipe = self._lemonbar.stdout

        start_time = time.time()
        end_time = start_time
        interrupted = False  # Whether the loop was interrupted by a readable

        # TODO: Determine whether this should be inside the loop. For my use,
        # it's fine here, but do people want to swap out readables at will?
        rlist = [
            module.readable for module in self._modules if module.readable]
        rlist.append(event_pipe)  # Wait for events coming from lemonbar too

        while True:
            last_loop_time = end_time - start_time
            start_time = time.time()

            wait_time = self._calculate_wait(last_loop_time, interrupted)

            readables = self._wait(rlist, wait_time)
            interrupted = len(readables) > 0

            self._run_modules(readables)

            if event_pipe in readables:
                event = event_pipe.readline().rstrip()
                LOGGER.info('Handling event "{}"'.format(event))
                for module in self._modules:
                    module.handle_event(event)

            end_time = time.time()
