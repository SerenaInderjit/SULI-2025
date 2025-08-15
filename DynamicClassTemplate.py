from ophyd import Component
from ophyd.sim import SynAxis, SynSignal
from collections import OrderedDict
from ophyd import Device


def make_new_class(num_mtrs, *args, **kwargs):

    # CREATE COMPONENTS THAT YOU WANT IN THE CLASS
    
    # Create single component manually
    my_signal = Component(SynSignal, name = "my_signal")


    # Dictionary to store dynamic number of components
    motors = OrderedDict()

    # Add num_mtrs motors
    for i in range(num_mtrs):
       motors[f"motor{i}"] = Component(SynAxis, name = f"motor{i}")



    # CREATE FUNCTIONS YOU WANT IN THE CLASS

    def __init__(self, *args, name, **kwargs):
      super(type(self), self).__init__(*args, name=name, **kwargs)
      self.num_mtrs = num_mtrs
    
    def my_function(self):
      print("This function works!")


    # ADD YOUR FUNCTIONS AND ATTRIBUTES TO THE CLSDICT

    docstring = (f"MyNewClass Device")
    read_attrs = ["my_signal"].extend(list(motors.keys()))


    clsdict = OrderedDict(
                __doc__=docstring,
                _default_read_attrs=read_attrs,   #   <-- Add attribute names into _default_read_attrs
                _default_configuration_attrs=[],
                __init__=__init__,                #   <-- Add Functions  name_to_call = object_name
                my_function=my_function,          #   <
                my_signal=my_signal               #   <-- Add single Components manually
            )
    
    clsdict = clsdict | motors                    #   <-- Add group of Components all at once
    

    # MAKE AND RETURN THE CLASS

    NewClass = type("NewClass", (Device,), clsdict, **{})   # type(name, bases, dict, **kwds)

    return NewClass


my_new_class = make_new_class(2)(name = "my_new_class")

    
    




