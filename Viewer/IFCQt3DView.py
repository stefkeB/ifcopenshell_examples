# region Imports
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

# endregion


class IFCQt3dView(QWidget):
    """
    3D View Widget
    - V1 = IFC File Loading, geometry parsing & basic navigation
    - V2 = Adding Edges display
    - V3 = Draw Origin Axes & Grid
    - V4 = Object Picking & Selection Syncing (+ reorganise scenegraph)
    - V5 = Working with multiple files (+ reorganise scenegraph again)
    - V6 = Revised Wireframe setup, improved highlights, select also in scenegraph
    """

    # Two signals to extend or shrink the selection
    add_to_selected_entities = pyqtSignal(str)
    remove_from_selected_entities = pyqtSignal(str)

    # region Initialisation

    def __init__(self):
        QWidget.__init__(self)

        # variables
        self.ifc_files = {}  # from filename to IFC model
        self.model_nodes = {}  # from filename to QEntity node
        self.start = time.time()

        # 3D View
        self.view = Qt3DWindow()
        self.view.defaultFrameGraph().setClearColor(QColor("#4466ff"))
        self.container = self.createWindowContainer(self.view)
        self.container.setMinimumSize(QSize(200, 100))
        self.container.setFocusPolicy(Qt.NoFocus)

        # Prepare our scene
        self.root = QEntity()
        self.root.setObjectName("Root")
        self.scene = QEntity()
        self.scene.setObjectName("Scene")
        self.scene.setParent(self.root)
        self.grids = QEntity()
        self.grids.setObjectName("Grids")
        self.grids.setParent(self.scene)
        self.grids.setProperty("IsProduct", True)
        self.display_edges = True
        self.display_meshes = True

        self.files = QEntity()
        self.files.setObjectName("Models")
        self.files.setProperty("IsProduct", True)
        self.files.setParent(self.root)

        # Selection List & Shared Materials
        self.materials = QEntity()
        self.materials.setObjectName("Materials")
        self.materials.setProperty("IsProduct", True)
        self.materials.setParent(self.scene)
        self.selected = []
        self.mat_highlight = QGoochMaterial()
        self.mat_highlight.setObjectName("Shared Highlight Material")
        self.mat_highlight.setShareable(True)
        self.mat_highlight.setDiffuse(QColor(50, 250, 50))
        self.mat_highlight.setShininess(0.5)
        self.materials.addComponent(self.mat_highlight)

        self.material = QPerVertexColorMaterial()
        self.material.setObjectName("Shared Vertex Color Material")
        self.material.setShareable(True)
        self.materials.addComponent(self.material)

        self.transparent = QDiffuseSpecularMaterial()
        self.transparent.setObjectName("Shared Transparent Material")
        self.transparent.setShareable(True)
        self.transparent.setAlphaBlendingEnabled(True)
        self.transparent.setDiffuse(QColor(230, 230, 250, 150))
        self.materials.addComponent(self.transparent)

        self.edge_material = QDiffuseSpecularMaterial()
        self.edge_material.setObjectName("Shared Lines Material")
        self.edge_material.setShareable(True)
        self.edge_material.setDiffuse(QColor(50, 50, 50))
        self.materials.addComponent(self.edge_material)

        self.camera = None
        self.cam_controller = None
        self.initialise_camera()
        self.create_light()
        self.view.setRootEntity(self.root)

        # Axes & Grid
        self.generate_axis(5)
        self.generate_grid(10)

        # Scene Graph
        self.scene_graph = QTreeWidget()
        self.scene_graph.setColumnCount(2)
        self.scene_graph.setHeaderLabels(["Object Name", "Class"])
        # self.scene_graph.selectionModel().selectionChanged.connect(self.toggle_visibility)
        # self.scene_graph.itemChanged.connect(self.toggle_visibility)  # is emitted on almost everything!
        self.scene_graph.itemChanged[QTreeWidgetItem, int].connect(self.toggle_visibility)
        # self.scene_graph.itemPressed.connect(self.toggle_visibility)

        # picking
        self.picking_sphere = None
        picking_settings = self.view.renderSettings().pickingSettings()
        self.picker = QObjectPicker(self.scene)
        self.picker.setObjectName("Picker")
        self.picker.setProperty("IsProduct", True)
        picking_settings.setFaceOrientationPickingMode(QPickingSettings.FrontAndBackFace)
        # set QObjectPicker to PointPicking:
        picking_settings.setPickMethod(QPickingSettings.TrianglePicking)
        # picking_settings.setPickMethod(QPickingSettings.LinePicking)
        # picking_settings.setPickMethod(QPickingSettings.PointPicking)
        picking_settings.setPickResultMode(QPickingSettings.NearestPick)
        # picking_settings.setWorldSpaceTolerance(.5)
        # self.picker.setHoverEnabled(True)
        # self.picker.setDragEnabled(True)
        # self.picker.moved.connect(self.pick)
        # self.picker.pressed.connect(self.pick)
        self.picker.clicked.connect(self.pick)
        # self.picker.released.connect(self.pick)
        self.root.addComponent(self.picker)

        # Finish GUI
        layout = QHBoxLayout()
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        splitter.addWidget(self.container)
        # splitter.addWidget(self.scene_graph)

        vbox = QVBoxLayout()
        # Series of buttons and check boxes in a horizontal layout
        buttons = QWidget()
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        buttons.setLayout(hbox)
        # Add buttons
        # Button : Reset Camera
        btn_camera_reset = QPushButton("Reset")
        btn_camera_reset.setToolTip("Reset the camera position")
        btn_camera_reset.pressed.connect(self.reset_camera)
        hbox.addWidget(btn_camera_reset)
        # Button : Store Camera
        btn_camera_store = QPushButton("Store")
        btn_camera_store.setToolTip("Store the camera position")
        btn_camera_store.pressed.connect(self.store_camera)
        hbox.addWidget(btn_camera_store)
        # Button : Rotate Camera
        btn_camera_rotate = QPushButton("Rotate")
        btn_camera_rotate.setToolTip("Turntable 30° around pick point")
        btn_camera_rotate.pressed.connect(self.rotate_around_position)
        hbox.addWidget(btn_camera_rotate)
        self.pick_position = QVector3D(0, 0, 0)
        # Button : Update Tree
        btn_update_tree = QPushButton("Update")
        btn_update_tree.setToolTip("Update Scenegraph Tree")
        btn_update_tree.pressed.connect(self.update_scene_graph_tree)
        hbox.addWidget(btn_update_tree)
        # Option: Display Meshes
        check_ms = QCheckBox("Meshes")
        check_ms.setToolTip("Display all meshes")
        check_ms.setChecked(self.display_meshes)
        check_ms.toggled.connect(self.toggle_meshes)
        hbox.addWidget(check_ms)
        # Option: Display Wireframe
        check_wf = QCheckBox("Wireframe")
        check_wf.setToolTip("Display all edges")
        check_wf.setChecked(self.display_edges)
        check_wf.toggled.connect(self.toggle_wireframe)
        hbox.addWidget(check_wf)
        btn_show_wireframe = QCheckBox("Wireframe")
        btn_camera_store.setToolTip("Store the camera position")
        btn_camera_store.pressed.connect(self.store_camera)
        hbox.addWidget(btn_camera_store)
        # Stretchable Spacer
        spacer = QSpacerItem(10, 10, QSizePolicy.Expanding)
        hbox.addSpacerItem(spacer)
        # Add Scenegraph
        scenegraph = QWidget()
        scenegraph.setLayout(vbox)
        vbox.addWidget(buttons)
        vbox.addWidget(self.scene_graph)
        splitter.addWidget(scenegraph)

        self.setLayout(layout)

    # endregion

    # region SelectionMethods

    def select_object_by_id(self, object_id):
        print("IFCQt3dView.select_object_by_id ", object_id)
        for f in self.files.children():
            for e in f.children():
                if e.objectName() == object_id:
                    self.selected.append(e)
                    self.set_highlight(e)
                    return

    def deselect_object_by_id(self, object_id):
        print("IFCQt3dView.deselect_object_by_id ", object_id)
        for f in self.files.children():
            for e in f.children():
                if e.objectName() == object_id:
                    self.set_highlight(e, False)
                    if e in self.selected:
                        self.selected.remove(e)
                    return

    def toggle_entity(self, entity):
        print("IFCQt3dView.toggle_entity ", entity.objectName())
        if entity in self.selected:
            self.selected.remove(entity)
            self.set_highlight(entity, False)
        else:
            self.selected.append(entity)
            self.set_highlight(entity)

    def set_highlight(self, entity, on=True):
        """
        Set the given QEntity to the highlight material

        :param entity: the geometry to highlight
        :type entity: QEntity
        :param on: True = set highlight, False = remove
        :param on: bool
        """
        # Switch the Material from our Mesh Child
        if on is False:
            for c in entity.children():
                c.removeComponent(self.mat_highlight)
                if c.property("IsTransparent") is True:
                    c.addComponent(self.transparent)
                else:
                    c.addComponent(self.material)
            self.highlight_in_scene_graph(entity, False)
        else:
            for c in entity.children():
                if c.property("IsTransparent") is True:
                    c.removeComponent(self.transparent)
                else:
                    c.removeComponent(self.material)
                if c.property("IsWireframe") is True:
                    c.addComponent(self.material)
                else:
                    c.addComponent(self.mat_highlight)
            self.highlight_in_scene_graph(entity)

    def select_exclusive_entity(self, entity):
        print("IFCQt3dView.select_exclusive_entity ", entity)
        for e in self.selected:
            if e is not entity:
                self.set_highlight(e, False)
                self.remove_from_selected_entities.emit(e.objectName())
        self.selected.clear()
        self.selected.append(entity)
        self.set_highlight(entity)
        self.add_to_selected_entities.emit(entity.objectName())

    def pick(self, e: QPickTriangleEvent):
        position = e.position()  # screen space
        localPosition = e.localIntersection()  # model space
        worldPosition = e.worldIntersection()  # world space QVector3D
        self.pick_position = worldPosition

        entity = e.entity()
        if entity is None:
            return
        # Picked mesh is child of container entity "parent"
        parent = entity.parentEntity()
        GlobalId = parent.objectName()
        print("IFCQt3dView.pick (" + GlobalId + ")")

        if e.button() == Qt.LeftButton and e.modifiers() == Qt.ControlModifier:
            self.toggle_entity(parent)
        else:
            if e.button() == Qt.LeftButton and e.modifiers() == Qt.ShiftModifier:
                # up = self.view.camera().upVector()
                self.view.camera().setViewCenter(worldPosition)
                self.view.camera().setUpVector(QVector3D(0, 1, 0))

                # Place the picking sphere at the Pick position
                if False:
                    if self.picking_sphere is None:
                        self.picking_sphere = QEntity(self.scene)
                        self.picking_sphere.setObjectName("Picking Sphere")
                        material = QPhongMaterial()
                        material.setAmbient(QColor(100, 50, 50))
                        material.setDiffuse(QColor(200, 150, 150))
                        self.picking_sphere.addComponent(material)
                        sphere_mesh = QSphereMesh()
                        sphere_mesh.setRadius(0.1)
                        self.picking_sphere.addComponent(sphere_mesh)
                    sphere_position = QTransform()
                    sphere_position.setTranslation(worldPosition)
                    self.picking_sphere.addComponent(sphere_position)
                    # self.generate_axis(5, worldPosition)
            elif e.button() == Qt.LeftButton:
                self.select_exclusive_entity(parent)

    # endregion

    def toggle_meshes(self):
        # Parse the whole Scenegraph and hide all branches with a Triangle Renderer

        # iterate over children
        for filename, model in self.model_nodes.items():
            for ifc_entity in model.children():
                for representation in ifc_entity.children():
                    # self.update_scene_graph_tree(item, node_item)
                    if representation.property("IsWireframe") is None:
                        representation.setEnabled(not representation.isEnabled())

    def toggle_wireframe(self, enabled=True):
        # Parse the whole Scenegraph and hide all branches with a Lines Renderer

        # iterate over children
        for filename, model in self.model_nodes.items():
            for ifc_entity in model.children():
                for representation in ifc_entity.children():
                    # self.update_scene_graph_tree(item, node_item)
                    if representation.property("IsWireframe") is True:
                        representation.setEnabled(not representation.isEnabled())

    # region SceneMethods

    def reset_camera(self):
        # self.cam_index = 0
        # self.cameras = []
        # controlled_cam = self.cam_controller.camera()
        view_cam = self.view.camera()
        # view_cam.lens().setPerspectiveProjection(45.0, 16.0 / 9.0, 0.1, 200)  # 16.0 / 9.0, 0.1, 200)
        # view_cam.setPosition(QVector3D(0, 0, 40))
        # view_cam.setViewCenter(QVector3D(0, 0, 0))
        # view_cam.setUpVector(QVector3D(0, 1, 0))
        # view_cam.setFieldOfView(45.0)

        view_cam.setPosition(self.cam_pos)
        view_cam.setViewCenter(self.cam_viewcenter)
        view_cam.setFieldOfView(self.cam_fieldofview)
        view_cam.setUpVector(self.cam_upvector)

        # self.cameras.append(view_cam)
        # cam_ortho = QCamera()
        # cam_ortho.lens().setOrthographicProjection(5.0, 5.0, 5.0, 5.0, 0.0, 200.0)
        # cam_ortho.setPosition(QVector3D(30, 30, 30))
        # cam_ortho.setViewCenter(QVector3D(0, 0, 0))
        # self.cameras.append(cam_ortho)
        #
        # self.camera = self.cameras[1]

    def store_camera(self):
        # capture current camera in a list
        camera = self.view.camera()
        self.cam_pos = camera.position()
        self.cam_viewcenter = camera.viewCenter()
        self.cam_viewvector = camera.viewVector()
        self.cam_fieldofview = camera.fieldOfView()
        self.cam_upvector = camera.upVector()
        pass

    def rotate_around_position(self, position=QVector3D(0,0,0), angle=30, rotation_axis=QVector3D(0,1,0)):
        # capture current matrix
        matrix = self.view.camera().transform().matrix()
        # move to position
        matrix.translate(-self.pick_position)
        # do the rotation
        matrix.rotate(30, QVector3D(0, 1, 0))
        # translate back
        matrix.translate(self.pick_position)
        # apply matrix
        self.view.camera().transform().setMatrix(matrix)
        pass

    def initialise_camera(self):
        # camera
        if self.camera is None:
            self.camera = self.view.camera()
            self.camera.setObjectName("Camera")
            ratio = self.view.width() / self.view.height()
            self.camera.lens().setPerspectiveProjection(45.0, ratio, 0.1, 200)  # 16.0 / 9.0, 0.1, 200)
            self.camera.setPosition(QVector3D(0, 0, 40))
            self.camera.setViewCenter(QVector3D(0, 0, 0))
            self.camera.setUpVector(QVector3D(0, 1, 0))
            self.camera.setFieldOfView(45.0)

            self.cam_pos = self.camera.position()
            self.cam_viewcenter = self.camera.viewCenter()
            self.cam_viewvector = self.camera.viewVector()
            self.cam_fieldofview = self.camera.fieldOfView()
            self.cam_upvector = self.camera.upVector()

        # for camera control
        if self.cam_controller is None:
            self.cam_controller = QOrbitCameraController(self.scene)
            # self.cam_controller = QFirstPersonCameraController(self.scene)
            self.cam_controller.setObjectName("Orbit Camera Controller")
            self.cam_controller.setLinearSpeed(50.0)
            self.cam_controller.setLookSpeed(180.0)
            self.cam_controller.setCamera(self.camera)

    def create_light(self):
        # Light
        self.lights = QEntity(self.scene)
        self.lights.setObjectName("Lights")
        self.lights.setProperty("IsProduct", True)

        # Light 1
        light_entity = QEntity(self.lights)
        light_entity.setObjectName("Light Entity 1")
        light_entity.setProperty("IsProduct", True)
        light = QPointLight(light_entity)
        light.setObjectName("Point Light")
        light.setColor(QColor.fromRgbF(1.0, 1.0, 1.0, 1.0))
        light.setIntensity(1)
        light_entity.addComponent(light)
        light_transform = QTransform(light_entity)
        light_transform.setObjectName("Light Transform")
        light_transform.setTranslation(QVector3D(10.0, 40.0, 0.0))
        light_entity.addComponent(light_transform)

        # Light 2
        light_entity2 = QEntity(self.lights)
        light_entity2.setObjectName("Light Entity 2")
        light_entity2.setProperty("IsProduct", True)
        light2 = QPointLight(light_entity2)
        light2.setObjectName("Point Light")
        light2.setColor(QColor.fromRgbF(0.8, 0.8, 1.0, 1.0))
        light2.setIntensity(1)
        light_entity2.addComponent(light2)
        light_transform2 = QTransform(light_entity2)
        light_transform2.setObjectName("Light Transform")
        light_transform2.setTranslation(QVector3D(10.0, -40.0, 0.0))
        light_entity2.addComponent(light_transform2)

    # endregion

    # region FileMethods

    def close_files(self):
        for child in self.files.children():
            child.setParent(None)
        self.update_scene_graph_tree()
        self.model_nodes.clear()
        self.selected.clear()
        pass

    def load_file(self, filename):
        """
        Load the file passed as filename and generates the geometry.
        If it already exists, the geometry is removed and recreated.

        :param filename: Full path to the IFC file
        """
        ifc_file = None
        if filename in self.ifc_files:
            ifc_file = self.ifc_files[filename]
        else:  # Load as new file
            print("Importing IFC file ...")
            start = time.time()
            ifc_file = ifcopenshell.open(filename)
            self.ifc_files[filename] = ifc_file
            print("Loaded in ", time.time() - start)

        model_node = None
        if filename in self.model_nodes:
            model_node = self.model_nodes[filename]
            for element in model_node.children():
                element.setParent(None)
        else:
            model_node = QEntity(self.files)
            self.model_nodes[filename] = model_node
            model_node.setProperty("IsProduct", True)
            model_node.setObjectName(filename)

        print("Importing IFC geometrical information ...")
        self.start = time.time()
        settings = ifcopenshell.geom.settings()
        settings.set(settings.WELD_VERTICES, False)  # false is needed to generate normals -- slower
        # settings.set(settings.NO_NORMALS, True)  # disable generation of normals
        settings.set(settings.USE_WORLD_COORDS, True)  # true = ignore transformation
        # settings.set(settings.SEW_SHELLS, True)  # true default - slightly slower?
        # settings.set(settings.GENERATE_UVS, True)  # true default
        settings.set(settings.FASTER_BOOLEANS, True)  # merge opening Booleans before subtracting
        # settings.set(settings.DISABLE_TRIANGULATION, True)  # if using OCC formats
        # settings.set(settings.USE_BREP_DATA, True)  # use OCC BREP data
        # settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, True)
        # settings.set(settings.DISABLE_BOOLEAN_RESULT, True) # works
        # settings.set(settings.DISABLE_OPENING_SUBTRACTIONS, True) # works
        # settings.set(settings.STRICT_TOLERANCE, False)  # default kernel tolerance to 1 = True
        # settings.set(settings.APPLY_LAYERSETS, True)  # geometry for individual layers
        settings.set(settings.APPLY_DEFAULT_MATERIALS, True)  # assign default material for elements without
        # settings.set_angular_tolerance(1)
        # settings.set_deflection_tolerance(1)  # default = 1e-3

        settings.set(settings.USE_PYTHON_OPENCASCADE, True)

        # Two methods
        # self.parse_project(filename, settings)  # SLOWER - create geometry for each product
        self.parse_geometry(filename, settings)  # FASTER - iteration with parallel processing
        print("\nFinished in ", time.time() - self.start)

        self.update_scene_graph_tree()
        self.scene_graph.expandToDepth(1)

    # endregion

    # region SceneGraphMethods

    def toggle_visibility(self, tree_item, column):
        # get the widget item
        if tree_item is not None and column == 0:
            # get its user data
            entity = tree_item.data(0, Qt.UserRole)
            if entity is not None:
                if entity.property("IsProduct") is True:
                    # TODO: this is the opposite of what we expect...
                    entity.setEnabled(not entity.isEnabled())
                    # set visibility to reflect the check state
                    if tree_item.checkState(0) == Qt.Checked:
                        # if not entity.isEnabled():
                        #    entity.setEnabled(True)
                        var = 1
                    if tree_item.checkState(0) == Qt.Unchecked:
                        var = 2
                        # if entity.isEnabled():
                        #    entity.setEnabled(False)

    def highlight_in_scene_graph(self, entity, highlight=True):
        """
        Highlight the entity in the scene graph

        :type entity: QEntity
        :type highlight: bool
        """
        iterator = QTreeWidgetItemIterator(self.scene_graph)
        while iterator.value():
            item = iterator.value()
            qentity = item.data(0, Qt.UserRole)
            if entity == qentity:
                item.setSelected(highlight)
                self.scene_graph.scrollToItem(item)
            iterator += 1

    def update_scene_graph_tree(self, node=None, parent=None):
        """
        Recursive update of the tree representing the 3D scene graph.
        This only takes the scene_graph itself into account.
        The TreeItems carry a reference to the QEntity node.
        The nodes are named with their IFC Object GlobalId.
        Nodes which represent an IfcProduct (or some grouping),
        get a check box to toggle the visibility of the QEntity.

        :param node: current QEntity
        :type node: QEntity
        :param parent: parent QTreeWidgetItem
        :type parent: QTreeWidgetItem
        """
        if node is None:
            node = self.root
        if parent is None:
            parent = self.scene_graph.invisibleRootItem()
            self.scene_graph.clear()

        node_item = QTreeWidgetItem([node.objectName(), node.metaObject().className()])
        parent.addChild(node_item)

        # Add a reference to the QEntity
        if node.property("IsProduct") is True:
            node_item.setData(0, Qt.UserRole, node)
            node_item.setData(0, Qt.ToolTipRole, str("{} - {}").format(node.objectName(), "IsProduct"))

            # display checkbox for Enabled Items
            node_item.setFlags(node_item.flags() | Qt.ItemIsUserCheckable)
            # TODO: this is the opposite of what we expect...
            if node.isEnabled():
                node_item.setCheckState(0, Qt.Unchecked)
            else:
                node_item.setCheckState(0, Qt.Checked)

        # iterate over children
        for item in node.children():
            self.update_scene_graph_tree(item, node_item)

    # endregion

    # region GeometryMethods

    def parse_geometry(self, filename, settings):
        ifc_file = self.ifc_files[filename]
        iterator = ifcopenshell.geom.iterator(settings, ifc_file, multiprocessing.cpu_count())
        iterator.initialize()
        counter = 0
        while True:
            shape = iterator.get()
            # skip openings and spaces geometry
            if not shape.data.product.is_a('IfcOpeningElement') and not shape.data.product.is_a('IfcSpace'):
                try:
                    self.generate_rendermesh(shape, self.model_nodes[filename])
                    print(str("Shape {0}\t[#{1}]\tin {2} seconds")
                          .format(str(counter), str(shape.data.id), time.time() - self.start))
                except Exception as e:
                    print(str("Shape {0}\t[#{1}]\tERROR - {2} : {3}")
                          .format(str(counter), str(shape.data.id), shape.data.product.is_a(), e))
                    pass
            counter += 1
            if not iterator.next():
                break

    def parse_project(self, filename, settings):
        ifc_file = self.ifc_files[filename]
        # parse all products
        products = ifc_file.by_type('IfcProduct')
        counter = 0
        for product in products:
            if not product.is_a('IfcOpeningElement') and not product.is_a('IfcSpace'):
                if product.Representation:
                    shape = ifcopenshell.geom.create_shape(settings, product)
                    self.generate_rendermesh(shape, self.model_nodes[filename])
                    print(str("Product {0}\t[#{1}]\tin {2} seconds")
                          .format(str(counter), str(product.id()), time.time() - self.start))
            counter += 1

    def parse_shape(self, geometry):
        # compute the tessellation
        tess = ShapeTesselator(geometry)
        tess.Compute(compute_edges=True)
        # tess.Compute(compute_edges=False, mesh_quality=1.0, parallel=True)

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

        # get the edges
        edges = []
        edge_count = tess.ObjGetEdgeCount()
        for i_edge in range(0, edge_count):
            vertex_count = tess.ObjEdgeGetVertexCount(i_edge)
            # edge = []
            for i_vertex in range(0, vertex_count):
                vertex = tess.GetEdgeVertex(i_edge, i_vertex)
                # edge.append(vertex)
                # edges.append(i_vertex)
                edges.append(vertex[0])
                edges.append(vertex[1])
                edges.append(vertex[2])
            # edges.append(edge)

        return vertices, normals, triangles, edges

    def generate_rendermesh(self, shape, parent):
        """
        Collecting the mesh geometry using OCC for the current TopoDS Shape.
        The vertices, edges, triangles and colors are used to create the
        Qt3D Entities & Nodes & Components for the 3D Representation.

        :param shape: TopoDS Shape (from OpenCASCADE)
        :param parent: QEntity parent Node (representing the File node)
        """
        data = shape.data
        geometry = shape.geometry
        styles = shape.styles
        style_ids = shape.style_ids

        custom_mesh_entity = QEntity(parent)
        custom_mesh_entity.setObjectName(shape.data.guid)
        custom_mesh_entity.setProperty("IsProduct", True)
        custom_mesh_entity.setProperty("GlobalId", shape.data.guid)

        it = OCC.Core.TopoDS.TopoDS_Iterator(geometry)
        index = 0
        while it.More():
            vertices, normals, triangles, edges = self.parse_shape(it.Value())

            # ------ MESH --------------------------
            custom_mesh_renderer = QGeometryRenderer()
            custom_mesh_renderer.setObjectName("Mesh Renderer")
            custom_mesh_renderer.setPrimitiveType(QGeometryRenderer.Triangles)
            custom_geometry = QGeometry(custom_mesh_renderer)
            custom_geometry.setObjectName("Custom Geometry")

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
            position_attribute.setObjectName("Position Vertex Attribute")
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
                normal_attribute.setObjectName("Normal Vertex Attribute")
                custom_geometry.addAttribute(normal_attribute)

            # Collect the colors via the materials (1 color per vertex)
            # we get a list of styles (ids) and surface styles (rgba values)
            # expressed per shape, not per vertex, so repeat them
            s_style = styles[index]
            r = s_style[0]
            g = s_style[1]
            b = s_style[2]
            a = s_style[3]
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
            color_attribute.setObjectName("Color Vertex Attribute")
            custom_geometry.addAttribute(color_attribute)

            # Faces Index Attribute
            index_data_buffer = QBuffer(QBuffer.IndexBuffer, custom_geometry)
            # index_data_buffer.setData(QByteArray(np.array(triangles).astype(np.uintc).tobytes()))
            index_data_buffer.setData(struct.pack("{}I".format(len(triangles)), *triangles))
            index_data_buffer.setObjectName("Index Data Buffer")
            index_attribute = QAttribute()
            index_attribute.setVertexBaseType(QAttribute.UnsignedInt)
            index_attribute.setAttributeType(QAttribute.IndexAttribute)
            index_attribute.setBuffer(index_data_buffer)
            index_attribute.setCount(len(triangles))
            index_attribute.setName("Indices")
            index_attribute.setObjectName("Index Unsigned Int Attribute")
            custom_geometry.addAttribute(index_attribute)

            # make the geometry visible with a renderer
            custom_mesh_renderer.setGeometry(custom_geometry)
            custom_mesh_renderer.setInstanceCount(1)
            custom_mesh_renderer.setFirstVertex(0)
            custom_mesh_renderer.setFirstInstance(0)

            # add everything to the scene
            custom_mesh_sub_entity = QEntity(custom_mesh_entity)
            custom_mesh_sub_entity.addComponent(custom_mesh_renderer)
            custom_mesh_sub_entity.setObjectName("Mesh")  # ifc_object.GlobalId)
            transform = QTransform()
            transform.setObjectName("Rotate X -90°")
            transform.setRotationX(-90)
            custom_mesh_sub_entity.addComponent(transform)
            if a < 1.0:
                custom_mesh_sub_entity.addComponent(self.transparent)
                custom_mesh_sub_entity.setProperty("IsTransparent", True)
            else:
                custom_mesh_sub_entity.addComponent(self.material)

            # ------ EDGES --------------------------
            custom_line_renderer = QGeometryRenderer()
            custom_line_renderer.setObjectName("Lines Renderer")
            custom_line_renderer.setPrimitiveType(QGeometryRenderer.Lines)
            custom_line_geometry = QGeometry(custom_line_renderer)
            custom_line_geometry.setObjectName("Custom Lines Geometry")

            # Position Attribute
            position_data_buffer = QBuffer(QBuffer.VertexBuffer, custom_line_geometry)
            # position_data_buffer.setData(QByteArray(np.array(edges).astype(np.float32).tobytes()))
            position_data_buffer.setData(struct.pack('%sf' % len(edges), *edges))
            position_attribute = QAttribute()
            position_attribute.setAttributeType(QAttribute.VertexAttribute)
            position_attribute.setBuffer(position_data_buffer)
            position_attribute.setVertexBaseType(QAttribute.Float)
            position_attribute.setVertexSize(3)  # 3 floats
            position_attribute.setByteOffset(0)  # start from first index
            position_attribute.setByteStride(3 * 4)  # 3 coordinates and 4 as length of float32 in bytes
            position_attribute.setCount(len(edges))  # vertices
            position_attribute.setName(QAttribute.defaultPositionAttributeName())
            custom_line_geometry.addAttribute(position_attribute)

            # Edges Index Attribute
            indices_edges = list(range(int(len(edges) / 3)))
            index_data_buffer = QBuffer(QBuffer.IndexBuffer, custom_line_geometry)
            # index_data_buffer.setData(QByteArray(np.array(indices_edges).astype(np.uintc).tobytes()))
            index_data_buffer.setData(struct.pack("{}I".format(len(indices_edges)), *indices_edges))
            index_data_buffer.setObjectName("Index Data Buffer")
            index_attribute = QAttribute()
            index_attribute.setVertexBaseType(QAttribute.UnsignedInt)
            index_attribute.setAttributeType(QAttribute.IndexAttribute)
            index_attribute.setBuffer(index_data_buffer)
            index_attribute.setCount(len(indices_edges))
            index_attribute.setName("Indices")
            index_attribute.setObjectName("Index Unsigned Int Attribute")
            custom_line_geometry.addAttribute(index_attribute)

            # make the geometry visible with a renderer
            custom_line_renderer.setGeometry(custom_line_geometry)
            custom_line_renderer.setInstanceCount(1)
            custom_line_renderer.setFirstVertex(0)
            custom_line_renderer.setFirstInstance(0)

            # add everything to the scene
            custom_line_entity = QEntity(custom_mesh_entity)  # TODO: rethink scenegraph
            custom_line_entity.setObjectName("Line")
            custom_line_entity.setProperty("IsWireframe", True)
            transform = QTransform()
            transform.setObjectName("Rotate X -90°")
            transform.setRotationX(-90)
            custom_line_entity.addComponent(transform)
            custom_line_entity.addComponent(custom_line_renderer)
            custom_line_entity.addComponent(self.edge_material)

            index += 1
            it.Next()

    def generate_line(self, start, end):
        vertices = start + end
        self.generate_primitive(vertices)

    def generate_axis(self, size, pos=None):
        if pos is None:
            pos = [0, 0, 0]
        elif type(pos) == QVector3D:
            pos = [pos.x(), pos.y(), pos.z()]
        x, y, z = pos[0], pos[1], pos[2]
        x_axis = [x, y, z, x + size, y, z]
        y_axis = [x, y, z, x, y + size, z]
        z_axis = [x, y, z, x, y, z + size]
        self.generate_primitive(x_axis, [1, 0, 0])
        self.generate_primitive(y_axis, [0, 1, 0])
        self.generate_primitive(z_axis, [0, 0, 1])

    def generate_grid(self, extent, pos=None, step_size=1):
        if pos is None:
            pos = [0, 0, 0]
        elif type(pos) == QVector3D:
            pos = [pos.x(), pos.y(), pos.z()]
        x, y, z = pos[0], pos[1], pos[2]
        for h in range(-extent, extent + step_size, step_size):
            grid_line = [x + h, y - extent, z, x + h, y + extent, z]
            self.generate_primitive(grid_line)
        for v in range(-extent, extent + step_size, step_size):
            grid_line = [x - extent, y + v, z, x + extent, y + v, z]
            self.generate_primitive(grid_line)

    def generate_primitive(self,
                           coordinates,
                           colors=None,
                           primitive=QGeometryRenderer.Lines):
        # coordinates = [x1, y1, z1, x2, y2, z2, ...]
        if colors is None:
            colors = [0.5, 0.5, 0.5]
        if len(colors) != len(coordinates):
            color_list = colors * int(len(coordinates) / len(colors))
        else:
            color_list = colors

        custom_line_renderer = QGeometryRenderer()
        custom_line_renderer.setPrimitiveType(primitive)
        custom_geometry = QGeometry(custom_line_renderer)

        # Position Attribute
        position_data_buffer = QBuffer(QBuffer.VertexBuffer, custom_geometry)
        # position_data_buffer.setData(QByteArray(np.array(coordinates).astype(np.float32).tobytes()))
        position_data_buffer.setData(struct.pack('%sf' % len(coordinates), *coordinates))
        position_attribute = QAttribute()
        # position_attribute.setAttributeType(QAttribute.VertexAttribute)
        position_attribute.setBuffer(position_data_buffer)
        # position_attribute.setVertexBaseType(QAttribute.Float)
        position_attribute.setVertexSize(3)  # 3 floats
        # position_attribute.setByteOffset(0)  # start from first index
        # position_attribute.setByteStride(3 * 4)  # 3 coordinates and 4 as length of float32 in bytes
        # position_attribute.setCount(len(coordinates))  # vertices
        position_attribute.setName(QAttribute.defaultPositionAttributeName())
        custom_geometry.addAttribute(position_attribute)

        # Color Attribute
        color_data_buffer = QBuffer(QBuffer.VertexBuffer, custom_geometry)
        # color_data_buffer.setData(QByteArray(np.array(color_list).astype(np.float32).tobytes()))
        color_data_buffer.setData(struct.pack('%sf' % len(color_list), *color_list))
        color_attribute = QAttribute()
        # color_attribute.setAttributeType(QAttribute.VertexAttribute)
        color_attribute.setBuffer(color_data_buffer)
        # color_attribute.setVertexBaseType(QAttribute.Float)
        color_attribute.setVertexSize(3)  # 3 floats
        # color_attribute.setByteOffset(0)  # start from first index
        # color_attribute.setByteStride(3 * 4)  # 3 coordinates and 4 as length of float32 in bytes
        color_attribute.setCount(len(color_list))  # colors (per vertex)
        color_attribute.setName(QAttribute.defaultColorAttributeName())
        custom_geometry.addAttribute(color_attribute)

        # ----------------------------------------------------------------------------
        # make the geometry visible with a renderer
        custom_line_renderer.setGeometry(custom_geometry)
        custom_line_renderer.setInstanceCount(1)
        custom_line_renderer.setFirstVertex(0)
        custom_line_renderer.setFirstInstance(0)

        # add everything to the scene
        custom_line_entity = QEntity(self.grids)
        custom_line_entity.setObjectName("Line")
        transform = QTransform()
        transform.setObjectName("Rotate X -90°")
        transform.setRotationX(-90)
        custom_line_entity.addComponent(transform)
        custom_line_entity.addComponent(custom_line_renderer)
        custom_line_entity.addComponent(self.material)

    # endregion


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
