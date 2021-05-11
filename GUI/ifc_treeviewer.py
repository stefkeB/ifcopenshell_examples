import sys
import os.path
try:
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import *
except Exception:
    from PySide2.QtGui import *
    from PySide2.QtCore import *
    from PySide2.QtWidgets import *
import ifcopenshell


class ViewTree(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        # Prepare Tree Widgets in a stretchable layout
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        # Object Tree
        self.object_tree = QTreeWidget()
        vbox.addWidget(self.object_tree)
        self.object_tree.setColumnCount(3)
        self.object_tree.setHeaderLabels(["Name", "Class", "ID"])

    def load_file(self, filename):
        # Import the IFC File
        self.ifc_file = ifcopenshell.open(filename)
        root_item = QTreeWidgetItem(
            [self.ifc_file.wrapped_data.header.file_name.name, 'File', ""])
        for item in self.ifc_file.by_type('IfcProject'):
            self.add_object_in_tree(item, root_item)
        # Finish the GUI
        self.object_tree.addTopLevelItem(root_item)
        self.object_tree.expandToDepth(3)

    def add_object_in_tree(self, ifc_object, parent_item):
        tree_item = QTreeWidgetItem([ifc_object.Name, ifc_object.is_a(), ifc_object.GlobalId])
        parent_item.addChild(tree_item)
        if hasattr(ifc_object, 'ContainsElements'):
            for rel in ifc_object.ContainsElements:
                for element in rel.RelatedElements:
                    self.add_object_in_tree(element, tree_item)
        if hasattr(ifc_object, 'IsDecomposedBy'):
            for rel in ifc_object.IsDecomposedBy:
                for related_object in rel.RelatedObjects:
                    self.add_object_in_tree(related_object, tree_item)


if __name__ == '__main__':
    app = 0
    if QApplication.instance():
        app = QApplication.instance()
    else:
        app = QApplication(sys.argv)

    w = ViewTree()
    w.resize(600, 800)
    filename = sys.argv[1]
    if os.path.isfile(filename):
        w.load_file(filename)
        w.show()
    sys.exit(app.exec_())
