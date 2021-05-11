import sys
import time
import os.path
import struct
import multiprocessing

try:
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import *
    from PyQt5.Qt3DCore import *
    from PyQt5.Qt3DExtras import *
    from PyQt5.Qt3DRender import *
except Exception:
    from PySide2.QtGui import *
    from PySide2.QtCore import *
    from PySide2.QtWidgets import *
    from PySide2.Qt3DCore import *
    from PySide2.Qt3DExtras import *
    from PySide2.Qt3DRender import *


import ifcopenshell
import ifcopenshell.geom
# https://github.com/IfcOpenShell/IfcOpenShell/blob/master/src/ifcopenshell-python/ifcopenshell/geom/occ_utils.py#L147
import ifcopenshell.geom.occ_utils
import OCC
import OCC.Core.gp
import OCC.Core.Geom
import OCC.Core.AIS

import OCC.Core.Bnd
import OCC.Core.BRepBndLib

import OCC.Core.BRep
import OCC.Core.BRepPrimAPI
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepBuilderAPI

import OCC.Core.GProp
import OCC.Core.BRepGProp

import OCC.Core.TopoDS
import OCC.Core.TopExp
import OCC.Core.TopAbs

from OCC.Core.Tesselator import ShapeTesselator

from collections import namedtuple
shape_tuple = namedtuple("shape_tuple", ("data", "geometry", "styles", "style_ids"))


class IFCQt3dView(QWidget):
    """
    3D View Widget
    - V1 = IFC File Loading, geometry parsing & basic navigation
    """
    def __init__(self):
        QWidget.__init__(self)

        # variables
        self.ifc_file = None
        self.start = time.time()

        # 3D View
        self.view = Qt3DWindow()
        self.view.defaultFrameGraph().setClearColor(QColor("#4466ff"))
        self.container = self.createWindowContainer(self.view)
        self.container.setMinimumSize(QSize(200, 100))
        self.container.setFocusPolicy(Qt.NoFocus)

        # Prepare our scene
        self.root = QEntity()
        self.material = QPerVertexColorMaterial()
        self.root.addComponent(self.material)
        self.material.setShareable(True)
        self.initialise_camera()
        self.view.setRootEntity(self.root)

        # Finish GUI
        layout = QHBoxLayout()
        layout.addWidget(self.container)
        self.setLayout(layout)

    def initialise_camera(self):
        # camera
        camera = self.view.camera()
        camera.lens().setPerspectiveProjection(45.0, 16.0 / 9.0, 0.1, 1000)
        camera.setPosition(QVector3D(0, 0, 40))
        camera.setViewCenter(QVector3D(0, 0, 0))

        # for camera control
        cam_controller = QOrbitCameraController(self.root)
        cam_controller.setLinearSpeed(50.0)
        cam_controller.setLookSpeed(180.0)
        cam_controller.setCamera(camera)

    def load_file(self, filename):
        if self.ifc_file is None:
            print("Importing IFC file ...")
            start = time.time()
            self.ifc_file = ifcopenshell.open(filename)
            print("Loaded in ", time.time() - start)

        print("Importing IFC geometrical information ...")
        self.start = time.time()
        settings = ifcopenshell.geom.settings()
        settings.set(settings.WELD_VERTICES, False)  # false is needed to generate normals -- slower!
        settings.set(settings.USE_WORLD_COORDS, True)  # true = ignore transformation

        settings.set(settings.USE_PYTHON_OPENCASCADE, True)

        # Two methods
        # self.parse_project(settings)  # SLOWER - create geometry for each product
        self.parse_geometry(settings)  # FASTER - iteration with parallel processing
        print("\nFinished in ", time.time() - self.start)

    def parse_geometry(self, settings):
        iterator = ifcopenshell.geom.iterator(settings, self.ifc_file, multiprocessing.cpu_count())
        iterator.initialize()
        counter = 0
        while True:
            shape = iterator.get()
            # skip openings and spaces geometry
            if not shape.data.product.is_a('IfcOpeningElement') and not shape.data.product.is_a('IfcSpace'):
                try:
                    self.generate_rendermesh(shape)
                    print(str("Shape {0}\t[#{1}]\tin {2} seconds")
                          .format(str(counter), str(shape.data.id), time.time() - self.start))
                except Exception as e:
                    print(str("Shape {0}\t[#{1}]\tERROR - {2} : {3}")
                          .format(str(counter), str(shape.data.id), shape.data.product.is_a(), e))
                    pass
            counter += 1
            if not iterator.next():
                break

    def parse_project(self, settings):
        # parse all products
        products = self.ifc_file.by_type('IfcProduct')
        counter = 0
        for product in products:
            if not product.is_a('IfcOpeningElement') and not product.is_a('IfcSpace'):
                if product.Representation:
                    shape = ifcopenshell.geom.create_shape(settings, product)
                    self.generate_rendermesh(shape)
                    print(str("Product {0}\t[#{1}]\tin {2} seconds")
                          .format(str(counter), str(product.id()), time.time() - self.start))
            counter += 1

    def parse_shape(self, geometry):
        # compute the tessellation
        tess = ShapeTesselator(geometry)
        tess.Compute()

        # get the vertices
        vertices = []
        vertex_count = tess.ObjGetVertexCount()
        for i_vertex in range(0, vertex_count):
            i1, i2, i3 = tess.GetVertex(i_vertex)
            vertices.append(i1)
            vertices.append(i2)
            vertices.append(i3)

        # get the normals
        normals = []
        normals_count = tess.ObjGetNormalCount()
        for i_normal in range(0, normals_count):
            i1, i2, i3 = tess.GetNormal(i_normal)
            normals.append(i1)
            normals.append(i2)
            normals.append(i3)

        # get the triangles
        triangles = []
        triangle_count = tess.ObjGetTriangleCount()
        for i_triangle in range(0, triangle_count):
            i1, i2, i3 = tess.GetTriangleIndex(i_triangle)
            triangles.append(i1)
            triangles.append(i2)
            triangles.append(i3)

        return vertices, normals, triangles

    def generate_rendermesh(self, shape):
        data = shape.data
        geometry = shape.geometry
        styles = shape.styles
        style_ids = shape.style_ids

        custom_mesh_entity = QEntity(self.root)
        it = OCC.Core.TopoDS.TopoDS_Iterator(geometry)
        index = 0
        while it.More():
            vertices, normals, triangles = self.parse_shape(it.Value())

            # ------ MESH --------------------------
            custom_mesh_renderer = QGeometryRenderer()
            custom_mesh_renderer.setPrimitiveType(QGeometryRenderer.Triangles)
            custom_geometry = QGeometry(custom_mesh_renderer)

            # Position Attribute
            position_data_buffer = QBuffer(QBuffer.VertexBuffer, custom_geometry)
            # position_data_buffer.setData(QByteArray(np.array(geometry.verts).astype(np.float32).tobytes()))
            position_data_buffer.setData(struct.pack('%sf' % len(vertices), *vertices))
            position_attribute = QAttribute()
            position_attribute.setAttributeType(QAttribute.VertexAttribute)
            position_attribute.setBuffer(position_data_buffer)
            position_attribute.setVertexBaseType(QAttribute.Float)
            position_attribute.setVertexSize(3)  # 3 floats
            position_attribute.setByteOffset(0)  # start from first index
            position_attribute.setByteStride(3 * 4)  # 3 coordinates and 4 as length of float32 in bytes
            position_attribute.setCount(len(vertices))  # vertices
            position_attribute.setName(QAttribute.defaultPositionAttributeName())
            custom_geometry.addAttribute(position_attribute)

            # Normal Attribute
            if len(normals) > 0:
                normals_data_buffer = QBuffer(QBuffer.VertexBuffer, custom_geometry)
                # normals_data_buffer.setData(QByteArray(np.array(geometry.normals).astype(np.float32).tobytes()))
                normals_data_buffer.setData(struct.pack('%sf' % len(normals), *normals))
                normal_attribute = QAttribute()
                normal_attribute.setAttributeType(QAttribute.VertexAttribute)
                normal_attribute.setBuffer(normals_data_buffer)
                normal_attribute.setVertexBaseType(QAttribute.Float)
                normal_attribute.setVertexSize(3)  # 3 floats
                normal_attribute.setByteOffset(0)  # start from first index
                normal_attribute.setByteStride(3 * 4)  # 3 coordinates and 4 as length of float32 in bytes
                normal_attribute.setCount(len(normals))  # vertices
                normal_attribute.setName(QAttribute.defaultNormalAttributeName())
                custom_geometry.addAttribute(normal_attribute)

            # Collect the colors via the materials (1 color per vertex)
            # we get a list of styles (ids) and surface styles (rgba values)
            # expressed per shape, not per vertex, so repeat them
            s_style = styles[index]
            r = s_style[0]
            g = s_style[1]
            b = s_style[2]
            color_list = [r, g, b] * int(len(vertices) / 3)

            # Color Attribute
            color_data_buffer = QBuffer(QBuffer.VertexBuffer, custom_geometry)
            # color_data_buffer.setData(QByteArray(np.array(color_list).astype(np.float32).tobytes()))
            color_data_buffer.setData(struct.pack('%sf' % len(color_list), *color_list))
            color_attribute = QAttribute()
            color_attribute.setAttributeType(QAttribute.VertexAttribute)
            color_attribute.setBuffer(color_data_buffer)
            color_attribute.setVertexBaseType(QAttribute.Float)
            color_attribute.setVertexSize(3)  # 3 floats
            color_attribute.setByteOffset(0)  # start from first index
            color_attribute.setByteStride(3 * 4)  # 3 coordinates and 4 as length of float32 in bytes
            color_attribute.setCount(len(color_list))  # colors (per vertex)
            color_attribute.setName(QAttribute.defaultColorAttributeName())
            custom_geometry.addAttribute(color_attribute)

            # Faces Index Attribute
            index_data_buffer = QBuffer(QBuffer.IndexBuffer, custom_geometry)
            # index_data_buffer.setData(QByteArray(np.array(triangles).astype(np.uintc).tobytes()))
            index_data_buffer.setData(struct.pack("{}I".format(len(triangles)), *triangles))
            index_attribute = QAttribute()
            index_attribute.setVertexBaseType(QAttribute.UnsignedInt)
            index_attribute.setAttributeType(QAttribute.IndexAttribute)
            index_attribute.setBuffer(index_data_buffer)
            index_attribute.setCount(len(triangles))
            custom_geometry.addAttribute(index_attribute)

            # make the geometry visible with a renderer
            custom_mesh_renderer.setGeometry(custom_geometry)
            custom_mesh_renderer.setInstanceCount(1)
            custom_mesh_renderer.setFirstVertex(0)
            custom_mesh_renderer.setFirstInstance(0)

            # add everything to the scene
            custom_mesh_sub_entity = QEntity(custom_mesh_entity)
            custom_mesh_sub_entity.addComponent(custom_mesh_renderer)
            transform = QTransform()
            transform.setRotationX(-90)
            custom_mesh_sub_entity.addComponent(transform)
            custom_mesh_sub_entity.addComponent(self.material)

            index += 1
            it.Next()


# Our Main function
def main():
    app = 0
    if QApplication.instance():
        app = QApplication.instance()
    else:
        app = QApplication(sys.argv)

    w = IFCQt3dView()
    w.resize(1280, 800)
    filename = sys.argv[1]
    if os.path.isfile(filename):
        w.load_file(filename)
        w.setWindowTitle("IFC Viewer - " + filename)
        w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
