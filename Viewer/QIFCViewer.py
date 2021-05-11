from IFCQt3DView import *
from IFCTreeWidget import *


class QIFCViewer(QMainWindow):
    """
    IFC Model Viewer
    - V1 = Loading the IFCTreeWidget and IFCQt3dView together (as-is)
    """
    def __init__(self):
        QMainWindow.__init__(self)

        self.ifc_file = None
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
        if self.ifc_file is None:
            print("Importing ", filename)
            start = time.time()
            self.ifc_file = ifcopenshell.open(filename)
            print("Loaded ", filename, " in ", time.time() - start, " seconds")

        # print("Loading Views ...")
        start = time.time()
        self.view_3d.ifc_file = self.ifc_file
        self.view_3d.load_file(filename)
        self.view_tree.ifc_file = self.ifc_file
        self.view_tree.load_file(filename)
        print("Loaded views in ", time.time() - start)


# Our Main function
def main():
    app = 0
    if QApplication.instance():
        app = QApplication.instance()
    else:
        app = QApplication(sys.argv)

    w = QIFCViewer()
    w.resize(1280, 800)
    filename = sys.argv[1]
    if os.path.isfile(filename):
        w.load_file(filename)
        w.setWindowTitle("IFC Viewer - " + filename)
        w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
