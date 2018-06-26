import os
import cupy as cp
import traceback
from PyQt5.Qt import QPixmap


class Renderer:

    OPEN_FILE_SUCCESS = 0
    OPEN_FILE_NOT_EXIST = 1
    OPEN_FILE_IO_ERROR = 2
    OPEN_FILE_SYNTAX_NOT_SUPPORT = 3

    im = cp.array([[]])

    def __init__(self, parent, shader_resolution):
        self.parent = parent
        self.shader_resolution = shader_resolution
        self.models = []

    def open_obj_file(self, filename) -> int:
        if not os.path.exists(filename):
            return self.OPEN_FILE_NOT_EXIST
        try:
            self.models.append(Model(filename))
        except IOError:
            return self.OPEN_FILE_IO_ERROR
        except SyntaxError:
            return self.OPEN_FILE_SYNTAX_NOT_SUPPORT
        return self.OPEN_FILE_SUCCESS

    def render(self, grid=True, face=True) -> QPixmap:
        # TODO
        pass


class Model:
    v = cp.zeros((0, 3), cp.float32)  # [x, y, z] float32
    vt = cp.zeros((0, 3), cp.float32)  # [u, v, w] float32
    vn = cp.zeros((0, 3), cp.float32)  # [x, y, z] float32
    f = []  # [[i_v, i_vt, i_vn, i_mtl] int32, ...]
    mtl = []

    com = cp.zeros((3,), cp.float32)  # center of mass
    size = 0.0  # max distance to the com

    def __init__(self, filename=None):
        if filename is not None:
            self.load_obj_file(filename)

    def load_obj_file(self, filename):
        self.clear()
        try:
            with open(filename) as f:
                for line in f:
                    line = line.rstrip('\n')
                    if not line or line.startswith('#'):
                        continue
                    element = line.strip().split()
                    if element[0] == 'v':
                        assert len(element) == 4
                        v = cp.array([[float(element[1]), float(element[2]), float(element[3])]], cp.float32)
                        self.v = cp.concatenate([self.v, v])
                    elif element[0] == 'vt':
                        assert len(element) in [3, 4]
                        vt = cp.zeros((1, 3), cp.float32)
                        vt[0, 0] = float(element[1])
                        vt[0, 1] = float(element[2])
                        if len(element) == 4:
                            vt[0, 2] = float(element[3])
                        self.vt = cp.concatenate([self.vt, vt])
                    elif element[0] == 'vn':
                        assert len(element) == 4
                        vn = cp.array([[float(element[1]), float(element[2]), float(element[3])]], cp.float32)
                        self.vn = cp.concatenate([self.vn, vn])
                    elif element[0] == 'f':
                        f = cp.zeros((0, 4), cp.int32)
                        for fv in element[1:]:
                            fv = fv.split('/')
                            assert len(fv) == 3
                            fva = cp.zeros((1, 4), cp.int32) - 1
                            if fv[0]:
                                fva[0, 0] = int(fv[0]) - 1  # index change
                            if fv[1]:
                                fva[0, 1] = int(fv[1]) - 1
                            if fv[2]:
                                fva[0, 2] = int(fv[2]) - 1
                            f = cp.concatenate([f, fva])
                        self.f.append(f)
                    elif element[0] == 'mtllib':
                        # TODO
                        pass
                    elif element[0] == 'usemtl':
                        # TODO
                        pass
                    elif element[0] in ['s', 'g', 'vp', 'p', 'l']:
                        # ignore these components
                        continue
                    else:
                        raise SyntaxError
        except IOError:
            self.clear()
            print(traceback.format_exc())
            raise IOError
        except (IndexError, ValueError, AssertionError):
            self.clear()
            print(traceback.format_exc())
            raise SyntaxError
        self.init_computation()

    def init_computation(self):
        # compute center of mass
        com = cp.sum(self.v, axis=0) / self.v_size
        # translate to origin point
        self.translate(-com)
        # compute size
        self.size = cp.max(cp.sqrt(cp.sum((self.v - com) ** 2, axis=1)), axis=0)

    def translate(self, xyz):
        self.v += xyz

    @property
    def v_size(self):
        return len(self.v)

    @property
    def vt_size(self):
        return len(self.vt)

    @property
    def vn_size(self):
        return len(self.vn)

    @property
    def f_size(self):
        return len(self.f)

    def clear(self):
        self.v = cp.zeros((0, 3), cp.float32)
        self.vt = cp.zeros((0, 3), cp.float32)
        self.vn = cp.zeros((0, 3), cp.float32)
        self.f = []
        self.mtl = []
