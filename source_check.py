from bluesky.plan_stubs import null, mv

import os, subprocess, inspect
from rich import print as cprint
from ophyd.sim import make_fake_device, SynAxis, FakeEpicsSignal

from source_check import m1a

def colored(text, tint='white', attrs=[], end=None):
    '''
    A simple wrapper around rich.print
    '''
    if not False:
        tint = tint.lower()
        this = f'[{tint}]{text}[/{tint}]'
        if end is not None:
            cprint(f'[{tint}]{text}[/{tint}]', end=end)
        else:
            cprint(f'[{tint}]{text}[/{tint}]')
    else:
        print(text)


def error_msg(text, end=None):
    '''Red text'''
    colored(text, 'red1', end=end)
def warning_msg(text, end=None):
    '''Yellow text'''
    colored(text, 'yellow', end=end)
def go_msg(text, end=None):
    '''Green text'''
    colored(text, 'green', end=end)
def url_msg(text, end=None):
    '''Underlined text, intended for URL decoration...'''
    colored(text, 'underline', end=end)
def bold_msg(text, end=None):
    '''Bright yellow text'''
    colored(text, 'yellow2', end=end)
def verbosebold_msg(text, end=None):
    '''Bright cyan text'''
    colored(text, 'cyan', end=end)
def list_msg(text, end=None):
    '''Dark cyan text'''
    colored(text, 'bold cyan', end=end)
def disconnected_msg(text, end=None):
    '''Purple text'''
    colored(text, 'magenta3', end=end)
def info_msg(text, end=None):
    '''Brown text'''
    colored(text, 'light_goldenrod2', end=end)
def cold_msg(text, end=None):
    '''Light blue text'''
    colored(text, 'blue', end=end)
def whisper(text, end=None):
    '''Light gray text'''
    colored(text, 'bold black', end=end)


class WDYWTD():
    '''What Do You Want To Do?

    An extremely simple textual user interface to the most commonly
    performed chores at BMM.

    '''
    def wdywtd(self):
        '''Prompt the user to do a thing.
        '''

        actions = {'1': ('SourceCheck',         'perform source check'),
                   '2': ('ChangeEdge',   'change edge'),
                   '3': ('Spreadsheet',  'import spreadsheet'),
                   '4': ('RunMacro',     'run macro'),
                   '5': ('AlignSlot',    'align wheel slot'),
                   '6': ('AlignGA',      'align glancing angle stage'),
                   '7': ('XRFSpectrum',  'view XRF spectrum'),

        }
        
        print('''
  CHOICES                       
======================================''')

        for i in range(1,8):
            text  = actions[str(i)][1]
            try:
                other = actions[chr(64+i)][1]
                print(f' {i}. {text:37} ')
            except:
                print(f' {i}. {text:37}')
        print('')
        choice = input(" What do you want to do? ")
        choice = choice.upper()
        print('\n')
        def bailout():
            whisper('doing nothing')
            yield from null()
        thing = 'do_nothing'
        if choice in actions:
            thing = f'do_{actions[choice][0]}'
        return getattr(self, thing, lambda: bailout)()
    def doSourceCheck(self):
        

        go_msg('You would like to perform a source check...\n')

        # Step 0 - preperation
        print("Make sure FE Shutter is closed...")
        print("Record current M1a position as operating position...")
        print("Record current FEslt position as operating position...")

        # Step 1 - detuned source
        print("Setting EPU1 to 100...")
        print("Setting EPU2 to 100...")
        print("Setting M1a to 'out' (using relative motion)...")


        # Step 2 - ios source
        print("Setting EPU1 to 85...")

        # Step 3 - csx source
        print("Setting EPU1 to 100...")
        print("Setting EPU2 to 85...")

        # Step 4 - source
        print("Setting EPU1 to 83...")
        print("Setting EPU2 to 83...")
        print("Make sure EPU phases are set to 0...")

        # Step 5 - check slits
        print("Setting FEslt to normal operating position...")

        # Step 6 - check M1a pos
        print("Setting M1a to 'in' (using relative motion)...")

        # Step 7 - check pink beam
        print("Setting FS diag to Pink Beam position...")

        # Step 8 - check pink beam and slits
        print("Setting FEslt to normal operating position...")




    def do_MoveDiag(self):
        go_msg('You would like to move es_diag1...\n')
        print("Where would you like to move it? (position name or 'm' for manual value)")
        es_diagWithLookup.get_all_positions()
        where = input()
        print(f"You chose {where}")
        y = float(es_diagWithLookup.motor.read()['es_diagWithLookup_motor']['value'])
        match where:
            case "m":
                print("Enter Y value (number or 'c' for current value): ")
                i = input()
                match i:
                    case "c":
                        y = y
                    case _:
                        y = float(i)
            case _:
                try:
                    y = es_diagWithLookup.lookup(where)
                except ValueError:
                    print(f"{where} is not one of the available options")
                    return
        print(f"Y: {y}")
        print(f"CONFIRM: Move to {y} (y/n)")
        confirmation = input()
        match confirmation.lower():
            case "y" | "yes":
                print (f"Moving to {y}...")
                print ("yield from mv(es_diagWithLookup, y)")
            case "n" | "no":
                print ("Movement canceled.")
        
    
    def do_AdjustSlit3(self):
        go_msg('You would like to adjust the size of the slt3...\n')
        print("Where would you like to position it? (2000, 50, 20, 10, or 'm' for manual coordinates)")
        slt3WithLookup.get_all_sizes()
        where = input()
        where = where.lower()
        print(f"You chose {where}")
        x = float(slt3WithLookup.x.read()['slt3WithLookup_x']['value'])
        y = float(slt3WithLookup.y.read()['slt3WithLookup_y']['value'])
        match where:
            case "2000" | "50" | "20" | "10":
                x, y = slt3WithLookup.lookup(where)
            case "m":
                print("Enter X value (number or 'c' for current value): ")
                i = input()
                match i:
                    case "c":
                        x = x
                    case _:
                        x = float(i)
                print(f"X: {x}")
                print("Enter Y value (number or 'c' for current value): ")
                i = input()
                match i:
                    case "c":
                        y = y
                    case _:
                        y = float(i)
                print(f"Y: {y}")
            case _:
                print(f"{where} is not one of the available options")
                return
        
        print(f"CONFIRM: Move to ({x}, {y}) (y/n)")
        confirmation = input()
        match confirmation.lower():
            case "y" | "yes":
                print (f"Moving to ({x}, {y})...")
                print ("yield from mv(slt3WithLookup, (x, y))")
            case "n" | "no":
                print ("Movement canceled.")
            

            