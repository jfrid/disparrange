#!/usr/bin/env python3

'''
Display setup configuration tool for use with e.g. i3 window manager.
The tool uses xrandr for activating and deactivating different display outputs
with specified mode (resolution) and position.

The display setups shall be defined in a JSON file with the following format:

{
    "setup-name": [
        {"output": "eDP-1", "mode": [1920, 1080], "pos": [1920, 0]},
        {"output": "DP-2-1"}
    ]
}

When a display setup is activated, all outputs listed for that setup is
activated whereas all others are deactivated (turned off). Each output
specification takes 1-3 arguments:

- "output": name of display output (can be listed with xrandr --listmonitors)
- "mode" (optional): mode or resolution to use. Defaults to auto, which is
  likely to be the native resolution of the display.
- "pos" (optional): position relative to the other displays. [0, 0] is the
  top left corner, so [1920, 200] means "locate this display 1920 pixels right
  and 200 pixels down".
'''

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


class OutputDevice(object):
    def __init__(self, name, is_connected):
        self.name = name
        self.is_connected = is_connected
        self.modes = []

    def __repr__(self):
        return "<{cls} {name}: {connected}>".format(
            cls=self.__class__.__name__, name=self.name,
            connected="connected" if self.is_connected else "disconnected"
        )

    def add_mode(self, width, height):
        self.modes.append([width, height])


def load_display_setups(filename):
    filepath = Path(filename)
    if not filepath.is_absolute():
        filepath = Path(__file__).parent.absolute() / filepath
    with open(filepath) as jsonfile:
        return json.load(jsonfile)


def get_available_displays():
    displays = []
    proc = subprocess.run(['xrandr'],
                           stdout=subprocess.PIPE, universal_newlines=True)
    new_display = None
    for line in proc.stdout.splitlines():
        if line.startswith('Screen'):
            continue
        if not line.startswith(' '):
            if new_display is not None:
                # A new display description is starting - add the previous one
                displays.append(new_display)
            display_props = line.split()
            name = display_props[0]
            is_connected = display_props[1] == 'connected'
            new_display = OutputDevice(name, is_connected)
        else:
            mode_props = line.split()
            resolution = mode_props[0].split('x')
            new_display.add_mode(*resolution)
    if new_display is not None:
        displays.append(new_display)
    return displays


def list_display_setups(setups_file):
    display_setups = load_display_setups(setups_file)
    print(f'The following setups are defined in {setups_file}:')
    print('\n'.join(display_setups.keys()))


def set_display_setup(setup_name, setups_file, dry_run=False):
    display_setups = load_display_setups(setups_file)

    display_setup = display_setups.get(setup_name)
    if display_setup is None:
        print('Invalid display setup name:', setup_name, file=sys.stderr)
        return 1

    print(f'Activating display setup {setup_name}')
    available_displays = get_available_displays()
    arg_groups = {}
    for setup in display_setup:
        output = setup.get('output')
        mode = setup.get('mode')
        pos = setup.get('pos', (0, 0))
        matching_displays = [ disp for disp in available_displays if disp.name == output]
        if not matching_displays:
            print(f'Output "{output}" does not exist', file=sys.stderr)
            return 2
        if not matching_displays[0].is_connected:
            print(f"warning: {output} is not connected", file=sys.stderr)

        display_args = ['--output', output,
                        '--pos', f'{pos[0]}x{pos[1]}']
        if mode is not None:
            display_args.extend(['--mode', f'{mode[0]}x{mode[1]}'])
        else:
            display_args.append('--auto')
        arg_groups[output] = display_args

    if len(arg_groups) == 0:
        print(f"No connected displays were configured - aborting", file=sys.stderr)
        return 3

    for display in available_displays:
        if not display.name in arg_groups.keys():
            arg_groups[display] = ['--output', display.name, '--off']

    xrandr_args = ['xrandr']
    for arg_group in arg_groups.values():
        xrandr_args.extend(arg_group)

    if dry_run:
        xrandr_args.append('--dryrun')
        print('command:', ' '.join(xrandr_args))
    return subprocess.run(xrandr_args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('setup', nargs='?',
                        help='Name of display setup to activate. Leave empty to '
                             'list available setups')
    parser.add_argument('-j', '--jsonfile', default='displaysetups.json',
                        help='Name of display setups JSON file')
    parser.add_argument('-n', '--dry-run', action='store_true')
    parser.add_argument('-l', '--list-setups', action='store_true',
                         help='List names of available setups in the jsonfile')

    args = parser.parse_args()
    if args.setup is None:
        list_display_setups(args.jsonfile)
    else:
        set_display_setup(args.setup, args.jsonfile, args.dry_run)
