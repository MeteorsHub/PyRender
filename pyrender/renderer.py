import os
import cupy as cp
import traceback
from PyQt5.Qt import QPixmap, QImage


class Renderer:

    OPEN_FILE_SUCCESS = 0
    OPEN_FILE_NOT_EXIST = 1
    OPEN_FILE_IO_ERROR = 2
    OPEN_FILE_SYNTAX_NOT_SUPPORT = 3

    PROJECTION_PERSPECTIVE = 0
    PROJECTION_RECTANGULAR = 1

    ZOOM_METHOD_IN = 0
    ZOOM_METHOD_OUT = 1

    im = cp.identity(3, cp.float32)
    em = cp.zeros((3, 4), cp.float32)

    render_grid = True
    render_face = True
    render_method = PROJECTION_PERSPECTIVE

    def __init__(self, parent, shader_resolution):
        self.parent = parent
        self.shader_resolution = shader_resolution
        # init camera configs
        self.im[0, 0] = 200.0
        self.im[1, 1] = 200.0
        self.im[0, 2] = shader_resolution[0]/2
        self.im[1, 2] = shader_resolution[1]/2
        self.em[2, 3] = -15.0
        self.em[0, 0] = 1.0
        self.em[1, 1] = 1.0
        self.em[2, 2] = 1.0

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

    def update_render(self) -> QPixmap:
        # TODO
        img = cp.zeros((self.shader_resolution[1], self.shader_resolution[0], 3), cp.uint8)

        v_color = cp.array([255, 255, 255], cp.uint8)
        if self.render_method == self.PROJECTION_PERSPECTIVE:
            for model in self.models:
                v_extend = cp.concatenate((model.v, cp.ones((model.v_size, 1), cp.float32)), axis=1)
                v_im = cp.transpose(cp.matmul(self.im, cp.matmul(self.em, cp.transpose(v_extend))))
                v_im = v_im / v_im[:, 2:]
                v_im = v_im[:, :2]
                v_im = v_im.astype(cp.int32)
                for i in range(len(v_im)):
                    if 0 <= v_im[i, 0] <= self.shader_resolution[0] and 0 <= v_im[i, 1] <= self.shader_resolution[1]:
                        img[v_im[i, 1], v_im[i, 0], :] = v_color
            img = cp.asnumpy(img)
            pixmap = QImage(img.data, img.shape[1], img.shape[0], QImage.Format_RGB888)
            pixmap = QPixmap(pixmap)
            return pixmap

    def zoom(self, method: ZOOM_METHOD_IN, factor=20):
        assert factor > 0
        if (10 + factor) < self.im[0, 0] < 400:
            if method == self.ZOOM_METHOD_OUT:
                factor = -factor
            self.im[0, 0] += factor
            self.im[1, 1] += factor


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
        self.com = com
        # translate to origin point
        self.translate(-com)
        # compute size
        self.size = cp.max(cp.sqrt(cp.sum((self.v - com) ** 2, axis=1)), axis=0)
        # resize to size of 10
        self.scale(10.0 / self.size)

    def translate(self, xyz):
        self.v += xyz
        self.com += xyz

    def scale(self, factor):
        self.v -= self.com
        self.v *= factor
        self.v += self.com
        self.size *= factor

    def rotate(self, axis: [0, 0, 1], angle: cp.pi):
        axis = self.norm(axis)
        self.v -= self.com
        cos_d = cp.cos(angle)
        sin_d = cp.sin(angle)
        x = axis[0]
        y = axis[1]
        z = axis[2]
        mat = cp.array([[(1-cos_d)*x*x+cos_d, (1-cos_d)*x*y-sin_d*z, (1-cos_d)*x*z+sin_d*y],
                        [(1-cos_d)*y*x+sin_d*z, (1-cos_d)*y*y+cos_d, (1-cos_d)*y*z-sin_d*x],
                        [(1-cos_d)*z*x-sin_d*y, (1-cos_d)*z*y+sin_d*x, (1-cos_d)*z*z+cos_d]], cp.float32)
        self.v = cp.matmul(self.v, cp.transpose(mat))
        self.v += self.com

    @staticmethod
    def mod(vct):
        return cp.linalg.norm(vct)

    @staticmethod
    def norm(vct):
        return vct / cp.linalg.norm(vct)

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
