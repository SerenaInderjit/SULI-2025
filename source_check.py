from bluesky.plan_stubs import null, mv

import os, subprocess, inspect
from rich import print as cprint

from source_check_devices import m1a, epu1, epu2, FEslt, fs_diag1_x

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


class SourceCheck():
    


    def source_check_manual(self):
        '''Prompt the user to do a thing.
        '''

        actions = {'0': ('Step0',   'preparation'),
                   '1': ('Step1',   'detuned source'),
                   '2': ('Step2',   'ios source'),
                   '3': ('Step3',   'csx source'),
                   '4': ('Step4',   'source'),
                   '5': ('Step5',   'check slits1'),
                   '6': ('Step6',   'check m1a pos'),
                   '7': ('Step7',   'check pink beam'),
                   '8': ('Step8',   'check pink beam & slits'),
                   '9': ('End',     'return to ops')
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
    
    m1a_ops = {}
    FEslt_ops = {}
    FSdiag_ops = {}
    epu1_ops = {}
    epu2_ops = {}

    def abort(self):
        print("Abort or Continue Step (default abort)\n1. Abort\n2. Continue")
        i = input()
        match i:
            case "2":
                return False
            case _:
                return True
            

    def input_default_n(self, prompt, plan, signal, target):
        print(prompt)
        i = input()
        match i:
            case "y":
                yield from plan(signal, target)
            case _:
                if (self.abort()):
                    return False
                else: 
                    return True 
            

    def input_default_y(self, prompt):
        print(prompt)
        i = input()
        match i:
            case "n":
                return False
            case _:
                return True


    def doPrep(self):

        print("\nSource check preparation\n")

        # Make sure FE shutter is closed
        print("Close FE shutter. Confirm ([y]/n)")
        if (self.input_default_n()):
            "yield from (TODO: build shutter device)"
        else:
            if (self.abort()):
                return
            else:
                self.doPrep()
        


        # Record starting positions using setpoints
        m1a_ops = {"x" : m1a.x.setpoint.get(), 
                   "y" : m1a.y.setpoint.get(), 
                   "z" :  m1a.z.setpoint.get(), 
                   "pit" : m1a.pit.setpoint.get(), 
                   "yaw" : m1a.yaw.setpoint.get(), 
                   "roll" : m1a.rol.setpoint.get()}
        
        FEslt_ops = {"x_gap" : FEslt.x.gap.setpoint.get(), 
                     "y_gap" : FEslt.y.gap.setpoint.get(), 
                     "x_cent" : FEslt.x.cent.setpoint.get(), 
                     "y_cent" : FEslt.y.cent.setpoint.get()}
        
        FSdiag_ops = {"x" : fs_diag1_x.setpoint.get()}

        epu1_ops = {"gap" : epu1.gap.setpoint.get(), "phase" : epu1.phase.setpoint.get()}
        epu2_ops = {"gap" : epu2.gap.setpoint.get(), "phase" : epu2.phase.setpoint.get()}

        print(f"Recording current M1a position as {m1a_ops}...")
        print(f"Recording current FEslt position as operating position as {FEslt_ops}...")
        print(f"Recording current FSdiag position as {FSdiag_ops}")
        print(f"Recording current EPU1 position as {epu1_ops}")
        print(f"Recording current EPU1 position as {epu2_ops}")

        # Make sure EPU phases are 0
        if (epu1.phase.setpoint.get() != 0):
            print("Set EPU1 phase to 0. Confirm (y/n)")     # Check risk for default
    
        if (epu2.phase.setpoint.get() != 0):
            print("Set EPU2 phase to 0. Confirm (y/n)")     # Check risk for default
        
        self.source_check_manual()



    def doStep1(self):

        print("\nStep 1 - detuned source\n")

        print("Set EPU1 Gap to 100. Confirm ([y]/n)")

        print("Set EPU2 Gap to 100. Confirm ([y]/n)")

        print ("Open FE slits. Confirm (y/[n])")

        print("Move m1a to 'out' position. Confirm (y/n)")     # Check risk for default

        print("Open FE shutter. Confirm (y/[n])")

        print("Take photo of FSdiag. Confirm ([y]/n)")

        self.source_check_manual()

    def doStep2(self):

        print("\nStep 2 - ios source\n")

        print("Set EPU1 Gap to 82. Confirm ([y]/n)")

        print("Take photo of FSdiag. Confirm ([y]/n)")

        self.source_check_manual()


    def doStep3(self):

        print("\nStep 3 - csx source\n")

        print("Set EPU1 Gap to 100. Confirm ([y]/n)")

        print("Set EPU2 Gap to 85. Confirm ([y]/n)")
        
        print("Take photo of FSdiag. Confirm ([y]/n)")

        self.source_check_manual()


    def doStep4(self):

        print("\nStep 4 - source\n")

        print("Set EPU1 Gap to 82. Confirm ([y]/n)")
        
        print("Take photo of FSdiag. Confirm ([y]/n)")

        self.source_check_manual()

    def doStep5(self):
        
        print("\nStep 5 - check slits1n]")

        print("Set Y Gap of FE slits to {operating pos}. Confirm (y/[n])")

        print("Take photo of FSdiag. Confirm ([y]/n)")

        self.source_check_manual()

    def doStep6(self):

        print("\nStep 6 - check m1a pos\n")

        print("Close FE shutter. Confirm ([y]/n)")

        print("Move m1a to {normal operating pos}. Confirm (y/n)")     # Check risk for default

        print("Open FE slits. Confirm (y/[n])")

        print("Take photo of FSdiag. Confirm ([y]/n)")

        self.source_check_manual()

    def doStep7(self):

        print("\nStep 7 - check pink beam\n")
        
        print("Close FE shutter. Confirm ([y]/n)")

        print("Set FS diag to Pink Beam position. Confirm (y/n)")     # Check risk for default
        
        print("Open FE shutter. Confirm (y/[n])")
        
        print("Take photo of FSdiag. Confirm ([y]/n)")

        print("Close FE shutter. Confirm ([y]/n)")

        self.source_check_manual()

    def doStep8(self):

        print("\nStep 8 - check pink beam & slits\n")

        print("Setting FEslt to {normal operating pos}. Confirm (y/[n])")

        print("Take photo of FSdiag. Confirm ([y]/n)")

        self.source_check_manual()

    def doReturnToOPS(self):

        print("\nEnd - return to operating positions\n")

        print("Close FE shutters. Confirm ([y]/n)")

        print("Set FS diag to 'out'. Confirm ([y]/n)")

        print("Open FE shutter. Confirm (y/[n])")








