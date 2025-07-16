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



# Find out all 16 extensions and add them
pos_sel_extensions = ["", "ONST", "TWST", "THST", "FRST", "FVST", "SXST", "SVST", "EIST", "NIST" ,"TEST"]


def make_lookup_row(*args, col_suffixes: list[str], prefix : str, pos_sel_dev : str, row_number : int, **kwargs):

    defn = OrderedDict()

    # Dynamic number of signals to represent the number of columns
    for i in range(len(col_suffixes)):
        pv = (prefix + "-" + col_suffixes[i] + "}Val:" + str(row_number) + "-SP")

        
        defn[f"motor{i}"] = (EpicsSignal, pv, {})


    # defn = {"motor1" : (EpicsSignal, <X_val_pv>, {}),
    #         "motor2" : (EpicsSignal, <Y_val_pv>, {}), 
    #           ...}
  
    class LookupRow(Device):

       
        row_values = DynamicDeviceComponent(defn)
        row_key = Cpt(EpicsSignal, ((prefix + "-" + pos_sel_dev + "}Pos-Sel." + pos_sel_extensions[row_number])))

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)       
        
        def get_row(self):
            row = {}
            row_key_value = self.row_key.get()
            row[row_key_value] = {}
            for key in defn:
                row[row_key_value][key] = getattr(self.row_values, key).get()
            return row

    return LookupRow



def make_lookup_table(*args, pos_sel_dev : str, num_rows : int, col_suffixes : list[str], prefix : str, **kwargs):
    defn = OrderedDict()
    
    # Dynamic number of signals to represent the number of rows
    for i in range(1, num_rows + 1):
        
        LookupRow = make_lookup_row(col_suffixes=col_suffixes, prefix=prefix, pos_sel_dev = pos_sel_dev, row_number=i)
        defn[f"row{i}"] = (LookupRow, "", {"name" : f"row{i}"})


    # defn = {"row1" : (LookupRow, "", {"name" : "row1"}),
    #         "row2" : (LookupRow, "", {"name" : "row2"}),
    #          ...}
        
    class LookupTable(Device):
        
        rows = DynamicDeviceComponent(defn)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)


        def get_table(self):
            table = {}
            for key in defn:
                row = getattr(self.rows, key).get_row()
                row_key = next(iter(row))
                table[row_key] = row[row_key]
            return table
        

    return LookupTable



def make_motors (*args, prefix : str, col_suffixes : list[str], **kwargs):
    defn = OrderedDict()


    for i in range(len(col_suffixes)):
        
        defn[f"motor{i}"] = (EpicsMotor, (prefix + "-" + col_suffixes[i] + "}Mtr"), {})
    

    # defn = {"motor0" : (EpicsMotor, <mtr0_pv>, {}),
    #         "motor1" : (EpicsMotor, <mtr1_pv>, {}),
    #          ...}


    class LookupMotors(Device):
        motors = DynamicDeviceComponent(defn)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def get_motors(self):
            motors = {}
            for key in defn:
                motor = {}
                motor["value"] = getattr(self.motors, key).user_readback.get()
                motor["setpoint"] = getattr(self.motors, key).user_setpoint.get()
                
                motors[key] = motor
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
            self.motor_list = [getattr(self.motors.motors, motor) for motor in self.motors.get_motors().keys()]
        

        def lookup(self, name : str):
            lookup = self.pos_lookup.get_table()

            new_name = ("Row_" + name).replace(" ", "_")

            for pos_name in lookup:
                if pos_name == new_name:
                    return lookup[pos_name]
            raise ValueError (f"Could not find {name} in lookup table")
                

        def lookup_by_values(self, pos : tuple[float]):
            lookup = self.pos_lookup.get_table()
            matched_entry = ""

            for lookup_index in range(len(lookup)):
                match = True
                lookup_entry_key = list(lookup.keys())[lookup_index]
                lookup_entry_values = list(lookup[lookup_entry_key].values())

                for axis_index in range(len(pos)):
                    if round(pos[axis_index], self.precision) != round(lookup_entry_values[axis_index], self.precision):
                        match = False                    

                if match == True:
                    matched_entry = lookup_entry_key
                    break

            if matched_entry == "":
                raise ValueError (f"Could not find {pos} in lookup")
            else:
                return matched_entry

        def get_all_positions(self):
            lookup = self.pos_lookup.get_table()
            length = len(lookup)
            print(f"\n  {length} possible positions:")
            print("----------------------------------")
            for pos_name in lookup:
                if lookup[pos_name] != "Undefined":
                    print(f'    {pos_name:_<15} : {tuple(lookup[pos_name].values())}')

        def where_am_i(self):
            motors = self.motors.get_motors()
            pos_sel_val = self.pos_sel.get()

            for axis in motors:
                print("Motor " + axis + " value: " + str(round(motors[axis]["value"], self.precision)))
            print("\nPos-Sel value: ", pos_sel_val)


            motor_values = tuple([motors[motor]['value'] for motor in motors.keys()])
            try:
                matched_entry = self.lookup_by_values(motor_values)
            except ValueError:
                matched_entry = ""

            
            if (matched_entry == "") or (pos_sel_val != matched_entry):
                print("\nYour motor values and/or Pos-Sel do not match one of the preset positions")
                print("Use " + self.name + ".get_all_positions() to see all preset positions.")
            else:
                print("\nYour motor values matched the position: " + matched_entry + " = ", self.lookup(matched_entry))


        def set_pos_sel(self, pos: str | tuple):
            if isinstance(pos, tuple):
                pos = self.lookup_by_values(pos)
            
            return self.pos_sel.set(str(pos))
        
        def sync_pos_sel(self, status = None):
            motors = self.motors.get_motors()
            motor_values = tuple([motors[axis]["setpoint"] for axis in motors])
            self.set_pos_sel(motor_values)
        
        def set(self, size : str | tuple):

            if isinstance(size, str):
                values = list(self.lookup(size).values())
            else: values = list(size)
            

            motors = self.motors.get_motors()
            axes = list(motors.keys())

            self.set_pos_sel("Undefined")
            move_status = getattr(self.motors.motors, axes[0]).set(values[0])

            for axis_index in range(1, len(axes)):
                curr_motor = getattr(self.motors.motors, axes[axis_index])
                move_status = move_status & curr_motor.set(values[axis_index])

            move_status.add_callback(self.sync_pos_sel)
            return move_status

            
    return DeviceWithLookup

sltclass = make_device_with_lookup_table(prefix="XF:23ID1-OP{Slt:3", pos_sel_dev="LUT", num_rows=10, col_suffixes=["Ax:X", "Ax:Y"], precision=3)
slt3WithLookup = sltclass(name = "slt3WithLookup")

