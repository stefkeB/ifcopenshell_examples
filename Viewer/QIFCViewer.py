from IFCQt3DView import *
from IFCTreeWidget import *


class QIFCViewer(QMainWindow):
    """
    IFC Model Viewer
    - V1 = Loading the IFCTreeWidget and IFCQt3dView together (as-is)
    - V2 = Open + Save methods, Toolbar and Status Bar & Files in a Dictionary
    """
    def __init__(self):
        QMainWindow.__init__(self)

        # A dictionary referring to our files, based on name
        self.ifc_files = {}
        self.ifc_file = None
        self.ifc_filename = None

        # menu, actions and toolbar
        toolbar = QToolBar("My main toolbar")
        self.addToolBar(toolbar)

        action_open = QAction("Open...", self)
        action_open.setShortcut("CTRL+O")
        action_open.setStatusTip("Open an IFC Model")
        action_open.triggered.connect(self.get_file)
        toolbar.addAction(action_open)

        action_save = QAction("Save", self)
        action_save.setShortcut("CTRL+S")
        action_save.setStatusTip("Save the IFC Model")
        action_save.triggered.connect(self.save)
        toolbar.addAction(action_save)

        self.setStatusBar(QStatusBar(self))


        # 3D Widget
        self.view_3d = IFCQt3dView()
        # Tree Widget
        self.view_tree = IFCTreeWidget()

        # Selection Syncing
        self.view_tree.select_object.connect(self.view_3d.select_object_by_id)
        self.view_tree.deselect_object.connect(self.view_3d.deselect_object_by_id)
        self.view_3d.add_to_selected_entities.connect(self.view_tree.receive_selection)

        # Docking Widgets
        self.dock = QDockWidget('Model Tree', self)
        self.dock.setWidget(self.view_tree)
        self.dock.setFloating(False)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

        # Main Widget = 3D View
        self.setCentralWidget(self.view_3d)

    def load_file(self, filename):
        # if self.ifc_file is None:
        print("Importing ", filename)
        start = time.time()
        self.ifc_file = ifcopenshell.open(filename)
        print("Loaded ", filename, " in ", time.time() - start, " seconds")
        self.ifc_filename = filename
        self.ifc_files[filename] = self.ifc_file

        # print("Loading Views ...")
        start = time.time()
        self.view_3d.ifc_file = self.ifc_file
        self.view_3d.load_file(filename)
        self.view_tree.ifc_file = self.ifc_file
        self.view_tree.load_file(filename)
        print("Loaded views in ", time.time() - start)

    def save(self):
        if self.ifc_file is None:
            return
        else:
            self.ifc_file.write(self.ifc_filename)

    def get_file(self):
        filenames, filter_string = QFileDialog.getOpenFileNames(self, caption="Open IFC File",
                                                                filter="IFC files (*.ifc)")

        # self.setWindowTitle("IFC Viewer")
        for file in filenames:
            if os.path.isfile(file):
                self.load_file(file)
                self.setWindowTitle(self.windowTitle() + " - " + os.path.basename(file))


# Our Main function
def main():
    app = 0
    if QApplication.instance():
        app = QApplication.instance()
    else:
        app = QApplication(sys.argv)

    w = QIFCViewer()
    w.setWindowTitle("IFC Viewer")
    w.resize(1280, 800)
    filename = sys.argv[1]
    if os.path.isfile(filename):
        w.load_file(filename)
        w.setWindowTitle(w.windowTitle() + " - " + os.path.basename(filename))
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
