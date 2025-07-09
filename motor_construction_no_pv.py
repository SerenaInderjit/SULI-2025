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

    # pos_lookup = DynamicDeviceComponent(defn)
    
    
    motor = Cpt(EpicsMotor, "Mtr")
    pos_sel = Cpt(EpicsSignal, "Pos-Sel")
    

    def __init__(self, prefix : str, *args, name = "", **kwargs):
        super().__init__(prefix, *args, name=name, **kwargs)
        self.pos_lookup = {"Out": -55.0, 
                           "YAG": -62.0,
                           "Cu Block": -74.0,
                           "SrTiO3": -76.0,
                           "HEO-dark": -79.0,
                           "HEO-light": -82.0,
                           "MgAl2O4": -86.0,
                           "Si": -89,
                           "ZnSe": -92.0,
                           "Undefined": 0.0}

    

    def lookup(self, name: str) -> float:
        
        for pair_name in self.pos_lookup:
            if pair_name == name:
                return self.pos_lookup[pair_name]       
        raise ValueError (f"Could not find {name} in lookup table")
    
    def get_all_positions(self):
        
        length = len(self.pos_lookup)
        print(f"{length} possible positions:")
        print("----------------------------------")
        for pair_name in self.pos_lookup:
            print(f'    {pair_name:_<15} : {self.pos_lookup[pair_name]}')


    def set_pos(self, pos: str | float):
        
        val = pos
        if isinstance(val, float):
            for pair_name in self.pos_lookup:
                if pair_name == val:
                    val = self.pos_lookup[pair_name]
        return self.pos_sel.set(str(val))


    def set(self, pos: str | float):
        if isinstance(pos, str):
            val = self.lookup(pos)
        else:
            val = pos
        mv_sts = self.motor.set(val)
        self.set_pos(pos)
        return mv_sts


class SlitsWithLookup(Device):

    x = Cpt(EpicsMotor, '-Ax:X}Mtr', name='x')
    y = Cpt(EpicsMotor, '-Ax:Y}Mtr', name='y')


    def __init__(self, prefix : str, *args, name = "", **kwargs):
        super().__init__(prefix, *args, name=name, **kwargs)
        lst_x = {
                "pair1" : {"pair_name" : "2000", "pair_val": 8.800},
                "pair2" : {"pair_name" : "50", "pair_val": 0.800},
                "pair3" : {"pair_name" : "20", "pair_val": - 8.727},
                "pair4" : {"pair_name" : "10", "pair_val": -17.350}
            }

        lst_y = {
                "pair1" : {"pair_name" : "2000", "pair_val": 0.000},
                "pair2" : {"pair_name" : "50", "pair_val": 0.000},
                "pair3" : {"pair_name" : "20", "pair_val": 0.050},
                "pair4" : {"pair_name" : "10", "pair_val": -0.075}
            }
        
        self.pair_dict = dict((lst_x[k]["pair_name"], (lst_x[k]["pair_val"], lst_y[k]["pair_val"])) for k in lst_x)

    def lookup(self, name: str):        
        for pair_name in self.pair_dict:
            if pair_name == name:
                return self.pair_dict[pair_name]     
        raise ValueError (f"Could not find {name} in lookup table")
    
    
    def get_all_sizes(self):
        
        length = len(self.pair_dict)
        print(f"{length} possible sizes:")
        print("----------------------------------")
        for pair_name in self.pair_dict:
            print(f'    {pair_name:_<10} : {self.pair_dict[pair_name]}')



    def set_pos(self, pos: str):
        val = pos
        if isinstance(val, float):
            for pair_name in self.pair_dict:
                if self.pair_dict[pair_name] == val:
                    val = pair_name
        return self.pos_sel.set(str(val))
    

    def set(self, size = None):
        if size is None:
            _xpos = round(self.x.get()[0], 3)
            _ypos = round(self.y.get()[0], 3)
            
            holes_reverse = dict((v, k) for k, v, in self.pair_dict.items())
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
            return x_sts & y_sts