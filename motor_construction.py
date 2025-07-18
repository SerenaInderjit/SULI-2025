from ophyd import EpicsMotor, sim, Device, Kind
from ophyd import Component as Cpt, FormattedComponent as FCpt
from ophyd.sim import make_fake_device, SynAxis, FakeEpicsSignal
from ophyd.signal import EpicsSignal
from ophyd.status import MoveStatus, wait
from ophyd.device import create_device_from_components
from ophyd.ophydobj import OphydObject
from bluesky.plans import count, scan
from bluesky.plan_stubs import mv
from bluesky.simulators import summarize_plan
from bluesky.preprocessors import SupplementalData
from collections import OrderedDict
from collections.abc import Iterable, MutableSequence
from ophyd.utils import (
    ExceptionBundle,
    RedundantStaging,
    doc_annotation_forwarder,
    getattrs,
    underscores_to_camel_case,
)


# Find out all 16 extensions and add them
pos_sel_extensions = ["", "ONST", "TWST", "THST", "FRST", "FVST", "SXST", "SVST", "EIST", "NIST" ,"TEST"]


def make_lookup_row(*args, col_suffixes: list[str], col_names : list[str], prefix : str, pos_sel_dev : str, row_number : int, **kwargs):

    defn = OrderedDict()

    for i in range(len(col_suffixes)):
        pv = (prefix + "-" + col_suffixes[i] + "}Val:" + str(row_number) + "-SP")

        
        defn[col_names[i]] = (EpicsSignal, pv, {})

  
    class LookupRow(Device):

       
        values = DynamicDeviceComponent(defn)
        key = Cpt(EpicsSignal, ((prefix + "-" + pos_sel_dev + "}Pos-Sel." + pos_sel_extensions[row_number])))

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)       
            
        
        def get_row(self):
            row = {}
            row_key = self.key.get()
            row[row_key] = {}
            for key in defn:
                row[row_key][key] = getattr(self.values, key).get()
            return row

    return LookupRow


def make_lookup_table(*args, pos_sel_dev : str, num_rows : int, col_suffixes : list[str], col_names : list[str], prefix : str, **kwargs):
    defn = OrderedDict()
    
    for i in range(1, num_rows + 1):
        
        LookupRow = make_lookup_row(col_suffixes=col_suffixes, col_names=col_names, prefix=prefix, pos_sel_dev = pos_sel_dev, row_number=i)
        defn[f"row{i}"] = (LookupRow, "", {"name" : f"row{i}"})

    return defn


def get_motor_components(*args, prefix : str, col_suffixes : list[str], col_names : list[str], **kwargs):
    defn = OrderedDict()

    for i in range(len(col_suffixes)):
        
        defn[col_names[i]] = Cpt(EpicsMotor, (prefix + "-" + col_suffixes[i] + "}Mtr"), name = col_names[i])

    return defn

def get_motor_signals(*args, prefix : str, col_suffixes : list[str], col_names : list[str], **kwargs):
    defn = OrderedDict()

    for i in range(len(col_suffixes)):
        
        defn[col_names[i]] = EpicsMotor((prefix + "-" + col_suffixes[i] + "}Mtr"), name = col_names[i])

    return defn

def make_lookup_table(*args, pos_sel_dev : str, num_rows : int, col_suffixes : list[str], col_names : list[str], prefix : str, **kwargs):
    defn = OrderedDict()
    
    
    for i in range(1, num_rows + 1):
        
        LookupRow = make_lookup_row(col_suffixes=col_suffixes, col_names=col_names, prefix=prefix, pos_sel_dev = pos_sel_dev, row_number=i)
        defn[f"row{i}"] = (LookupRow, "", {"name" : f"row{i}"})

    return OrderedDict(pos_lookup = DynamicDeviceComponent(defn))




def make_device_with_lookup_table(prefix : str, pos_sel_dev: str, num_rows: int, col_suffixes: list[str],  col_names : list[str], precision : int = 20, *args, **kwargs):


    pos_sel = OrderedDict(pos_sel = Cpt(EpicsSignal, prefix + "-" + pos_sel_dev + "}Pos-Sel", kind = 'hinted', string=True))

    motor_components = get_motor_components(prefix=prefix, col_suffixes=col_suffixes, col_names = col_names)
    motor_signals = get_motor_signals(prefix=prefix, col_suffixes=col_suffixes, col_names = col_names)


    pos_lookup = make_lookup_table(prefix=prefix, pos_sel_dev=pos_sel_dev, num_rows=num_rows, col_suffixes=col_suffixes, col_names = col_names)

    def __init__(self, *args, **kwargs):
        super(type(self), self).__init__(*args, **kwargs)
        self.precision = precision

    def get_motors(self):
        motors = {}
        for key in motor_signals:
            motor = {}
            motor["value"] = motor_signals[key].user_readback.get()
            motor["setpoint"] = motor_signals[key].user_setpoint.get()
            motors[key] = motor
        return motors
    
    def get_table(self):
        table = {}
        for i in range(1, num_rows + 1):
            key = f"row{i}"
            row = getattr(self.pos_lookup, key).get_row()
            row_key = next(iter(row))
            table[row_key] = row[row_key]
        return table
    
    def get_all_positions(self):
        lookup = self.get_table()
        length = len(lookup)
        print(f"\n  {length} possible positions:")
        print("----------------------------------")
        for pos_name in lookup:
            if lookup[pos_name] != "Undefined":
                print(f'    {pos_name:_<15} : {tuple(lookup[pos_name].values())}')

    def lookup(self, name : str):
        lookup = self.get_table()

        new_name = (name)

        for pos_name in lookup:
            if pos_name == new_name:
                return lookup[pos_name]
        raise ValueError (f"Could not find {name} in lookup table")
    
    def lookup_by_values(self, pos : tuple[float]):
        lookup = self.get_table()
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
    
    def where_am_i(self):
        motors = self.get_motors()
        pos_sel_val = self.pos_sel.get()

        for axis in motors:
            print("Motor " + axis + " value: " + str(round(motors[axis]["value"], self.precision)))
        print("\nPos-Sel value: ", pos_sel_val)


        motor_values = tuple([motors[motor]['value'] for motor in motors.keys()])
        try:
            matched_entry = self.lookup_by_values(motor_values)
            
        except ValueError:
            matched_entry = ""

        print("matched_entry", matched_entry)
        
        if (matched_entry == "") or (pos_sel_val != matched_entry):
            print("\nYour motor values and/or Pos-Sel do not match one of the preset positions")
            print("Use " + self.name + ".get_all_positions() to see all preset positions.")
        else:
            print("\nYour motor and pos-sel values matched the position: " + matched_entry + " = ", self.lookup(matched_entry))

    def set_pos_sel(self, pos: str | tuple):
        if isinstance(pos, tuple):
            pos = self.lookup_by_values(pos)
        
        return self.pos_sel.set(str(pos))
    
    def sync_pos_sel(self, status = None):
        self.set_pos_sel("Undefined")
        motors = self.get_motors()
        motor_values = tuple([motors[axis]["setpoint"] for axis in motors])
        self.set_pos_sel(motor_values)

    def set(self, size : str | tuple):

        if isinstance(size, str):
            values = list(self.lookup(size).values())
        else: values = list(size)
        

        motors = self.get_motors()
        axes = list(motors.keys())

        self.set_pos_sel("Undefined")
        move_status = getattr(self.motors, axes[0]).set(values[0])

        for axis_index in range(1, len(axes)):
            curr_motor = getattr(self.motors, axes[axis_index])
            move_status = move_status & curr_motor.set(values[axis_index])

        move_status.add_callback(self.sync_pos_sel)
        return move_status
    
    docstring = (f"DeviceWithLookup Device")

    read_attrs_names = ["pos_lookup", "pos_sel"].extend(col_names)

    clsdict = OrderedDict(
            __doc__=docstring,
            _default_read_attrs=read_attrs_names,
            _default_configuration_attrs=[],
            __init__ = __init__,
            get_motors = get_motors,
            get_table = get_table,
            get_all_positions = get_all_positions,
            lookup = lookup,
            lookup_by_values = lookup_by_values,
            where_am_i = where_am_i,
            set_pos_sel = set_pos_sel,
            sync_pos_sel = sync_pos_sel,
            set = set
        )

    clsdict = clsdict | motor_components | pos_lookup | pos_sel
    
    DeviceWithLookup = type("DeviceWithLookup", (Device, ), clsdict, **{})

    return DeviceWithLookup

    

sltclass = make_device_with_lookup_table(prefix="XF:23ID1-OP{Slt:3", pos_sel_dev="LUT", num_rows=10, col_suffixes=["Ax:X","Ax:Y"], col_names = ["x", "y"], precision=3)

slt3WithLookup = sltclass(name = "slt3WithLookup")


