from ophyd import EpicsMotor, sim, Device
from ophyd import Component as Cpt, FormattedComponent as FCpt
from ophyd.sim import make_fake_device, SynAxis
from ophyd.signal import EpicsSignal
from ophyd.status import MoveStatus
from ophyd.device import DynamicDeviceComponent
from bluesky.plans import count, scan
from bluesky.plan_stubs import mv
from bluesky.preprocessors import SupplementalData

class LookupPair(Device):
    pair_name = FCpt(EpicsSignal, "{self.prefix}{self.name_postfix}", kind="config")
    pair_val = FCpt(EpicsSignal, "{self.prefix}{self.val_postfix}", kind="config")

    
    
    def __init__(self, *args, name_postfix : str, val_postfix : str, **kwargs):
        self.name_postfix = name_postfix
        self.val_postfix = val_postfix
        super().__init__(*args, **kwargs)
        


from collections import OrderedDict



class DynamicLookup(Device):
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

    lookupPairs = DynamicDeviceComponent(defn)

        

class CustomMotor(EpicsMotor):
    pos_lookup = Cpt(DynamicLookup, "")

    def __init__(self, name = "", prefix="", **kwargs):
        super().__init__(prefix, name = name, **kwargs)
        self.name = name
        self.prefix = prefix


    def lookup_by_name(self, name: str) -> float:
        
        pair_lst = list(self.pos_lookup.lookupPairs.get())
        for pair in pair_lst:
            if pair.pair_name == name:
                return pair.pair_val       
            
        raise ValueError (f"Could not find {name} in lookup table")
    
    def get_all_positions(self):
        pair_lst = list(self.pos_lookup.lookupPairs.get())
        length = len(pair_lst)
        print(f"{length} possible positions:")
        print("----------------------------------")
        for pair in pair_lst:
            print(f'    {pair.pair_name:_<15} : {pair.pair_val}')


    def set(self, pos: str | float):
        if isinstance(pos, str):
            val = self.lookup_by_name(pos)
        else:
            val = pos
        return super().set(val)
