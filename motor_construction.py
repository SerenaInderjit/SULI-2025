import ophyd
from ophyd import EpicsMotor, sim, Device, Kind
from ophyd import Component as Cpt, FormattedComponent as FCpt, DynamicDeviceComponent
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


pos_sel_extensions = ["", "ONST", "TWST", "THST", "FRST", "FVST", "SXST", "SVST", "EIST", "NIST" ,"TEST", "ELST", "TVST", "TTST", "FTST", "FFST"] 


def make_lookup_row(*args, pos_sel_dev : str, col_suffixes: list[str], col_names : list[str], row_number : int, **kwargs):

    defn = OrderedDict({
        col_name: (EpicsSignal, "-" + col_suffix.replace("-", "").replace("}Mtr", "") + "}Val:" + str(row_number) + "-SP", {})
        for col_name, col_suffix in zip(col_names, col_suffixes)
    })
    
  
    class LookupRow(Device):

       
        values = DynamicDeviceComponent(defn)
        key = Cpt(EpicsSignal, (("-" + pos_sel_dev + "}Pos-Sel." + pos_sel_extensions[row_number])))

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


def get_lookup_defn(*args, pos_sel_dev : str, num_rows : int, col_suffixes : list[str], col_names : list[str], **kwargs):
    defn = OrderedDict()
    
    for i in range(1, num_rows + 1):
        
        LookupRow = make_lookup_row(col_suffixes=col_suffixes, col_names=col_names, pos_sel_dev = pos_sel_dev, row_number=i)
        defn[f"row{i}"] = (LookupRow, "", {"name" : f"row{i}"})

    return DynamicDeviceComponent(defn)


def make_device_with_lookup_table(cls : Device, pos_sel_dev: str, num_rows: int, precision : int = 20, *args, **kwargs):

    # Gather motor components, column names, and column suffixes from cls
    motor_components = OrderedDict()
    col_names = []
    col_suffixes = []
    for key in cls.__dict__['component_names']:
        signal = cls.__dict__[key]
        if (cls.__dict__[key].cls == EpicsMotor):
            motor_components[key] = cls.__dict__[key]
            col_names.append(key)
            col_suffixes.append(signal.suffix)

    
    pos_lookup = OrderedDict(pos_lookup = get_lookup_defn(pos_sel_dev=pos_sel_dev, num_rows=num_rows, col_suffixes=col_suffixes, col_names = col_names))
    pos_sel = OrderedDict(pos_sel = Cpt(EpicsSignal, "-" + pos_sel_dev + "}Pos-Sel", kind = 'hinted', string=True))

    def __init__(self, *args, **kwargs):
        super(type(self), self).__init__(*args, **kwargs)
        self.precision = precision


    def _get_motors(self):
        motors = {}
        for key in motor_components:
            motor = {}
            motor["value"] = getattr(self, key).user_readback.get()
            motor["setpoint"] = getattr(self, key).user_setpoint.get()
            motors[key] = motor
        return motors
    
    def _get_table(self):
        table = {}
        for i in range(1, num_rows + 1):
            key = f"row{i}"
            row = getattr(self.pos_lookup, key).get_row()
            row_key = next(iter(row))
            table[row_key] = row[row_key]
        return table
    
    def get_all_positions(self):
        lookup = self._get_table()
        length = len(lookup)
        print(f"\n  {length} Possible Positions:")
        print("----------------------------------")
        for pos_name in lookup:
            if lookup[pos_name] != "Undefined":
                print(f'    {pos_name:_<15} : {tuple(lookup[pos_name].values())}')

    def lookup(self, name : str):
        lookup = self._get_table()

        new_name = (name)

        for pos_name in lookup:
            if pos_name == new_name:
                return lookup[pos_name]
        raise ValueError (f"Could not find {name} in lookup table")
    
    def lookup_by_values(self, pos : tuple[float]):
        lookup = self._get_table()
        matched_entry = None
        for lookup_index in range(len(lookup)):
            
            lookup_entry_key = list(lookup.keys())[lookup_index]
            lookup_entry_values = list(lookup[lookup_entry_key].values())
            match = all(round(pos[axis_index], self.precision) == round(lookup_entry_values[axis_index], self.precision) for axis_index in range(len(pos)))
            
                    
            if match == True:
                matched_entry = lookup_entry_key
                break

        if matched_entry == None:
            raise ValueError (f"Could not find {pos} in lookup")
        else:
            return matched_entry    
    
    def where_am_i(self):
        motors = self._get_motors()
        pos_sel_val = self.pos_sel.get()

        for axis in motors:
            print("Motor " + axis + " value: " + str(round(motors[axis]["value"], self.precision)))
        print("\nPos-Sel value: ", pos_sel_val)


        motor_values = tuple([motors[motor]['value'] for motor in motors.keys()])
        try:
            matched_entry = self.lookup_by_values(motor_values)
            
        except ValueError:
            matched_entry = None

        
        if (matched_entry is None) or (pos_sel_val != matched_entry):
            print("\nYour motor values and/or Pos-Sel do not match one of the preset positions")
            print("Use " + self.name + ".get_all_positions() to see all preset positions.")
        else:
            print("\nYour motor and pos-sel values matched the position: " + matched_entry + " = ", self.lookup(matched_entry))

    def set_pos_sel(self, pos: str | tuple):
        if isinstance(pos, tuple):
            pos = self.lookup_by_values(pos)
        
        return self.pos_sel.set(str(pos))
    
    def _sync_pos_sel(self, status = None):
        self.set_pos_sel("Undefined")
        motors = self._get_motors()
        motor_values = tuple([motors[axis]["setpoint"] for axis in motors])
        self.set_pos_sel(motor_values)

    def set(self, size : str | tuple):

        if isinstance(size, str):
            values = list(self.lookup(size).values())
        else: values = list(size)
        

        motors = self._get_motors()
        axes = list(motors.keys())

        self.set_pos_sel("Undefined")
        init_motor = getattr(self, axes[0])
        move_status = init_motor.set(values[0])

        for axis_index in range(1, len(axes)):
            curr_motor = getattr(self, axes[axis_index])
            move_status = move_status & curr_motor.set(values[axis_index])

        move_status.add_callback(self._sync_pos_sel)
        return move_status
    
    docstring = (f"DeviceWithLookup Device")

    read_attrs_names = ["pos_lookup", "pos_sel"].extend(col_names)

    clsdict = OrderedDict(
            __doc__=docstring,
            _default_read_attrs=read_attrs_names,
            _default_configuration_attrs=[],
            __init__ = __init__,
            _get_motors = _get_motors,
            _get_table = _get_table,
            get_all_positions = get_all_positions,
            lookup = lookup,
            lookup_by_values = lookup_by_values,
            where_am_i = where_am_i,
            set_pos_sel = set_pos_sel,
            _sync_pos_sel = _sync_pos_sel,
            set = set
        )

    clsdict = clsdict | motor_components | pos_sel | pos_lookup
    
    DeviceWithLookup = type("DeviceWithLookup", (cls,), clsdict, **{})

    return DeviceWithLookup

slt3WithLookup = make_device_with_lookup_table(SlitsXY, pos_sel_dev="LUT", num_rows=10, precision=3)('XF:23ID1-OP{Slt:3', name = "slt3WithLookup")




