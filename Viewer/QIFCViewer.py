import time
import os.path
from IFCQt3DView import *
from IFCTreeWidget import *
from IFCPropertyWidget import *
from IFCListingWidget import *


class QIFCViewer(QMainWindow):
    """
    IFC Model Viewer
    - V1 = Loading the IFCTreeWidget and IFCQt3dView together (as-is)
    - V2 = Open + Save methods, Toolbar and Status Bar & Files in a Dictionary
    - V3 = Use separate Tree Views as two separate Dock Widgets and link them
    - V4 = Syncing updates & edits of values between Object and Property Tree
    - V5 = Supporting drag and drop of IFC files onto the app
    - V6 = Make the 3D view optional (switch)
    """
    def __init__(self, use_3d=True):
        QMainWindow.__init__(self)

        # A dictionary referring to our files, based on name
        self.ifc_files = {}
        self.setAcceptDrops(True)

        self.USE_3D = use_3d

        # menu, actions and toolbar
        self.setUnifiedTitleAndToolBarOnMac(True)
        toolbar = QToolBar("My main toolbar")
        toolbar.setFloatable(False)
        toolbar.setMovable(False)
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
        action_save.setStatusTip("Confirm saving of all IFC Models")
        action_save.triggered.connect(self.save_files)
        toolbar.addAction(action_save)
        file_menu.addAction(action_save)

        action_reload = QAction("Reload All", self)
        action_reload.setShortcut("CTRL+R")
        action_reload.setStatusTip("Reload all IFC Models")
        action_reload.triggered.connect(self.reload_files)
        toolbar.addAction(action_reload)
        file_menu.addAction(action_reload)

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
        if self.USE_3D:
            self.view_3d = IFCQt3dView()
        self.view_tree = IFCTreeWidget()
        self.view_properties = IFCPropertyWidget()
        self.view_takeoff = IFCListingWidget()

        # Selection Syncing
        if self.USE_3D:
            self.view_tree.select_object.connect(self.view_3d.select_object_by_id)
            self.view_tree.deselect_object.connect(self.view_3d.deselect_object_by_id)
            self.view_3d.add_to_selected_entities.connect(self.view_tree.receive_selection)
        self.view_tree.send_selection_set.connect(self.view_properties.set_from_selected_items)
        # Update Syncing
        self.view_properties.send_update_object.connect(self.view_tree.receive_object_update)

        # Docking Widgets
        if self.USE_3D is True:
            self.dock = QDockWidget('Model Tree', self)
            self.dock.setWidget(self.view_tree)
            self.dock.setFloating(False)
            self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

        self.dock2 = QDockWidget('Property Tree', self)
        self.dock2.setWidget(self.view_properties)
        self.dock2.setFloating(False)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock2)

        self.dock3 = QDockWidget('Take off', self)
        self.dock3.setWidget(self.view_takeoff)
        self.dock3.setFloating(False)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock3)

        # Main Widget = 3D View
        if self.USE_3D:
            self.setCentralWidget(self.view_3d)
        else:
            self.setCentralWidget(self.view_tree)

    # region File Methods

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
            dlg.setIcon(QMessageBox.Warning)
            dlg.setText(str("Do you want to replace the currently loaded model?\n"
                            "{}").format(filename))
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

        if self.USE_3D:
            self.view_3d.ifc_files[filename] = ifc_file
            self.view_3d.load_file(filename)

        self.view_takeoff.ifc_files[filename] = ifc_file
        print("Loaded all views in ", time.time() - start)
        return True

    def dragEnterEvent(self, event):
        data = event.mimeData()
        urls = data.urls()
        if urls and urls[0].scheme() == 'file':
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        data = event.mimeData()
        urls = data.urls()
        if urls and urls[0].scheme() == 'file':
            event.acceptProposedAction()

    def dropEvent(self, event):
        data = event.mimeData()
        urls = data.urls()
        if urls and urls[0].scheme() == 'file':
            for f in urls:
                filepath = str(f.path())
                # only .ifc files are acceptable
                if os.path.isfile(filepath) and os.path.splitext(filepath)[1] == '.ifc':
                    self.load_file(filepath)
                else:
                    dialog = QMessageBox()
                    dialog.setWindowTitle("Error: Invalid File")
                    dialog.setText(str("Only .ifc files are accepted.\nYou dragged {}").format(filepath))
                    dialog.setIcon(QMessageBox.Warning)
                    dialog.exec_()

    def reload_files(self):
        """
        Reload all currently open files
        """
        for ifc_filename, ifc_file in self.ifc_files.items():
            self.load_file(ifc_filename)

    def save_files(self):
        """
        Save all currently loaded files
        """
        for ifc_filename, ifc_file in self.ifc_files.items():

            dlg = QMessageBox(self.parent())
            dlg.setWindowTitle("Confirm file save")
            dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            dlg.setText(str("Do you want to save:\n{}?").format(ifc_filename))
            dlg.setDetailedText(str("When you click 'OK', you still have the chance of"
                                    "selecting a new name or location."))
            button = dlg.exec_()
            if button == QMessageBox.Ok:
                savepath = QFileDialog.getSaveFileName(self, caption="Save IFC File",
                                                       directory=ifc_filename,
                                                       filter="IFC files (*.ifc)")
                if savepath[0] != '':
                    ifc_file.write(savepath[0])

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
        if self.USE_3D:
            self.view_3d.close_files()
        self.view_takeoff.close_files()
        self.setWindowTitle("IFC Viewer")


# Our Main function
def main():
    app = 0
    if QApplication.instance():
        app = QApplication.instance()
    else:
        app = QApplication(sys.argv)
    app.setApplicationDisplayName("IFC Viewer")
    w = QIFCViewer(use_3d=False)
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
