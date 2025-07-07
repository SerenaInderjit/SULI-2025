from ophyd import EpicsMotor, sim, Device
from ophyd import Component as Cpt, FormattedComponent as FCpt
from ophyd.sim import make_fake_device, SynAxis
from ophyd.signal import EpicsSignal
from ophyd.status import MoveStatus, wait
from ophyd.device import DynamicDeviceComponent
from ophyd.ophydobj import OphydObject
from bluesky.plans import count, scan
from bluesky.plan_stubs import mv
from bluesky.simulators import summarize_plan
from bluesky.preprocessors import SupplementalData

from collections import deque

class LookupPair(Device):
    pair_name = FCpt(EpicsSignal, "{prefix}{self.name_postfix}", kind="config")
    pair_val = FCpt(EpicsSignal, "{prefix}{self.val_postfix}", kind="config")

    
    
    def __init__(self, *args, name_postfix : str, val_postfix : str, **kwargs):
        self.name_postfix = name_postfix
        self.val_postfix = val_postfix
        super().__init__(*args, **kwargs)
        


from collections import OrderedDict

        


class MotorWithLookup(Device):
    defn = OrderedDict({
        "pair1": (LookupPair, "", {"name_postfix" : "Pos-Sel.ONST", "val_postfix" : "Val:1-SP"}),
        "pair2": (LookupPair, "", {"name_postfix" : "Pos-Sel.TWST", "val_postfix" : "Val:2-SP"}),
        "pair3": (LookupPair, "", {"name_postfix" : "Pos-Sel.THST", "val_postfix" : "Val:3-SP"}),
        "pair4": (LookupPair, "", {"name_postfix" : "Pos-Sel.FRST", "val_postfix" : "Val:4-SP"}),
        "pair5": (LookupPair, "", {"name_postfix" : "Pos-Sel.FVST", "val_postfix" : "Val:5-SP"}),
        "pair6": (LookupPair, "", {"name_postfix" : "Pos-Sel.SXST", "val_postfix" : "Val:6-SP"}),
        "pair7": (LookupPair, "", {"name_postfix" : "Pos-Sel.SVST", "val_postfix" : "Val:7-SP"}),
        "pair8": (LookupPair, "", {"name_postfix" : "Pos-Sel.EIST", "val_postfix" : "Val:8-SP"}),
        "pair9": (LookupPair, "", {"name_postfix" : "Pos-Sel.NIST", "val_postfix" : "Val:9-SP"}),
        "pair10": (LookupPair, "", {"name_postfix" : "Pos-Sel.TEST", "val_postfix" : "Val:10-SP"})
    })

    pos_lookup = DynamicDeviceComponent(defn)
    motor = Cpt(EpicsMotor, "Mtr")
    pos_sel = Cpt(EpicsSignal, "Pos-Sel", kind = 'hinted', string=True)
    

    def __init__(self, prefix : str, *args, name = "", **kwargs):
        super().__init__(prefix, *args, name=name, **kwargs)
        self.readings = deque(maxlen=5)

    def lookup(self, name: str) -> float:
        pair_lst = list(self.pos_lookup.get())
        for pair in pair_lst:
            if pair.pair_name == name:
                return pair.pair_val       
        raise ValueError (f"Could not find {name} in lookup table")
    
    def get_all_positions(self):
        pair_lst = list(self.pos_lookup.get())
        length = len(pair_lst)
        print(f"{length} possible positions:")
        print("----------------------------------")
        for pair in pair_lst:
            if pair.pair_name != "Undefined":
                print(f'    {pair.pair_name:_<15} : {pair.pair_val}')


    def set_pos(self, pos: str | float):
        pair_lst = list(self.pos_lookup.get())
        val = pos
        if  not isinstance(val, str):
            for pair in pair_lst:
                if float(pair.pair_val) == float(val):
                    val = pair.pair_name
                    break
        return self.pos_sel.set(str(val))


    def update_pos(self, status):
        curr_pos = (self.motor.read()[self.name + '_motor_user_setpoint']['value'])
        self.set_pos(curr_pos)


    def set(self, pos: str | float):
        if isinstance(pos, str):
            val = self.lookup(pos)
        else:
            val = pos

        self.set_pos("Undefined")
        mv_sts = self.motor.set(val)
        mv_sts.add_callback(self.update_pos)
    
        
        return mv_sts



class SlitsWithLookup(Device):

    defn_x = OrderedDict({
        "pair1": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.ONST", "val_postfix" : "-MC10}Val:1-SP"}),
        "pair2": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.TWST", "val_postfix" : "-MC10}Val:2-SP"}),
        "pair3": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.THST", "val_postfix" : "-MC10}Val:3-SP"}),
        "pair4": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.FRST", "val_postfix" : "-MC10}Val:4-SP"}), 
        "pair5": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.FVST", "val_postfix" : "-MC10}Val:5-SP"}), 
        "pair6": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.SXST", "val_postfix" : "-MC10}Val:6-SP"}), 
        "pair7": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.SVST", "val_postfix" : "-MC10}Val:7-SP"}), 
        "pair8": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.EIST", "val_postfix" : "-MC10}Val:8-SP"}), 
        "pair9": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.NIST", "val_postfix" : "-MC10}Val:9-SP"}), 
        "pair10": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.TEST", "val_postfix" : "-MC10}Val:10-SP"})

    })
    defn_y = OrderedDict({
        "pair1": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.ONST", "val_postfix" : "-Ax:Y}Val:1-SP"}),
        "pair2": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.TWST", "val_postfix" : "-Ax:Y}Val:2-SP"}),
        "pair3": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.THST", "val_postfix" : "-Ax:Y}Val:3-SP"}),
        "pair4": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.FRST", "val_postfix" : "-Ax:Y}Val:4-SP"}),
        "pair5": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.FVST", "val_postfix" : "-Ax:Y}Val:5-SP"}), 
        "pair6": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.SXST", "val_postfix" : "-Ax:Y}Val:6-SP"}), 
        "pair7": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.SVST", "val_postfix" : "-Ax:Y}Val:7-SP"}), 
        "pair8": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.EIST", "val_postfix" : "-Ax:Y}Val:8-SP"}), 
        "pair9": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.NIST", "val_postfix" : "-Ax:Y}Val:9-SP"}), 
        "pair10": (LookupPair, "", {"name_postfix" : "-MC10}Pos-Sel.TEST", "val_postfix" : "-Ax:Y}Val:10-SP"})
    })


    pos_lookup_x = DynamicDeviceComponent(defn_x)
    pos_lookup_y = DynamicDeviceComponent(defn_y)
    x = Cpt(EpicsMotor, '-Ax:X}Mtr', name='x')
    y = Cpt(EpicsMotor, '-Ax:Y}Mtr', name='y')
    pos_sel = Cpt(EpicsSignal, "-MC10}Pos-Sel", kind='hinted', string=True)


    def __init__(self, prefix : str, *args, name = "", **kwargs):
        super().__init__(prefix, *args, name=name, **kwargs)

    def get_lookup(self):
        lst_x = list(self.pos_lookup_x.get())
        lst_y = list(self.pos_lookup_y.get())
        
        lookup = dict((lst_x[k].pair_name, (lst_x[k].pair_val, lst_y[k].pair_val)) for k in range(len(lst_x)) if lst_x[k].pair_name != "Undefined")
        return lookup

    def lookup(self, name: str):
        lookup = self.get_lookup
        
        for pair_name in lookup:
            if pair_name == name:
                return lookup[pair_name]     
        raise ValueError (f"Could not find {name} in lookup table")

    
    
    def get_all_sizes(self):
        lookup = self.get_lookup()

        length = len(lookup)

        print(f"{length} possible sizes:")
        print("----------------------------------")
        for pair_name in lookup:
            print(f'    {pair_name:_<10} : {lookup[pair_name]}')


    def set_pos(self, pos: str | tuple):
        lookup = self.get_lookup()

        val = pos
        if isinstance(val, tuple):
            for pair_name in lookup:
                pair_val = lookup[pair_name]
                if (float(pos[0]) == float(pair_val[0])) & (float(pos[1]) == float(pair_val[1])):
                    val = pair_name
        return self.pos_sel.set(str(val))
    

    def update_pos(self, status):
        _xpos = (self.x.read()[(self.name) + '_x_user_setpoint']['value'])
        _ypos = (self.y.read()[(self.name) + '_y_user_setpoint']['value'])

        self.set_pos((_xpos, _ypos))

    def set(self, size : str | tuple = None):
        if size is None:
            _xpos = float(self.x.read()[(self.name) + '_x_user_setpoint']['value'])
            _ypos = float(self.y.read()[(self.name) + '_y_user_setpoint']['value'])

            lst_x = list(self.pos_lookup_x.get())
            lst_y = list(self.pos_lookup_y.get())
            
            holes_reverse = dict(((lst_x[k].pair_val, lst_y[k].pair_val), lst_x[k].pair_name) for k in range(len(lst_x)) if lst_x[k].pair_name != "Undefined")
            
            try:
                _size_slt3_pinhole = holes_reverse[(_xpos, _ypos)]
                print(f'{_size_slt3_pinhole}um pinhole at {self.name}: {self.x.name} = {_xpos:.4f}, {self.y.name} = {_ypos:.4f}') 
            except KeyError:
                print(f'Unknown configuration: {self.x.name} = {_xpos:.4f}, {self.y.name} = {_ypos:.4f}') 


        else:
            if isinstance(size, str):
                x_pos, y_pos = self.lookup(str(size))
            else:
                x_pos, y_pos = size

            print('Moving to {} um {}'.format(size, self.name))
            
            self.set_pos("Undefined")
            x_sts = self.x.set(x_pos)
            y_sts = self.y.set(y_pos)
            mv_sts = x_sts & y_sts
            mv_sts.add_callback(self.update_pos)


            return x_sts & y_sts
        
