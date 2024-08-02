# https://stackoverflow.com/questions/76476952/how-to-resolve-error-0x80070057-the-parameter-is-incorrect-in-pyside6-qt3d

import struct
import sys
from PySide6.QtCore import (QByteArray)
from PySide6.QtGui import (QGuiApplication, QVector3D)
from PySide6.Qt3DCore import (Qt3DCore)
from PySide6.Qt3DExtras import (Qt3DExtras)
from PySide6.Qt3DRender import (Qt3DRender)

import os
os.environ['QT3D_RENDERER'] = 'opengl'

class Window(Qt3DExtras.Qt3DWindow):
    def __init__(self):
        super().__init__()

        self.camera().lens().setPerspectiveProjection(45, 16 / 9, 0.1, 1000)
        self.camera().setPosition(QVector3D(0, 0, 10))
        self.camera().setViewCenter(QVector3D(0, 0, 0))

        self.rootEntity = Qt3DCore.QEntity()
        self.material = Qt3DExtras.QPerVertexColorMaterial(self.rootEntity)
        
        self.camController = Qt3DExtras.QOrbitCameraController(self.rootEntity)
        self.camController.setLinearSpeed(50)
        self.camController.setLookSpeed(180)
        self.camController.setCamera(self.camera())

        self.setRootEntity(self.rootEntity)

        self.generate_primitive([0, 0, 0, 1, 0, 0], colors=[1, 0, 0])
        self.generate_primitive([0, 0, 0, 0, 1, 0], colors=[0, 1, 0])
        self.generate_primitive([0, 0, 0, 0, 0, 1], colors=[0, 0, 1])

        pts = [0, 0, 2,
               1, 0, 2,
               1, 1, 2,
               0, 1, 2]
        # TODO: LineLoop still passes through 0, 0, 0 !!!
        self.generate_primitive(pts, primitive=Qt3DRender.QGeometryRenderer.PrimitiveType.Lines)

    def generate_primitive(self,
                           coordinates,
                           colors=None,
                           primitive=Qt3DRender.QGeometryRenderer.PrimitiveType.Lines):
        # coordinates = [x1, y1, z1, x2, y2, z2, ...]
        if colors is None:
            colors = [0.5, 0.5, 0.5]
        if len(colors) != len(coordinates):
            color_list = colors * int(len(coordinates) / len(colors))
        else:
            color_list = colors

        # Entity
        custom_primitive_entity = Qt3DCore.QEntity(self.rootEntity)

        # Renderer
        custom_line_renderer = Qt3DRender.QGeometryRenderer(custom_primitive_entity)
        custom_line_renderer.setPrimitiveType(primitive)
        custom_geometry = Qt3DCore.QGeometry(custom_line_renderer)

        # Position Attribute
        position_data_buffer = Qt3DCore.QBuffer(custom_geometry)
        position_data_buffer.setData(struct.pack('%sf' % len(coordinates), *coordinates))
        position_attribute = Qt3DCore.QAttribute(custom_geometry)
        position_attribute.setBuffer(position_data_buffer)
        position_attribute.setVertexSize(3)  # 3 floats
        position_attribute.setName(Qt3DCore.QAttribute.defaultPositionAttributeName())
        custom_geometry.addAttribute(position_attribute)

        # Color Attribute
        color_data_buffer = Qt3DCore.QBuffer(custom_geometry)
        color_data_buffer.setData(struct.pack('%sf' % len(color_list), *color_list))
        color_attribute = Qt3DCore.QAttribute(custom_geometry)
        color_attribute.setBuffer(color_data_buffer)
        color_attribute.setVertexSize(3)  # 3 floats
        color_attribute.setCount(len(color_list))  # colors (per vertex)
        color_attribute.setName(Qt3DCore.QAttribute.defaultColorAttributeName())
        custom_geometry.addAttribute(color_attribute)

        # make the geometry visible with a renderer
        custom_line_renderer.setGeometry(custom_geometry)

        # add everything to the scene
        transform = Qt3DCore.QTransform(custom_geometry)
        transform.setRotationX(-90)
        custom_primitive_entity.addComponent(transform)
        custom_primitive_entity.addComponent(custom_line_renderer)
        custom_primitive_entity.addComponent(self.material)

if __name__ == '__main__':
    app = QGuiApplication(sys.argv)
    view = Window()
    view.show()
    sys.exit(app.exec())