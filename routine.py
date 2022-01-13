"""A collection of classes used in the 'machine code' generated by Auto Maple's compiler for each routine."""

import config
import utils
import csv
import settings
from os.path import splitext, basename
from layout import Layout


def update(func):
    """
    Decorator function that updates both the displayed routine and details
    for all mutative Routine operations.
    """

    def f(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        config.gui.set_routine(self.display)
        config.gui.view.details.update_details()
        return result
    return f


def dirty(func):
    """Decorator function that sets the dirty bit for mutative Routine operations."""

    def f(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        self.dirty = True
        return result
    return f


class Routine:
    """Describes a routine file in Auto Maple's custom 'machine code'."""

    labels = {}
    index = 0

    def __init__(self):
        self.dirty = False
        self.path = ''
        self.sequence = []
        self.display = []       # Updated alongside sequence

    @dirty
    @update
    def set(self, arr):
        self.sequence = arr
        self.display = [str(x) for x in arr]

    @dirty
    @update
    def append_component(self, p):
        self.sequence.append(p)
        self.display.append(str(p))

    @dirty
    @update
    def append_command(self, i, c):
        """Appends Command object C to the Point at index I in the sequence."""

        target = self.sequence[i]
        target.commands.append(c)
        config.gui.edit.routine.commands.update_display()

    @dirty
    @update
    def move_component_up(self, i):
        """Moves the component at index I upward if possible."""

        if i > 0:
            temp_s = self.sequence[i-1]
            temp_d = self.display[i-1]
            self.sequence[i-1] = self.sequence[i]
            self.display[i-1] = self.display[i]
            self.sequence[i] = temp_s
            self.display[i] = temp_d
            config.gui.edit.routine.components.select(i-1)

    @dirty
    @update
    def move_component_down(self, i):
        if i < len(self) - 1:
            temp_s = self.sequence[i+1]
            temp_d = self.display[i+1]
            self.sequence[i+1] = self.sequence[i]
            self.display[i+1] = self.display[i]
            self.sequence[i] = temp_s
            self.display[i] = temp_d
            config.gui.edit.routine.components.select(i+1)

    @dirty
    @update
    def move_command_up(self, i, j):
        """
        Within the Point at routine index I, moves the Command at index J upward
        if possible and updates the Edit UI.
        """

        point = self.sequence[i]
        if j > 0:
            temp = point.commands[j-1]
            point.commands[j-1] = point.commands[j]
            point.commands[j] = temp

            edit = config.gui.edit
            edit.routine.commands.update_display()
            edit.routine.commands.select(j-1)

    @dirty
    @update
    def move_command_down(self, i, j):
        point = self.sequence[i]
        if j < len(point.commands) - 1:
            temp = point.commands[j+1]
            point.commands[j+1] = point.commands[j]
            point.commands[j] = temp

            edit = config.gui.edit
            edit.routine.commands.update_display()
            edit.routine.commands.select(j+1)

    @dirty
    @update
    def delete_component(self, i):
        """Deletes the Component at index I."""

        self.sequence.pop(i)
        self.display.pop(i)

        edit = config.gui.edit
        edit.routine.components.clear_selection()
        edit.editor.reset()

    @dirty
    @update
    def delete_command(self, i, j):
        """Within the Point at routine index I, deletes the Command at index J."""

        point = self.sequence[i]
        point.commands.pop(j)

        edit = config.gui.edit
        edit.routine.commands.update_display()
        edit.routine.commands.clear_selection()
        edit.editor.create_edit_ui(self.sequence, i, edit.routine.components.update_obj)

    @update
    def update_component(self, i, new_kwargs):
        target = self.sequence[i]
        try:
            target.update(**new_kwargs)
            self.display[i] = str(target)
            self.dirty = True
        except (ValueError, TypeError) as e:
            print(f"\n[!] Found invalid arguments for '{target.__class__.__name__}':")
            print(f"{' ' * 4} -  {e}")

    @update
    def update_command(self, i, j, new_kwargs):
        target = self.sequence[i].commands[j]
        try:
            target.update(**new_kwargs)
            self.display[i] = str(self.sequence[i])
            self.dirty = True
        except (ValueError, TypeError) as e:
            print(f"\n[!] Found invalid arguments for '{target.__class__.__name__}':")
            print(f"{' ' * 4} -  {e}")

    def save(self, file_path):
        """Encodes and saves the current Routine at location PATH."""

        result = []
        for item in self.sequence:
            result.append(item.encode())
            if isinstance(item, Point):
                for c in item.commands:
                    result.append(' ' * 4 + c.encode())
        result.append('')

        with open(file_path, 'w') as file:
            file.write('\n'.join(result))
        self.dirty = False

        utils.print_separator()
        print(f"[~] Saved routine to '{basename(file_path)}'.")

    def clear(self):
        Routine.index = 0
        self.set([])
        self.dirty = False
        self.path = ''
        config.layout = None
        settings.reset()

        config.gui.clear_routine_info()

    def load(self, file=None):
        """
        Attempts to load FILE into a sequence of Components. If no file path is provided, attempts to
        load the previous routine file.
        :param file:    The file's path.
        :return:        None
        """

        utils.print_separator()
        print(f"[~] Loading routine '{basename(file)}':")

        if not file:
            if self.path:
                file = self.path
                print(' *  File path not provided, using previously loaded routine.')
            else:
                print('[!] File path not provided, no routine was previously loaded either.')
                return False

        ext = splitext(file)[1]
        if ext != '.csv':
            print(f" !  '{ext}' is not a supported file extension.")
            return False

        self.clear()

        # Compile and Link
        self.compile(file)
        for c in self.sequence:
            if isinstance(c, Jump):
                c.bind()

        self.dirty = False
        self.path = file
        config.layout = Layout.load(file)
        config.gui.view.status.set_routine(basename(file))
        config.gui.edit.minimap.draw_default()
        print(f"[~] Finished loading routine '{basename(splitext(file)[0])}'.")

    def compile(self, file):
        Routine.labels = {}
        with open(file, newline='') as f:
            csv_reader = csv.reader(f, skipinitialspace=True)
            curr_point = None
            line = 1
            for row in csv_reader:
                result = self._eval(row, line)
                if result:
                    if isinstance(result, Command):
                        if curr_point:
                            curr_point.commands.append(result)
                    else:
                        self.append_component(result)
                        if isinstance(result, Point):
                            curr_point = result
                line += 1

    def _eval(self, row, i):
        if row and isinstance(row, list):
            first, rest = row[0].lower(), row[1:]
            args, kwargs = utils.separate_args(rest)
            line_error = f' !  Line {i}: '

            if first in SYMBOLS:
                c = SYMBOLS[first]
            elif first in config.command_book:
                c = config.command_book[first]
            else:
                print(line_error + f"Command '{first}' does not exist.")
                return

            try:
                obj = c(*args, **kwargs)
                if isinstance(obj, Label):
                    obj.set_index(len(self))
                    Routine.labels[obj.label] = obj
                return obj
            except (ValueError, TypeError) as e:
                print(line_error + f"Found invalid arguments for '{c.__name__}':")
                print(f"{' ' * 4} -  {e}")

    @staticmethod
    def get_all_components():
        """Returns a dictionary mapping all creatable Components to their names."""

        options = config.command_book.copy()
        for e in (Point, Label, Jump, Setting):
            options[e.__name__.lower()] = e
        return options

    def __getitem__(self, i):
        return self.sequence[i]

    def __len__(self):
        return len(self.sequence)


#################################
#       Routine Components      #
#################################
class Component:
    id = 'Routine Component'
    PRIMITIVES = {int, str, bool, float}

    def __init__(self, *args, **kwargs):
        if len(args) > 1:
            raise TypeError('Component superclass __init__ only accepts 1 (optional) argument: LOCALS.')
        if len(kwargs) != 0:
            raise TypeError('Component superclass __init__ does not accept any keyword arguments.')
        if len(args) == 0:
            self.kwargs = {}
        elif type(args[0]) != dict:
            raise TypeError("Component superclass __init__ only accepts arguments of type 'dict'.")
        else:
            self.kwargs = args[0].copy()
            self.kwargs.pop('__class__')
            self.kwargs.pop('self')

    @utils.run_if_enabled
    def execute(self):
        self.main()

    def main(self):
        pass

    def update(self, *args, **kwargs):
        """Updates this Component's constructor arguments with new arguments."""

        self.__class__(*args, **kwargs)     # Validate arguments before actually updating values
        self.__init__(*args, **kwargs)

    def info(self):
        """Returns a dictionary of useful information about this Component."""

        return {
            'name': self.__class__.__name__,
            'vars': self.kwargs.copy()
        }

    def encode(self):
        """Encodes an object using its ID and its __init__ arguments."""

        arr = [self.id]
        for key, value in self.kwargs.items():
            if key != 'id' and type(self.kwargs[key]) in Component.PRIMITIVES:
                arr.append(f'{key}={value}')
        return ', '.join(arr)


class Command(Component):
    id = 'Command Superclass'

    def __init__(self, *args):
        super().__init__(*args)
        self.id = self.__class__.__name__

    def __str__(self):
        variables = self.__dict__
        result = '    ' + self.id
        if len(variables) - 1 > 0:
            result += ':'
        for key, value in variables.items():
            if key != 'id':
                result += f'\n        {key}={value}'
        return result


class Point(Component):
    """Represents a location in a user-defined routine."""

    id = '*'

    def __init__(self, x, y, frequency=1, skip='False', adjust='False'):
        super().__init__(locals())
        self.x = float(x)
        self.y = float(y)
        self.location = (self.x, self.y)
        self.frequency = settings.validate_nonnegative_int(frequency)
        self.counter = int(settings.validate_boolean(skip))
        self.adjust = settings.validate_boolean(adjust)
        if not hasattr(self, 'commands'):       # Updating Point should not clear commands
            self.commands = []

    def main(self):
        """Executes the set of actions associated with this Point."""

        if self.counter == 0:
            move = config.command_book.get('move')
            move(*self.location).execute()
            if self.adjust:
                adjust = config.command_book.get('adjust')
                adjust(*self.location).execute()
            for command in self.commands:
                command.execute()
        self._increment_counter()

    @utils.run_if_enabled
    def _increment_counter(self):
        """Increments this Point's counter, wrapping back to 0 at the upper bound."""

        self.counter = (self.counter + 1) % self.frequency

    def info(self):
        curr = super().info()
        curr['vars'].pop('location', None)
        curr['vars']['commands'] = ', '.join([c.id for c in self.commands])
        return curr

    def __str__(self):
        return f'  * {self.location}'


class Label(Component):
    id = '@'

    def __init__(self, label):
        super().__init__(locals())
        self.label = str(label)
        if self.label in Routine.labels:
            raise ValueError
        self.links = set()
        self.index = None

    def set_index(self, i):
        self.index = i

    def encode(self):
        return '\n' + super().encode()

    def info(self):
        curr = super().info()
        curr['vars']['index'] = self.index
        return curr

    def __delete__(self, instance):
        del self.links
        Routine.labels.pop(self.label)

    def __str__(self):
        return f'{self.label}:'


class Jump(Component):
    """Jumps to the given Label."""

    id = '>'

    def __init__(self, label, frequency=1, skip='False'):
        super().__init__(locals())
        self.label = str(label)
        self.frequency = settings.validate_nonnegative_int(frequency)
        self.counter = int(settings.validate_boolean(skip))
        self.link = None

    def main(self):
        if self.link is None:
            print(f"\n[!] Label '{self.label}' does not exist.")
        else:
            if self.counter == 0:
                Routine.index = self.link.index
            self._increment_counter()

    @utils.run_if_enabled
    def _increment_counter(self):
        self.counter = (self.counter + 1) % self.frequency

    def bind(self):
        """
        Binds this Goto to its corresponding Label. If the Label's index changes, this Goto
        instance will automatically be able to access the updated value.
        :return:    Whether the binding was successful
        """

        if self.label in Routine.labels:
            self.link = Routine.labels[self.label]
            self.link.links.add(self)
            return True
        return False

    def __delete__(self, instance):
        if self.link is not None:
            self.link.links.remove(self)

    def __str__(self):
        return f'  > {self.label}'


class Setting(Component):
    """Changes the value of the given setting variable."""

    id = '$'

    def __init__(self, target, value):
        super().__init__(locals())
        self.key = str(target)
        if self.key not in settings.SETTING_VALIDATORS:
            raise ValueError(f"Setting '{target}' does not exist")
        self.value = settings.SETTING_VALIDATORS[self.key](value)

    def main(self):
        setattr(settings, self.key, self.value)

    def __str__(self):
        return f'  $ {self.key} = {self.value}'


SYMBOLS = {
    '*': Point,
    '@': Label,
    '>': Jump,
    '$': Setting
}
