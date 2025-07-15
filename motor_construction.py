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
                row[axis] = getattr(self.axes, axis).get()
            return row

    return LookupRow



def make_lookup_table(*args, pos_sel_dev : str, num_rows : int, col_suffixes : list[str], prefix : str, **kwargs):
    defn = OrderedDict()
    
    # Find out all 16 extensions and add them
    pos_sel_extensions = ["", "ONST", "TWST", "THST", "FRST", "FVST", "SXST", "SVST", "EIST", "NIST" ,"TEST"]

    # Dynamic number of signals to represent the number of rows
    for i in range(1, num_rows):
        
        pos_name = "Row_" + EpicsSignal((prefix + "-" + pos_sel_dev + "}Pos-Sel." + pos_sel_extensions[i])).get().replace(" ", "_")
        LookupRow = make_lookup_row(col_suffixes=col_suffixes, prefix=prefix, row_number=i)           # Possible to use one row class to instantiate all rows of the table? (row_number changes)

        defn[pos_name] = (LookupRow, "", {"name" : "row{i}"})
        
    class LookupTable(Device):
        
        rows = DynamicDeviceComponent(defn)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)


        def get_table(self):
            table = {}
            for row in defn:
                curr_row = {}
                for axis in col_suffixes:
                    curr_row[(axis.replace(":", "_"))] = self.rows.read()[self.name + "_rows_" + row + "_axes_" + (axis.replace(":", "_"))]["value"]
                table[row] = curr_row
            return table
        

    return LookupTable



def make_motors (*args, prefix : str, col_suffixes : list[str], **kwargs):
    defn = OrderedDict()

    for col_suffix in col_suffixes:
        valid_key_name = (col_suffix).replace(":", "_") 
        defn[valid_key_name] = (EpicsMotor, (prefix + "-" + col_suffix + "}Mtr"), {})
    
    class LookupMotors(Device):
        motors = DynamicDeviceComponent(defn)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def get_motors(self):
            motors = {}
            for axis in defn:
                curr_axis = {}
                curr_axis["value"] = getattr(self.motors, axis).user_readback.get()
                curr_axis["setpoint"] = getattr(self.motors, axis).user_setpoint.get()
                
                motors[axis] = curr_axis
            return motors

    return LookupMotors



def make_device_with_lookup_table(prefix : str, pos_sel_dev: str, num_rows: int, col_suffixes: list[str],  precision : int = 20, *args, **kwargs):

    
    lookup_class = make_lookup_table(pos_sel_dev=pos_sel_dev, num_rows=num_rows, col_suffixes=col_suffixes, prefix=prefix)
    motors_class = make_motors(prefix=prefix, col_suffixes=col_suffixes)

    class DeviceWithLookup(Device):

        pos_lookup = Cpt(lookup_class, "")
        motors = Cpt(motors_class, "")


        pos_sel = Cpt(EpicsSignal, prefix + "-" + pos_sel_dev + "}Pos-Sel", kind = 'hinted', string=True)
    

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.precision = precision
        
        def lookup(self, name : str):
            lookup = self.pos_lookup.get_table()

            new_name = ("Row_" + name).replace(" ", "_")

            for pos_name in lookup:
                if pos_name == new_name:
                    return lookup[pos_name]
            raise ValueError (f"Could not find {name} in lookup table")
                
        def get_all_positions(self):
            lookup = self.pos_lookup.get_table()
            length = len(lookup)
            print(f"\n  {length} possible positions:")
            print("----------------------------------")
            for pos_name in lookup:
                if lookup[pos_name] != "Undefined":
                    print(f'    {pos_name:_<15} : {tuple(lookup[pos_name].values())}')

        def where_am_i(self):
            lookup = self.pos_lookup.get_table()
            motors = self.motors.get_motors()
            pos_sel_val = self.pos_sel.get()

            for axis in motors:
                print("Motor " + axis + " value: " + str(round(motors[axis]["value"], self.precision)))
            print("\nPos-Sel value: ", pos_sel_val)

            matched_entry = ""

            for index in range(len(lookup)):
                match = True
                lookup_entry_positions = list(lookup.values())[index]
                
                lookup_entry_name = list(lookup.keys())[index]
                for axis_index in range(len(range(len(lookup_entry_positions)))):
                    axis = list(motors.keys())[axis_index]
                    axis_value = motors[axis]["value"]
                    lookup_value = lookup_entry_positions[axis]
                    if round(axis_value, self.precision) != round(lookup_value, self.precision):
                        match = False

                if match == True:
                    matched_entry = lookup_entry_name.replace("Row_", "")
                    break
            
            pos_sel_match = pos_sel_val == matched_entry

            
            if (matched_entry == "") or (pos_sel_match == False):
                print("\nYour motor values and/or Pos-Sel do not match one of the preset positions")
                print("Use " + self.name + ".get_all_positions() to see all preset positions.")
            else:
                print("\nYour motor values matched the position: " + matched_entry + " = ", self.lookup(matched_entry))

        




        def set_pos_sel(self, pos: str | tuple):
            lookup = self.pos_lookup.get_table()

            if isinstance(pos, tuple):
                for pos_name in lookup:
                    print("pos: " + pos + " pos_name: " + pos_name)
                    pos_tuple = tuple(lookup[pos_name].values())
                    match = True
                    for axis_index in range(len(pos_tuple) - 1):
                        if float(pos[axis_index]) != float(pos_tuple[axis_index]):
                            print("<" + str(float(pos[axis_index]))  + "   " + str(float(pos_tuple[axis_index])) + ">")
                            match = False
                    if match == True:
                        pos = pos_name
                        break

            
            return self.pos_sel.set(str(pos))
        
        def update_pos(self, status):
            
            motors = self.motors.get_motors()
            motor_values = tuple([motors[axis]["setpoint"] for axis in motors])
            print(motor_values)
            self.set_pos_sel(motor_values)
        
        def set(self, size : str | tuple):

            if isinstance(size, str):
                values = list(self.lookup(size).values())
            else: values = list(size)
            

            motors = self.motors.get_motors()
            # {'Ax_X': {'value': 0.0005 100000000011207, 'setpoint': 0.00043000000000059657},
            #  'Ax_Y': {'value': -0.0011199999999998989, 'setpoint': 0.0}}


            axes = list(motors.keys())
            # ['Ax_X', 'Ax_Y']

            self.set_pos("Undefined")
            move_status = getattr(self.motors.motors, axes[0]).set(values[0])

            for axis_index in range(1, len(axes)):
                curr_motor = getattr(self.motors.motors, axes[axis_index])      # curr_motor is an EpicsMotor signal
                move_status = move_status & curr_motor.set(values[axis_index])

            move_status.add_callback(self.update_pos)
            return move_status

            
    return DeviceWithLookup

