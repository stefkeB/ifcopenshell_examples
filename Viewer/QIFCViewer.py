from Qt3D_minimal import *
from ifc_treeviewer2 import *


class QIFCViewer(QMainWindow):
    """
    IFC Model Viewer
    - V1 = Loading the ViewTree and View3D together (as-is)
    """
    def __init__(self):
        QMainWindow.__init__(self)

        self.ifc_file = None
        # 3D Widget
        self.view_3d = View3D()
        # Tree Widget
        self.view_tree = ViewTree()

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
