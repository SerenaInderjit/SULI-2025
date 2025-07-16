from ophyd import AreaDetector, SingleTrigger, StatsPlugin, ROIPlugin, TransformPlugin, OverlayPlugin, Signal
from ophyd.areadetector.plugins import HDF5Plugin_V22
from ophyd.areadetector.filestore_mixins import FileStoreHDF5IterativeWrite
from pathlib import PurePath


import logging
from typing import Union, Optional
from functools import reduce

import networkx as nx
from ophyd import (EpicsScaler, EpicsSignal, EpicsMotor, EpicsSignalRO, Device, BlueskyInterface,
                   SingleTrigger, HDF5Plugin, ImagePlugin, StatsPlugin,
                   ROIPlugin, TransformPlugin, OverlayPlugin, ProsilicaDetector, TIFFPlugin, Signal, Staged, CamBase)

from ophyd.areadetector.cam import AreaDetectorCam, ADBase
from ophyd.areadetector.detectors import DetectorBase
from ophyd.areadetector.filestore_mixins import FileStoreHDF5IterativeWrite, FileStoreTIFFIterativeWrite, resource_factory
from ophyd.areadetector import ADComponent, EpicsSignalWithRBV
from ophyd.areadetector.plugins import PluginBase, ProcessPlugin, HDF5Plugin_V22, TIFFPlugin_V22, CircularBuffPlugin_V34, CircularBuffPlugin, PvaPlugin
from ophyd import Component as Cpt, DeviceStatus
from ophyd.device import FormattedComponent as FCpt
from ophyd import AreaDetector
from ophyd.status import Status, SubscriptionStatus
from pathlib import PurePath
import time as ttime
import itertools

from ophyd.sim import NullStatus


import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def update_describe_typing(dic, obj):
    """
    Function for updating dictionary result of `describe` to include better typing.
    Previous defaults did not use `dtype_str` and simply described an image as an array.

    Parameters
    ==========
    dic: dict
        Return dictionary of describe method
    obj: OphydObject
        Instance of plugin
    """
    key = obj.parent._image_name
    cam_dtype = obj.parent.cam.data_type.get(as_string=True)
    type_map = {'UInt8': '|u1', 'UInt16': '<u2', 'Float32':'<f4', "Float64":'<f8'}
    if cam_dtype in type_map:
        dic[key].setdefault('dtype_str', type_map[cam_dtype])

class ExternalFileReference(Signal):
    """
    A pure software signal where a Device can stash a datum_id.

    For example, it can store timestamps from HDF5 files. It needs
    a `shape` because an HDF5 file can store multiple frames which
    have multiple timestamps.
    """
    def __init__(self, *args, shape, **kwargs):
        super().__init__(*args, **kwargs)
        self.shape = shape

    def describe(self):
        res = super().describe()
        res[self.name].update(
            dict(external="FILESTORE:", dtype="array", shape=self.shape)
        )
        return res

class HDF5PluginWithFileStorePlain(HDF5Plugin_V22, FileStoreHDF5IterativeWrite): ##SOURCED FROM BELOW FROM FCCD WITH SWMR removed
    _default_read_attrs = ("time_stamp",)
    # Captures the datum id for the timestamp recorded in the HDF5 file
    time_stamp = Cpt(ExternalFileReference, value="", kind="normal", shape=[])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # In CSS help: "N < 0: Up to abs(N) new directory levels will be created"
        self.stage_sigs.update({"create_directory": -3})
        # last=False turns move_to_end into move_to_start. Yes, it's silly.
        self.stage_sigs.move_to_end("create_directory", last=False)

        # Setup for timestamping using the detector
        self._ts_datum_factory = None
        self._ts_resource_uid = ""
        self._ts_counter = None

    def stage(self):
        # Start the timestamp counter
        self._ts_counter = itertools.count()
        return super().stage()

    def get_frames_per_point(self):
        return self.parent.cam.num_images.get()

    def make_filename(self):
        # stash this so that it is available on resume
        self._ret = super().make_filename()
        return self._ret

    def describe(self):
        ret = super().describe()
        update_describe_typing(ret, self)
        return ret

    def _generate_resource(self, resource_kwargs):
        super()._generate_resource(resource_kwargs)
        fn = PurePath(self._fn).relative_to(self.reg_root)

        # Update the shape that describe() will report
        # Multiple images will have multiple timestamps
        fpp = self.get_frames_per_point()
        self.time_stamp.shape = [fpp] if fpp > 1 else []

        # Query for the AD_HDF5_TS timestamp
        # See https://github.com/bluesky/area-detector-handlers/blob/master/area_detector_handlers/handlers.py#L230
        resource, self._ts_datum_factory = resource_factory(
            spec="AD_HDF5_DET_TS",
            root=str(self.reg_root),
            resource_path=str(fn),
            resource_kwargs=resource_kwargs,
            path_semantics=self.path_semantics,
        )

        self._ts_resource_uid = resource["uid"]
        self._asset_docs_cache.append(("resource", resource))

    def generate_datum(self, key, timestamp, datum_kwargs):
        ret = super().generate_datum(key, timestamp, datum_kwargs)
        datum_kwargs = datum_kwargs or {}
        datum_kwargs.update({"point_number": next(self._ts_counter)})
        # make the timestamp datum, in this case we know they match
        datum = self._ts_datum_factory(datum_kwargs)
        datum_id = datum["datum_id"]

        # stash so that we can collect later
        self._asset_docs_cache.append(("datum", datum))
        # put in the soft-signal so it gets auto-read later
        self.time_stamp.put(datum_id)
        return ret


class StandardCam(SingleTrigger, AreaDetector):#TODO is there something more standard for prosilica? seems only used on prosilica. this does stats, but no image saving (unsure if easy to configure or not and enable/disable)
    stats1 = Cpt(StatsPlugin, 'Stats1:')
    stats2 = Cpt(StatsPlugin, 'Stats2:')
    stats3 = Cpt(StatsPlugin, 'Stats3:')
    stats4 = Cpt(StatsPlugin, 'Stats4:')
    stats5 = Cpt(StatsPlugin, 'Stats5:')
    roi1 = Cpt(ROIPlugin, 'ROI1:')
    roi2 = Cpt(ROIPlugin, 'ROI2:')
    roi3 = Cpt(ROIPlugin, 'ROI3:')
    roi4 = Cpt(ROIPlugin, 'ROI4:')
    #proc1 = Cpt(ProcessPlugin, 'Proc1:')
    trans1 = Cpt(TransformPlugin, 'Trans1:')
    over1 = Cpt(OverlayPlugin, 'Over1:') ##for crosshairs in tiff


class StandardProsilicaWithHDF5(StandardCam):
    hdf5 = Cpt(HDF5PluginWithFileStorePlain,
              suffix='HDF1:',
              write_path_template='/nsls2/data/csx/legacy/prosilica_data/hdf5/%Y/%m/%d',
              root='/nsls2/data/csx/legacy')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hdf5.kind = "normal"




# HDF5 Camera
cam_fs1_hdf5 = StandardProsilicaWithHDF5('XF:23IDA-BI:1{FS:1-Cam:1}', name = 'cam_fs1_hdf5')
# Test wit RE(count([cam_fs1_hdf5]))


for k in (f'stats{j}' for j in range(1, 6)):
    cam_fs1_hdf5.read_attrs.append(k)
    getattr(cam_fs1_hdf5, k).read_attrs = ['total']
    getattr(cam_fs1_hdf5, k).total.kind = 'hinted'


roi_params = ['.min_xyz', '.min_xyz.min_y', '.min_xyz.min_x',
              '.size', '.size.y', '.size.x', '.name_']

configuration_attrs_list = [] 

configuration_attrs_list.extend(['roi' + str(i) + string for i in range(1,5) for string in roi_params])
for attr in configuration_attrs_list:
    getattr(cam_fs1_hdf5, attr).kind='config'

cam_fs1_hdf5.configuration_attrs.extend(['roi1', 'roi2', 'roi3','roi4'])



# XF:23ID-PPS{Sh:FE}Pos-Sts




# Canting magnet readback value
canter = EpicsSignalRO('SR:C23-MG:G1{MG:Cant-Ax:X}Mtr.RBV', name='canter')

# Phaser magnet motor
phaser = EpicsMotor('SR:C23-MG:G1{MG:Phaser-Ax:Y}Mtr',name='phaser')



# M1A mirror (csx1/startup/optics.py)

class FMBHexapodMirrorAxis(PVPositioner):
    readback = Cpt(EpicsSignalRO, 'Mtr_MON')
    setpoint = Cpt(EpicsSignal, 'Mtr_POS_SP')
    actuate = FmtCpt(EpicsSignal, '{self.parent.prefix}}}MOVE_CMD.PROC')
    actual_value = 1
    stop_signal = FmtCpt(EpicsSignal, '{self.parent.prefix}}}STOP_CMD.PROC')
    stop_value = 1
    done = FmtCpt(EpicsSignalRO, '{self.parent.prefix}}}BUSY_STS')
    done_value = 0


class FMBHexapodMirror(Device):
    z = Cpt(FMBHexapodMirrorAxis, '-Ax:Z}')
    y = Cpt(FMBHexapodMirrorAxis, '-Ax:Y}')
    x = Cpt(FMBHexapodMirrorAxis, '-Ax:X}')
    pit = Cpt(FMBHexapodMirrorAxis, '-Ax:Pit}')
    yaw = Cpt(FMBHexapodMirrorAxis, '-Ax:Yaw}')
    rol = Cpt(FMBHexapodMirrorAxis, '-Ax:Rol}')


m1a = FMBHexapodMirror('XF:23IDA-OP:1{Mir:1', name='m1a', labels=['optics'])

# RE(mvr(m1a.pit, 0.025))


# Front End Slits  FE:C23A-OP{Slt:12-Ax:X}size.VAL

class acc_slit(PVPositionerPC):
    setpoint = Cpt(EpicsSignal, 'size.VAL')
    readback = Cpt(EpicsSignalRO, 't2.C')

class acc_slit_cent(PVPositionerPC):
    setpoint = Cpt(EpicsSignal, 'center.VAL')
    readback = Cpt(EpicsSignalRO, 't2.D')

class FEAxis(Device):
    gap = FCpt(acc_slit, '{prefix}-Ax:{self.axis}}}')
    cent = FCpt(acc_slit_cent, '{prefix}-Ax:{self.axis}}}')

    def __init__(self, *args, axis : str, **kwargs):
        self.axis = axis
        super().__init__(*args, **kwargs)

class FrontEndSlit(Device):
    x = Cpt(FEAxis, '', axis = 'X')
    y = Cpt(FEAxis, '', axis = 'Y')

FEslt = FrontEndSlit('FE:C23A-OP{Slt:12', name = 'FEslt', labels=['optics'])

# EPUs 

# (csx1/devices/epu.py)

class EPUMotor(PVPositionerPC):
    readback = Cpt(EpicsSignalRO, 'Pos-I')
    setpoint = Cpt(EpicsSignal, 'Pos-SP')
    stop_signal = FCpt(EpicsSignal,
                        '{self._stop_prefix}{self._stop_suffix}-Mtr.STOP')
    stop_value = 1

    def __init__(self, *args, parent=None, stop_suffix=None, **kwargs):
        self._stop_prefix = parent._epu_prefix
        self._stop_suffix = stop_suffix
        super().__init__(*args, parent=parent, **kwargs)

class Interpolator(Device):
    input = Cpt(EpicsSignal, 'Val:Inp1-SP')
    input_offset = Cpt(EpicsSignal, 'Val:InpOff1-SP')
    # {'Enabled', 'Disabled'}
    input_link = Cpt(EpicsSignal, 'Enbl:Inp1-Sel', string=True)
    input_pv = Cpt(EpicsSignal, 'Val:Inp1-SP.DOL$', string=True)
    output = Cpt(EpicsSignalRO, 'Val:Out1-I')
    # {'Enable', 'Disable'}
    output_link = Cpt(EpicsSignalRO, 'Enbl:Out1-Sel', string=True)
    output_pv = Cpt(EpicsSignal, 'Calc1.OUT$', string=True)
    output_deadband = Cpt(EpicsSignal, 'Val:DBand1-SP')
    output_drive = Cpt(EpicsSignalRO, 'Val:OutDrv1-I')
    interpolation_status = Cpt(EpicsSignalRO, 'Sts:Interp1-Sts', string=True)
    #table = Cpt(EpicsSignal, 'Val:Table-Sel', name='table')# this pv has no FLT

class EPU(Device):
    gap = Cpt(EPUMotor, '-Ax:Gap}', stop_suffix='-Ax:Gap}')
    phase = Cpt(EPUMotor, '-Ax:Phase}', stop_suffix='-Ax:Phase}')
    x_off = FCpt(EpicsSignalRO,'{self._ai_prefix}:FPGA:x_mm-I')
    x_ang = FCpt(EpicsSignalRO,'{self._ai_prefix}:FPGA:x_mrad-I')
    y_off = FCpt(EpicsSignalRO,'{self._ai_prefix}:FPGA:y_mm-I')
    y_ang = FCpt(EpicsSignalRO,'{self._ai_prefix}:FPGA:y_mrad-I')
    flt = Cpt(Interpolator, '-FLT}')
    rlt = Cpt(Interpolator, '-RLT}')
    table = Cpt(EpicsSignal, '}Val:Table-Sel', name='table')# this pv has no FLT

    def __init__(self, *args, ai_prefix=None, epu_prefix=None, **kwargs):
        self._ai_prefix = ai_prefix
        self._epu_prefix = epu_prefix
        super().__init__(*args, **kwargs)

# (csx1/startup/accelerator.py)
epu1 = EPU('XF:23ID-ID{EPU:1', epu_prefix='SR:C23-ID:G1A{EPU:1', ai_prefix='SR:C31-{AI}23', name='epu1')
epu2 = EPU('XF:23ID-ID{EPU:2', epu_prefix='SR:C23-ID:G1A{EPU:2', ai_prefix='SR:C31-{AI}23-2', name='epu2', labels=['source'])


# BPM

class BPM_signal(Device):
    setpoint = Cpt(EpicsSignalRO, '-SP')
    deviation = Cpt(EpicsSignalRO, 'S-I')

class BPMAxis(Device):
    pos = FCpt(BPM_signal, '{prefix}Pos{self.axis}')
    angle = FCpt(BPM_signal, '{prefix}Angle{self.axis}')

    def __init__(self, *args, axis : str, **kwargs):
        self.axis = axis
        super().__init__(*args, **kwargs)

class BPM(Device):
    x = Cpt(BPMAxis, '', axis = 'X')
    y = Cpt(BPMAxis, '', axis = 'Y')


bpm = BPM('XF:23ID-ID{BPM}Val:', name = 'bpm')

es_diag1_y = EpicsMotor('XF:23ID1-ES{Diag:1-Ax:Y}Mtr', name='es_diag1_y', labels=['motors'])

fluo_screen_y = EpicsMotor('XF:23IDA-BI:1{FS:1-Ax:X}Mtr', name='fluo_screen_y', labels=['motors'])
# Turn fluo screen scan into image with ROIs
def make_fluo_img():
    img = np.array(list(db[-1].data("cam_fs1_hdf5_image")))[0][0]
    fig, ax = plt.subplots()

    imgplot = ax.imshow(img)

    rectangle1 = patches.Rectangle((cam_fs1_hdf5.roi1.min_xyz.min_x.get(), cam_fs1_hdf5.roi1.min_xyz.min_y.get()), cam_fs1_hdf5.roi1.size.x.get(), cam_fs1_hdf5.roi1.size.y.get(), linewidth = 1, edgecolor='aquamarine', facecolor='none', label = 'ROI1')
    rectangle2 = patches.Rectangle((cam_fs1_hdf5.roi2.min_xyz.min_x.get(), cam_fs1_hdf5.roi2.min_xyz.min_y.get()), cam_fs1_hdf5.roi2.size.x.get(), cam_fs1_hdf5.roi2.size.y.get(), linewidth = 1, edgecolor='aquamarine', facecolor='none', label = 'ROI2')
    rectangle3 = patches.Rectangle((cam_fs1_hdf5.roi3.min_xyz.min_x.get(), cam_fs1_hdf5.roi3.min_xyz.min_y.get()), cam_fs1_hdf5.roi3.size.x.get(), cam_fs1_hdf5.roi3.size.y.get(), linewidth = 1, edgecolor='aquamarine', facecolor='none', label = 'ROI3')
    rectangle4 = patches.Rectangle((cam_fs1_hdf5.roi4.min_xyz.min_x.get(), cam_fs1_hdf5.roi4.min_xyz.min_y.get()), cam_fs1_hdf5.roi4.size.x.get(), cam_fs1_hdf5.roi4.size.y.get(), linewidth = 1, edgecolor='aquamarine', facecolor='none', label = 'ROI4')


    roi1 = ax.add_patch(rectangle1)
    roi2 = ax.add_patch(rectangle2)
    roi3 = ax.add_patch(rectangle3)
    roi4 = ax.add_patch(rectangle4)

    imgplot.set_cmap('jet')
    plt.show()
