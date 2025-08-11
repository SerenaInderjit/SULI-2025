from bluesky.plan_stubs import null, mv
from bluesky.plans import count

import os, subprocess, inspect
from rich import print as cprint
from typing import Callable
from source_check_devices import FE_shutter, m1a, epu1, epu2, FEslt, canter, phaser, fs_diag1_x, cam_fs1_hdf5, make_fluo_img


# sd.baseline.extend([FEslt.x.gap.readback, 
#           FEslt.x.cent.readback, 
#           FEslt.y.gap.readback, 
#           FEslt.y.cent.readback,
#           fs_diag1_x.pos_sel,
#           fs_diag1_x.x.user_readback,
#           canter,
#           phaser.user_readback])


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

def print_dict(dict):
    for key in dict:
        print(f"\t{key}: {dict[key]}")


class SourceCheck():
    


    def source_check_manual(self):
        '''Prompt the user to do a thing.
        '''

        actions = {'0': ('Prep',   'preparation'),
                   '1': ('Step1',   'detuned source'),
                   '2': ('Step2',   'ios source'),
                   '3': ('Step3',   'csx source'),
                   '4': ('Step4',   'source'),
                   '5': ('Step5',   'check slits1'),
                   '6': ('Step6',   'check m1a pos'),
                   '7': ('Step7',   'check pink beam'),
                   '8': ('Step8',   'check pink beam & slits'),
                   '9': ('Return',     'return to ops'),
                   '10': ('Quit',   'Quit')
        }
        
        print('''
  CHOICES                       
======================================''')

        for i in range(0,11):
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

    def end_step(self, next_step, next_step_name):
        """Handle the end of a source check step.
        
        Prompt the user to
                
                (1) Continue to next step
                (2) Go back to the source check menu
                (3) Quit the source check
                
        and proceed with their choice.
        """

        print("End of step - Choose how to proceed:\n")
        print(f" 1. Continue to next step: {next_step_name}")
        print(" 2. Quit and go to menu")
        print(" 3. Quit source check (default)")
        i = input()
        match i:
            case "1":
                next_step()
            case "2":
                self.source_check_manual()
            case _:
                return 


    def pause(self, prompt, action : tuple | Callable, current_step : Callable, current_prompt : Callable):
        """Handle an interruption in the source check process.
        
        Prompt the user to 
        
                (1) quit
                (2) continue the step
                (3) restart the current step
                (4) go back to the source check menu

        and return True to continue the step, otherwise, perform the desired action.

        Parameters
        ----------
        current_step : function
                The function representing the current step in the source check process.
        """
        print("\nSource check paused. What would you like to do?")
        print("1. Continue from last prompt" \
                "\n2. Return to source check menu" \
                "\n3. Restart step" \
                "\n4. Quit source check (default)")
        match input():
                case "1": 
                        return current_prompt(prompt, action, current_step)

                case "2":
                        self.source_check_manual()
                        return False

                case "3":
                        current_step()
                        return False
                
                case _:
                        return False
            

    def confirm_default_n(self, prompt, action : tuple | Callable, current_step : Callable):
        """Prompt the user to confirm an action with a default response of 'n'.
            Performs action and returns True if the user confirms otherwise returns 
            result of the pause() function.

        Parameters
        ----------
        prompt : str
                The message to display to the user.
        action : function
                The plan to execute if the user confirms.
        current_step : function
                The function representing the current step in the source check process.
        """
        match input(prompt + "  "):
                case "y":
                        if isinstance(action, Callable):
                            #  yield from action()
                             print(f"yield from {action.__name__}")
                        else:
                            plan, motor, target = action
                            # yield from plan(signal, target)
                            print(f"yield from {plan.__name__}({motor}, {target})")
                            return True

                case _ : return self.pause(prompt, action, current_step, self.confirm_default_n)
        
    
    def confirm_default_y(self, prompt, action: tuple | Callable, current_step : Callable):
        """Prompt the user to confirm an action with a default response of 'y'.
            Returns returns result of the pause() function if user refuses, otherwise 
            performs action and returns True.

        Parameters
        ----------
        prompt : str
                The message to display to the user.
        action : function
                The plan to execute if the user confirms.
        current_step : function
                The function representing the current step in the source check process.
        """
        match input(prompt + "  "):
                case "n" : return self.pause(prompt, action, current_step, self.confirm_default_y)
             
                case _ :
                        if isinstance(action, Callable):
                            #  yield from action()
                             print(f"yield from {action.__name__}")
                        else:
                            plan, motor, target = action
                            # yield from plan(signal, target)
                            print(f"yield from {plan.__name__}({motor}, {target})")
                            return True

    def prompt_and_act(self, prompts, actions, defaults, current_step):
        """Prompt the user with a list of prompts and actions, and execute the actions based on the user's input.
        
        Parameters
        ----------
        prompts : list of str
                The messages to display to the user.
        actions : list of tuple | Callable
                The plans to execute if the user confirms.
        defaults : list of str
                The default responses for each prompt.
        current_step : Callable
                The function representing the current step in the source check process.
        """
        for prompt, action, default in zip(prompts, actions, defaults):
            if default == 'y':
                if not self.confirm_default_y(prompt, action, current_step):
                    return False
            else:
                if not self.confirm_default_n(prompt, action, current_step):
                    return False
        return True


    def do_Prep(self):

        print("\nSource check preparation")
        print("--------------------------")

        # Make sure FE shutter is closed
        print("\n\tFE Shutter")
        print("\t-----------")
        if FE_shutter.status.get() != 'Closed':
            if not self.confirm_default_y("\n\tClose FE Shutter? ([y]/n)", (mv, FE_shutter, 'Close'), self.do_Prep): return
            
        else:
            print("\n\tFE Shutter is closed")
        
        # Record starting positions using setpoints
        print("\n\tRecord OPS")
        print("\t-----------")
        m1a_ops = {"x" : round(m1a.x.setpoint.get(), 4), 
                   "y" : round(m1a.y.setpoint.get(), 4), 
                   "z" :  round(m1a.z.setpoint.get(), 4), 
                   "pit" : round(m1a.pit.setpoint.get(), 4), 
                   "yaw" : round(m1a.yaw.setpoint.get(), 4), 
                   "roll" : round(m1a.rol.setpoint.get(), 4)}
        
        FEslt_ops = {"x_gap" : round(FEslt.x.gap.setpoint.get(), 4), 
                     "y_gap" : round(FEslt.y.gap.setpoint.get(), 4), 
                     "x_cent" : round(FEslt.x.cent.setpoint.get(), 4), 
                     "y_cent" : round(FEslt.y.cent.setpoint.get(), 4)}
        
        FSdiag_ops = {"x" : round(fs_diag1_x.x.user_setpoint.get(), 4)}
        
        epu1_ops = {"gap" : round(epu1.gap.setpoint.get(), 4), "phase" : round(epu1.phase.setpoint.get(), 4)}
        epu2_ops = {"gap" : round(epu2.gap.setpoint.get(), 4), "phase" : round(epu2.phase.setpoint.get(), 4)}
        
        print(f"\n\tRecording current M1a position as \n")
        print_dict(m1a_ops)
        print(f"\n\tRecording current FEslt position as operating position as \n")
        print_dict(FEslt_ops)
        print(f"\n\tRecording current FSdiag position as \n")
        print_dict(FSdiag_ops)
        print(f"\n\tRecording current EPU1 position as \n")
        print_dict(epu1_ops)
        print(f"\n\tRecording current EPU1 position as \n")
        print_dict(epu2_ops)

        # Make sure EPU phases are 0
        print("\n\tEPU Phases")
        print("\t-----------")

        if (epu1.phase.setpoint.get() != 0):

            if not self.confirm_default_n((f"\n\tThe current EPU1 phase is {epu1_ops['phase']}. Set EPU1 phase to 0? (y/n)"), 
                                        (mv, epu1.phase, 0), self.do_Prep): return
            
        else:
            print("\n\tEPU1 phase is 0")
    
        if (epu2.phase.setpoint.get() != 0):

            if not self.confirm_default_n((f"\n\tThe current EPU2 phase is {epu2_ops['phase']}. Set EPU2 phase to 0? (y/n)"), 
                                        (mv, epu2.phase, 0), self.do_Prep): return
            
        else:
            print("\n\tEPU2 phase is 0")

        print()
        self.end_step(self.do_Step1, "Detuned Source")


    def do_Step1(self):

        print("\nStep 1 - detuned source\n")
        print("--------------------------")

        prompts = [
            "\n\tSet EPU1 Gap to 100. Confirm ([y]/n).",
            "\n\tSet EPU2 Gap to 100. Confirm ([y]/n).",
            "\n\tOpen FE slits. Confirm (y/[n]).",
            "\n\tMove m1a to 'out' position. Confirm (y/[n]).",
            "\n\tOpen FE shutter. Confirm (y/[n]).",
            "\n\tTake photo of FSdiag. Confirm ([y]/n)."
        ]

        actions = [
            (mv, epu1.gap, 100),
            (mv, epu2.gap, 100),
            FEslt.mv_open,
            m1a.mv_out,
            (mv, FE_shutter, 'Open'),
            make_fluo_img
        ]
        
        defaults = ['y', 'y', 'n', 'n', 'n', 'y']

        if not self.prompt_and_act(prompts, actions, defaults, self.do_Step1): return

        print()
        self.end_step(self.do_Step2, "IOS Source")


    def do_Step2(self):

        print("\nStep 2 - ios source\n")
        print("--------------------------")

        prompts = [
            "\n\tSet EPU1 Gap to 82. Confirm ([y]/n)", 
            "\n\tTake photo of FSdiag. Confirm ([y]/n)."
        ]

        actions = [
            (mv, epu1.gap, 82),
            make_fluo_img
        ]

        defaults = ['y', 'y']

        if not self.prompt_and_act(prompts, actions, defaults, self.do_Step2): return

        print()
        self.end_step(self.do_Step3, "CSX Source")


    def do_Step3(self):

        print("\nStep 3 - csx source\n")
        print("--------------------------")

        prompts = [
            "\n\tSet EPU1 Gap to 100. Confirm ([y]/n)", 
            "\n\tSet EPU2 Gap to 85. Confirm ([y]/n)", 
            "\n\tTake photo of FSdiag. Confirm ([y]/n)."
        ]

        actions = [
            (mv, epu1.gap, 100),
            (mv, epu2.gap, 85),
            make_fluo_img
        ]

        defaults = ['y', 'y', 'y']

        if not self.prompt_and_act(prompts, actions, defaults, self.do_Step3): return
        print()
        self.end_step(self.do_Step3, "Source")


    def do_Step4(self):

        print("\nStep 4 - source\n")
        print("--------------------------")

        prompts = [
            "\n\tSet EPU1 Gap to 82. Confirm ([y]/n)", 
            "\n\tTake photo of FSdiag. Confirm ([y]/n)."
        ]

        actions = [
            (mv, epu1.gap, 82),
            make_fluo_img
        ]

        defaults = ['y', 'y']

        if not self.prompt_and_act(prompts, actions, defaults, self.do_Step4): return

        print()
        self.end_step(self.do_Step3, "Check Slits")

    def do_Step5(self):
        
        print("\nStep 5 - check slits]")
        print("--------------------------")

        prompts = [
             f"\n\tSet X Gap of FE slits to operating position: {self.FEslt_ops['x_gap']}. Confirm (y/[n])",
            "\n\tTake photo of FSdiag. Confirm ([y]/n)"
        ]

        actions = [
            (mv, FEslt.x.gap, self.FEslt_ops['x_gap']),
            make_fluo_img
        ]

        defaults = ['n', 'y']

        if not self.prompt_and_act(prompts, actions, defaults, self.do_Step5): return

        print()
        self.end_step(self.do_Step3, "Check M1a Position")

    def do_Step6(self):

        print("\nStep 6 - check m1a pos\n")
        print("--------------------------")


        prompts = [
            "\n\tClose FE shutter. Confirm ([y]/n)",
            f"\n\tMove m1a to operating position: {self.m1a_ops}. Confirm (y/[n])",
            "\n\tOpen FE slits. Confirm (y/[n])",
            "\n\tTake photo of FSdiag. Confirm ([y]/n)"
        ]

        actions = [
            (mv, FE_shutter, 'Close'),
            (mv, m1a, self.m1a_ops),
            FEslt.mv_open,
            make_fluo_img
        ]

        defaults = ['y', 'n', 'n', 'y']

        if not self.prompt_and_act(prompts, actions, defaults, self.do_Step6): return

        print()
        self.end_step(self.do_Step3, "Check Pink Beam")

    def do_Step7(self):

        print("\nStep 7 - check pink beam\n")
        print("--------------------------")


        prompts = [
            "\n\tClose FE shutter. Confirm ([y]/n)",
            "\n\tSet FS diag to Pink Beam position. Confirm (y/[n])",
            "\n\tOpen FE shutter. Confirm (y/[n])",
            "\n\tTake photo of FSdiag. Confirm ([y]/n)"
        ]

        actions = [
            (mv, FE_shutter, 'Close'),
            (mv, fs_diag1_x, 'Pink Beam'),
            (mv, FE_shutter, 'Open'),
            make_fluo_img
        ]

        defaults = ['y', 'n', 'n', 'y']

        if not self.prompt_and_act(prompts, actions, defaults, self.do_Step7): return
        

        print()
        self.end_step(self.do_Step3, "Check Pink Beam & Slits")

    def do_Step8(self):

        print("\nStep 8 - check pink beam & slits\n")
        print("-----------------------------------")

        prompts = [
            "\n\tClose FE shutter. Confirm ([y]/n)",
            f"\n\tSet FEslt to operating position: {self.FEslt_ops}. Confirm (y/[n])",
            "\n\tTake photo of FSdiag. Confirm ([y]/n)"
        ]

        actions = [
            (mv, FE_shutter, 'Close'),
            (mv, FEslt, self.FEslt_ops),
            make_fluo_img
        ]

        defaults = ['y', 'n', 'y']

        if not self.prompt_and_act(prompts, actions, defaults, self.do_Step8): return

        print()
        self.end_step(self.do_Step3, "Return to OPS")


    def do_ReturnToOPS(self):

        print("\nEnd - return to operating positions\n")
        print("-------------------------------------")

        prompts = [
            "\n\tClose FE shutter. Confirm ([y]/n)",
            "\n\tSet FS diag to 'out'. Confirm ([y]/n)",
            "\n\tOpen FE shutter. Confirm (y/[n])"
        ]

        actions = [
            (mv, FE_shutter, 'Close'),
            (mv, fs_diag1_x, 'out'),
            (mv, FE_shutter, 'Open')
        ]

        defaults = ['y', 'y', 'n']

        if not self.prompt_and_act(prompts, actions, defaults, self.do_ReturnToOPS): return

    def do_Quit(self):
        return
    

prompt = SourceCheck()





