from IFCQt3DView import *
from IFCTreeWidget import *
from IFCPropertyWidget import *


class QIFCViewer(QMainWindow):
    """
    IFC Model Viewer
    - V1 = Loading the IFCTreeWidget and IFCQt3dView together (as-is)
    - V2 = Open + Save methods, Toolbar and Status Bar & Files in a Dictionary
    - V3 = Use separate Tree Views as two separate Dock Widgets and link them
    """
    def __init__(self):
        QMainWindow.__init__(self)

        # A dictionary referring to our files, based on name
        self.ifc_files = {}

        # menu, actions and toolbar
        toolbar = QToolBar("My main toolbar")
        self.addToolBar(toolbar)
        menu_bar = self.menuBar()
        file_menu = QMenu("&File", self)
        menu_bar.addMenu(file_menu)

        action_open = QAction("Open...", self)
        action_open.setShortcut("CTRL+O")
        action_open.setStatusTip("Open an IFC Model")
        action_open.triggered.connect(self.get_file)
        toolbar.addAction(action_open)
        file_menu.addAction(action_open)

        action_save = QAction("Save All", self)
        action_save.setShortcut("CTRL+S")
        action_save.setStatusTip("Saves all IFC Models")
        action_save.triggered.connect(self.save_files)
        toolbar.addAction(action_save)
        file_menu.addAction(action_save)

        action_close = QAction("Close All", self)
        action_close.setShortcut("CTRL+W")
        action_close.setStatusTip("Close all IFC Models")
        action_close.triggered.connect(self.close_files)
        toolbar.addAction(action_close)
        file_menu.addAction(action_close)

        action_quit = QAction("Quit", self)
        action_quit.setShortcut("CTRL+Q")
        action_quit.setStatusTip("Quit the application")
        action_quit.triggered.connect(qApp.quit)
        file_menu.addAction(action_quit)

        self.setStatusBar(QStatusBar(self))

        # Main Widgets
        self.view_3d = IFCQt3dView()
        self.view_tree = IFCTreeWidget()
        self.view_properties = IFCPropertyWidget()

        # Selection Syncing
        self.view_tree.select_object.connect(self.view_3d.select_object_by_id)
        self.view_tree.deselect_object.connect(self.view_3d.deselect_object_by_id)
        self.view_3d.add_to_selected_entities.connect(self.view_tree.receive_selection)
        self.view_tree.send_selection_set.connect(self.view_properties.set_from_selected_items)

        # Docking Widgets
        self.dock = QDockWidget('Model Tree', self)
        self.dock.setWidget(self.view_tree)
        self.dock.setFloating(False)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

        self.dock2 = QDockWidget('Property Tree', self)
        self.dock2.setWidget(self.view_properties)
        self.dock2.setFloating(False)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock2)

        # Main Widget = 3D View
        self.setCentralWidget(self.view_3d)

    def load_file(self, filename):
        """
        Load an IFC file from the given path. If the file was already loaded,
        the user is asked if the file should be replaced.

        :param filename: full path to the IFC file
        :return: True if the file was loaded, False if cancelled.
        """
        if filename in self.ifc_files:
            # Display warning that this model was already loaded. Replace or Cancel.
            dlg = QMessageBox(self.parent())
            dlg.setWindowTitle("Model already loaded!")
            dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            dlg.setText("Do you want to replace the currently loaded model?")
            button = dlg.exec_()
            if button == QMessageBox.Cancel:
                return False

        start = time.time()
        ifc_file = ifcopenshell.open(filename)
        print("Loaded ", filename, " in ", time.time() - start, " seconds")
        self.ifc_files[filename] = ifc_file

        # print("Loading Views ...")
        start = time.time()
        self.view_tree.ifc_files[filename] = ifc_file
        self.view_tree.load_file(filename)

        self.view_3d.ifc_files[filename] = ifc_file
        self.view_3d.load_file(filename)
        print("Loaded all views in ", time.time() - start)
        return True

    def save_files(self):
        """
        Save all currently loaded files
        """
        for ifc_filename, ifc_file in self.ifc_files.items():
            ifc_file.write(ifc_filename)

    def get_file(self):
        """
        Get a File Open dialog to select IFC files to load in the project
        """
        filenames, filter_string = QFileDialog.getOpenFileNames(self, caption="Open IFC File",
                                                                filter="IFC files (*.ifc)")

        # self.setWindowTitle("IFC Viewer")
        for file in filenames:
            if os.path.isfile(file):
                if self.load_file(file):
                    # Concatenate all file names
                    title = "IFC Viewer"
                    for filename, file in self.ifc_files.items():
                        title += " - " + os.path.basename(filename)
                    if len(title) > 64:
                        title = title[:64] + "..."
                    self.setWindowTitle(title)

    def close_files(self):
        """
        Close all loaded files (and clear the different views)
        """
        self.ifc_files = {}
        self.view_tree.close_files()
        self.view_properties.reset()
        self.view_3d.close_files()
        self.setWindowTitle("IFC Viewer")


# Our Main function
def main():
    app = 0
    if QApplication.instance():
        app = QApplication.instance()
    else:
        app = QApplication(sys.argv)
    app.setApplicationDisplayName("IFC Viewer")
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
