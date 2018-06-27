import sys
from PyQt5.Qt import QPixmap, QApplication, QWidget, QMainWindow, QFileDialog, QMessageBox, QLabel
from PyQt5.uic import loadUi

from renderer import Renderer


class MainWindow(QMainWindow):

    def __init__(self, shader_resolution=(800, 600)):
        super().__init__()
        self.shader_resolution = shader_resolution
        loadUi('ui/MainWindow.ui', self)
        self.init_ui()
        self.renderer = Renderer(self, shader_resolution)

    def init_ui(self):
        init_img = QPixmap(800, 600)
        self.update_shader(init_img)

    def update_shader(self, img: QPixmap=None):
        self.shader: QLabel
        if img is None:
            img = self.renderer.update_render()
        self.shader.setPixmap(img)

    def on_clicked_action_open(self):
        filename = QFileDialog.getOpenFileName(self, 'Open .obj model file', r'../3d_object', '*.obj')[0]
        if not filename:
            return
        stat = self.renderer.open_obj_file(filename)
        if stat == Renderer.OPEN_FILE_SUCCESS:
            self.update_shader()
            return
        msg = "Failed opening '%s'. " % filename
        if stat == Renderer.OPEN_FILE_NOT_EXIST:
            msg += 'File do not exist.'
        if stat == Renderer.OPEN_FILE_IO_ERROR:
            msg += 'File io error.'
        if stat == Renderer.OPEN_FILE_SYNTAX_NOT_SUPPORT:
            msg += 'File syntax not support.'
        QMessageBox.warning(self, 'Failed Opening', msg)

    def on_clicked_button_zoom_in(self):
        self.renderer.zoom(self.renderer.ZOOM_METHOD_IN)
        self.update_shader()

    def on_clicked_button_zoom_out(self):
        self.renderer.zoom(self.renderer.ZOOM_METHOD_OUT)
        self.update_shader()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec_())
