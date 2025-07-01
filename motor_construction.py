from ophyd import EpicsMotor, sim, Device
from ophyd import Component as Cpt, FormattedComponent as FCpt
from ophyd.sim import make_fake_device, SynAxis
from ophyd.signal import EpicsSignal
from ophyd.status import MoveStatus
from ophyd.device import DynamicDeviceComponent
from bluesky.plans import count, scan
from bluesky.plan_stubs import mv
from bluesky.simulators import summarize_plan
from bluesky.preprocessors import SupplementalData

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
    pos_sel = Cpt(EpicsSignal, "Pos-Sel")
    

    def __init__(self, prefix : str, *args, name = "", **kwargs):
        super().__init__(prefix, *args, name=name, **kwargs)

    

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


    def set(self, pos: str | float):
        if isinstance(pos, str):
            val = self.lookup(pos)
        else:
            val = pos
        mv_sts = self.motor.set(val)
        
        
        # if (mv_sts.success):
        #     self.set_pos(pos)
        # else:
        #     self.set_pos("Undefined")


        print((self.motor.read()[(self.name) + '_motor_user_setpoint'][value]))
        # self.set_pos(self.motor.read()[(self.name) + '_user_setpoint'][value])
        return mv_sts


class SlitsWithLookup(Device):

    defn_x = OrderedDict({
        "pair1": (LookupPair, "", {"name_postfix" : "-Ax:X}Pos-Sel.ONST", "val_postfix" : "-Ax:X}Val:1-SP"}),
        "pair2": (LookupPair, "", {"name_postfix" : "-Ax:X}Pos-Sel.TWST", "val_postfix" : "-Ax:X}Val:2-SP"}),
        "pair3": (LookupPair, "", {"name_postfix" : "-Ax:X}Pos-Sel.THST", "val_postfix" : "-Ax:X}Val:3-SP"}),
        "pair4": (LookupPair, "", {"name_postfix" : "-Ax:X}Pos-Sel.FRST", "val_postfix" : "-Ax:X}Val:4-SP"})
    })
    defn_y = OrderedDict({
        "pair1": (LookupPair, "", {"name_postfix" : "-Ax:Y}Pos-Sel.ONST", "val_postfix" : "-Ax:Y}Val:1-SP"}),
        "pair2": (LookupPair, "", {"name_postfix" : "-Ax:Y}Pos-Sel.TWST", "val_postfix" : "-Ax:Y}Val:2-SP"}),
        "pair3": (LookupPair, "", {"name_postfix" : "-Ax:Y}Pos-Sel.THST", "val_postfix" : "-Ax:Y}Val:3-SP"}),
        "pair4": (LookupPair, "", {"name_postfix" : "-Ax:Y}Pos-Sel.FRST", "val_postfix" : "-Ax:Y}Val:4-SP"})
    })


    pos_lookup_x = DynamicDeviceComponent(defn_x)
    pos_lookup_y = DynamicDeviceComponent(defn_y)
    x = Cpt(EpicsMotor, '-Ax:X}Mtr', name='x')
    y = Cpt(EpicsMotor, '-Ax:Y}Mtr', name='y')
    pos_sel = Cpt(EpicsSignal, "}Pos-Sel", kind="hinted")


    def __init__(self, prefix : str, *args, name = "", **kwargs):
        super().__init__(prefix, *args, name=name, **kwargs)


    def lookup(self, name: str):
        lst_x = list(self.pos_lookup_x.get())
        lst_y = list(self.pos_lookup_y.get())
        
        pair_dict = dict((lst_x[k].pair_name, (lst_x[k].pair_val, lst_y[k].pair_val)) for k in range(len(self.defn_x)))
        
        for pair_name in pair_dict:
            if pair_name == name:
                return pair_dict[pair_name]     
        raise ValueError (f"Could not find {name} in lookup table")
    
    
    def get_all_sizes(self):
        lst_x = list(self.pos_lookup_x.get())
        lst_y = list(self.pos_lookup_y.get())
        
        pair_dict = dict((lst_x[k].pair_name, (lst_x[k].pair_val, lst_y[k].pair_val)) for k in range(len(self.defn_x)))
        length = len(pair_dict)
        print(f"{length} possible sizes:")
        print("----------------------------------")
        for pair_name in pair_dict:
            print(f'    {pair_name:_<10} : {pair_dict[pair_name]}')

        print(self.pair_dict)


    def set_pos(self, pos: str):
        lst_x = list(self.pos_lookup_x.get())
        lst_y = list(self.pos_lookup_y.get())
        
        pair_dict = dict((lst_x[k].pair_name, (lst_x[k].pair_val, lst_y[k].pair_val)) for k in range(len(self.defn_x)))
        val = pos
        if isinstance(val, float):
            for pair_name in pair_dict:
                if pair_dict[pair_name] == val:
                    val = pair_name
        return self.pos_sel.set(str(val))
    

    def set(self, size = None):
        if size is None:
            _xpos = round(self.x.get()[0], 3)
            _ypos = round(self.y.get()[0], 3)

            lst_x = list(self.pos_lookup_x.get())
            lst_y = list(self.pos_lookup_y.get())
            
            holes_reverse = dict(((lst_x[k].pair_val, lst_y[k].pair_val), lst_x[k].pair_name) for k in range(len(self.defn_x)))
            try:
                _size_slt3_pinhole = holes_reverse[(_xpos, _ypos)]
                print(f'{_size_slt3_pinhole}um pinhole at {self.name}: {self.x.name} = {_xpos:.4f}, {self.y.name} = {_ypos:.4f}') 
            except KeyError:
                print(f'Unknown configuration: {self.x.name} = {_xpos:.4f}, {self.y.name} = {_ypos:.4f}') 


        else:
            print('Moving to {} um {}'.format(size, self.name))
            x_pos, y_pos = self.lookup(str(size))
            x_sts = self.x.set(x_pos)
            y_sts = self.y.set(y_pos)
            self.set_pos(size)
            return x_sts & y_sts