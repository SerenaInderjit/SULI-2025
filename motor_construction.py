from ophyd import EpicsMotor, sim, Device
from ophyd import Component as Cpt, FormattedComponent as FCpt
from ophyd.sim import make_fake_device, SynAxis, FakeEpicsSignal
from ophyd.signal import EpicsSignal
from ophyd.status import MoveStatus, wait
from ophyd.device import DynamicDeviceComponent
from ophyd.ophydobj import OphydObject
from bluesky.plans import count, scan
from bluesky.plan_stubs import mv
from bluesky.simulators import summarize_plan
from bluesky.preprocessors import SupplementalData
from collections import OrderedDict

def make_lookup_row(*args, col_suffixes: list[str], prefix : str, row_number : int, **kwargs):

    defn = OrderedDict()
    num_cols = len(col_suffixes)

    # Dynamic number of signals to represent the number of columns
    for i in range(num_cols):
        pv = (prefix + "-" + col_suffixes[i] + "}Val:" + str(row_number) + "-SP")

        valid_key_name = (col_suffixes[i]).replace(":", "_") # Key names can't have ":" for some reason # Make lowercase
        defn[valid_key_name] = (EpicsSignal, pv, {})

    # defn = {"Ax:X" : (EpicsSignal, <X_val_pv>, {}),
    #         "Ax:Y" : (EpicsSignal, <Y_val_pv>, {}), 
    #           ...}
  
    class LookupRow(Device):

       
        axes = DynamicDeviceComponent(defn)
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)       
        
        def get_row(self):
            row = {}
            for axis in defn:
                row[axis] = defn[axis][1].get()
            return row

    return LookupRow



def make_lookup_table(*args, pos_sel_dev : str, num_rows : int, col_suffixes : list[str], prefix : str, **kwargs):
    defn = OrderedDict()
    
    # Find out all 16 extensions and add them
    pos_sel_extensions = ["ONST", "TWST", "THST", "FVST", "SXST", "EIST", "NIST" ,"TEST"]

    # Dynamic number of signals to represent the number of rows
    for i in range(num_rows):
        pos_name = EpicsSignal((prefix + "-" + pos_sel_dev + "}Pos-Sel." + pos_sel_extensions[i])).read()
        LookupRow = make_lookup_row(col_suffixes=col_suffixes, prefix=prefix, row_number=i)           # Possible to use one row class to instantiate all rows of the table? (row_number changes)

        defn[pos_name] = (LookupRow, "", {"name" : "row{i}"})
        
    class LookupTable(Device):
        
        rows = DynamicDeviceComponent(defn)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

    return LookupTable



def make_motors (*args, prefix : str, col_suffixes : list[str], **kwargs):
    defn = OrderedDict()

    for col_suffix in col_suffixes:
        valid_key_name = (col_suffix).replace(":", "_") 
        defn[valid_key_name] = (EpicsMotor, (prefix + col_suffix + "}Mtr"), {})
    
    class LookupMotors(Device):
        motors = DynamicDeviceComponent(defn)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def get_motors(self):
            motors = {}
            for axis in defn:
                curr_axis = {}
                curr_axis["value"] = self.motors.read()[self.name + "_motors_" + axis]["value"]
                curr_axis["setpoint"] = self.motors.read()[self.name + "_motors_" + axis + "_user_setpoint"]["value"]
                
                motors[axis] = curr_axis
            return motors

    return LookupMotors



def make_device_with_lookup_table(prefix : str, pos_sel_dev: str, num_rows: int, col_suffixes: list[str],  *args, **kwargs):

    
    lookup_class = make_lookup_table(pos_sel_dev=pos_sel_dev, num_rows=num_rows, col_suffixes=col_suffixes, prefix=prefix)
    motors_class = make_motors(prefix=prefix, col_suffixes=col_suffixes)

    class DeviceWithLookup(Device):

        pos_lookup = Cpt(lookup_class, "")
        motors = Cpt(motors_class, "")


        pos_sel = Cpt(EpicsSignal, prefix + pos_sel_dev + "}Pos-Sel", kind = 'hinted', string=True)
    

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
        
        def lookup(self, name : str):
            lookup = self.pos_lookup.get_table()
            for pos_name in lookup:
                if pos_name == name:
                    return lookup[pos_name]
            raise ValueError (f"Could not find {name} in lookup table")
                
        def get_all_positions(self):
            lookup = self.pos_lookup.get_table()
            length = len(lookup)
            print(f"\n{length} possible positions:")
            print("----------------------------------")
            for pos_name in lookup:
                if lookup[pos_name] != "Undefined":
                    print(f'    {pos_name:_<15} : {lookup[pos_name]}')

        def set_pos(self, pos: str | tuple):
            lookup = self.pos_lookup.get_table()

            if isinstance(pos, tuple):
                for pos_name in lookup:
                    pos_tuple = tuple(lookup[pos_name].values())
                    match = True
                    for axis_index in range(len(pos_tuple) - 1):

                        if float(pos[axis_index]) != float(pos_tuple[axis_index]):
                            match = False
                    if match == True:
                        pos = pos_name
                        break
                    
            return self.pos_sel.set(str(pos))
        
        def update_pos(self, status):
            
            motors = self.motors.get_motors()
            
            motor_values = tuple([motors[axis]["value"] for axis in motors])
            
            self.set_pos(motor_values)
        
        def set(self, size : str | tuple):

            if isinstance(size, str):
                values = list(self.lookup(size).values())
            else: values = list(size)
            
            motor = getattr(self.motors.motors, "Ax_X")
            move_status = MoveStatus(motor, motor.set(0))
            return move_status

            
    return DeviceWithLookup