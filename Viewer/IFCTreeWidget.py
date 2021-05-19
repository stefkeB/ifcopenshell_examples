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


def entity_summary(entity):
    """
    Return a multi-line string containing a summary of information about
    the IFC entity instance (STEP Id, Name, Class and GlobalId).
    Can be used in a Tooltip.

    :param entity: The IFC entity instance
    """
    myId = str(entity.id()) if hasattr(entity, "id") else "<no id>"
    myName = entity.Name if hasattr(entity, "Name") else "<no name>"
    myClass = entity.is_a() if hasattr(entity, "is_a") else "<no class>"
    myGlobalId = entity.GlobalId if hasattr(entity, "GlobalId") else "<no GlobalId>"
    return str("STEP id\t: #{}\nName\t: {}\nClass\t: {}\nGlobalId\t: {}").format(
        myId, myName, myClass, myGlobalId)


class IFCTreeWidget(QWidget):
    """
    Fifth version of the IFC Tree Widget/View
    - V1 = Single Tree (object + basic hierarchy)
    - V2 = Double Tree (object with type, properties/quantities + attributes)
    - V3 = Support for Selection Signals (to be linked to 3D view)
    - V4 = Object Tree with references + Property tree with Header data
    - V5 = Editing the name of objects + keeping multiple files in a dictionary
    - V6 = Spinning off the property tree into its own widget
    - V7 = Make the tree configurable (Decomposition, Root Class Chooser)
    """
    def __init__(self):
        QWidget.__init__(self)
        # A dictionary referring to our files, based on name
        self.ifc_files = {}

        # Main Settings
        self.root_class = 'IfcProject'
        self.follow_associations = False
        self.follow_defines = False
        self.follow_decomposition = True

        # Prepare Tree Widgets in a stretchable layout
        vbox = QVBoxLayout()
        self.setLayout(vbox)

        # Series of buttons and check boxes in a horizontal layout
        buttons = QWidget()
        vbox.addWidget(buttons)
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        buttons.setLayout(hbox)
        # Option : Decomposition
        self.check_c = QCheckBox("Decomposition")
        self.check_c.setToolTip("Display the Containment and Decomposition relations in the object tree")
        self.check_c.setChecked(self.follow_decomposition)
        self.check_c.toggled.connect(self.toggle_decomposition)
        hbox.addWidget(self.check_c)
        # Stretchable Spacer
        spacer = QSpacerItem(10, 10, QSizePolicy.Expanding)
        hbox.addSpacerItem(spacer)
        # Root Class Chooser
        self.root_class_chooser = QComboBox()
        self.root_class_chooser.setToolTip("Select the top level class to display in the tree")
        self.root_class_chooser.setMinimumWidth(80)
        self.root_class_chooser.addItem('IfcProject')
        self.root_class_chooser.addItem('IfcMaterial')
        self.root_class_chooser.addItem('IfcProduct')
        self.root_class_chooser.addItem('IfcRelationship')
        self.root_class_chooser.addItem('IfcPropertySet')
        self.root_class_chooser.setEditable(True)
        self.root_class_chooser.activated.connect(self.toggle_chooser)
        hbox.addWidget(self.root_class_chooser)

        # Object Tree
        self.object_tree = QTreeWidget()
        vbox.addWidget(self.object_tree)
        self.object_tree.setColumnCount(2)
        self.object_tree.setHeaderLabels(["Name", "Class"])
        self.object_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.object_tree.selectionModel().selectionChanged.connect(self.send_selection)
        self.object_tree.itemDoubleClicked.connect(self.check_object_name_edit)
        self.object_tree.itemChanged.connect(self.set_object_name_edit)

    select_object = pyqtSignal(object)
    deselect_object = pyqtSignal(object)
    send_selection_set = pyqtSignal(object)

    def send_selection(self, selected_items, deselected_items):
        items = self.object_tree.selectedItems()
        self.send_selection_set.emit(items)
        for item in items:
            entity = item.data(0, Qt.UserRole)
            if hasattr(entity, "GlobalId"):
                GlobalId = entity.GlobalId
                if GlobalId != '':
                    self.select_object.emit(GlobalId)
                    print("IFCTreeWidget.send_selection.select_object ", GlobalId)

        # send the deselected items as well
        for index in deselected_items.indexes():
            if index.column() == 0:  # only for first column, to avoid repeats
                item = self.object_tree.itemFromIndex(index)
                entity = item.data(0, Qt.UserRole)
                if hasattr(entity, "GlobalId"):
                    GlobalId = entity.GlobalId
                    if GlobalId != '':
                        self.deselect_object.emit(GlobalId)
                        print("treeview.send_selection.deselect_object ", GlobalId)

    def receive_selection(self, ids):
        print("IFCTreeWidget.receive_selection ", ids)
        self.object_tree.clearSelection()
        if not len(ids):
            return
        # TODO: this may take a while in large trees - should we have a cache?
        iterator = QTreeWidgetItemIterator(self.object_tree)
        while iterator.value():
            item = iterator.value()
            entity = item.data(0, Qt.UserRole)
            if entity is not None and hasattr(entity, "GlobalId"):
                if entity.GlobalId == ids:
                    item.setSelected(not item.isSelected())
                    index = self.object_tree.indexFromItem(item)
                    self.object_tree.scrollTo(index)
            iterator += 1

    def receive_object_update(self, ifc_object):
        iterator = QTreeWidgetItemIterator(self.object_tree)
        while iterator.value():
            item = iterator.value()
            entity = item.data(0, Qt.UserRole)
            if entity == ifc_object:
                # refresh my name
                item.setText(0, ifc_object.Name)
            iterator += 1

    def close_files(self):
        self.ifc_files.clear()
        self.object_tree.clear()

    def load_file(self, filename):
        """
        Load the file passed as filename and builds the whole object tree.
        If it already exists, that branch is removed and recreated.

        :param filename: Full path to the IFC file
        """
        ifc_file = None
        if filename in self.ifc_files:
            ifc_file = self.ifc_files[filename]
            for i in range(self.object_tree.topLevelItemCount()):
                toplevel_item = self.object_tree.topLevelItem(i)
                if filename == toplevel_item.text(0):
                    root = self.object_tree.invisibleRootItem()
                    root.removeChild(toplevel_item)
        else:  # Load as new file
            ifc_file = ifcopenshell.open(filename)
            self.ifc_files[filename] = ifc_file

        self.add_objects(filename)
        self.prepare_chooser()

    def add_objects(self, filename):
        """Fill the Object Tree with TreeItems representing Entity Instances

        :param filename: The filename for a loaded IFC model (in the files dictionary)
        :type filename: str
        """
        ifc_file = self.ifc_files[filename]
        root_item = QTreeWidgetItem([filename, 'File'])
        root_item.setData(0, Qt.UserRole, ifc_file)
        try:
            for item in ifc_file.by_type(self.root_class):
                self.add_object_in_tree(item, root_item)
        except:
            dlg = QMessageBox(self.parent())
            dlg.setWindowTitle("Invalid IFC Class!")
            dlg.setStandardButtons(QMessageBox.Ok)
            dlg.setText(str("{} is not a valid class name.\nSuggestions are IfcProject or IfcWall.").format(self.root_class))
            dlg.exec_()
        # Finish the GUI
        self.object_tree.addTopLevelItem(root_item)
        self.object_tree.expandToDepth(3)

    def add_object_in_tree(self, ifc_object, parent_item):
        """
        Fill the Object Tree recursively with Objects and their
        children, as defined by the relationships

        :param ifc_object: an IFC entity instance
        :type ifc_object: entity_instance
        :param parent_item: the parent QTreeWidgetItem
        :type parent_item: QTreeWidgetItem
        """
        my_name = ifc_object.Name if hasattr(ifc_object, "Name") else ""
        tree_item = QTreeWidgetItem([my_name, ifc_object.is_a()])
        parent_item.addChild(tree_item)
        tree_item.setData(0, Qt.UserRole, ifc_object)
        tree_item.setToolTip(0, entity_summary(ifc_object))

        if self.follow_decomposition:
            if hasattr(ifc_object, 'ContainsElements'):
                for rel in ifc_object.ContainsElements:
                    for element in rel.RelatedElements:
                        self.add_object_in_tree(element, tree_item)
            if hasattr(ifc_object, 'IsDecomposedBy'):
                for rel in ifc_object.IsDecomposedBy:
                    for related_object in rel.RelatedObjects:
                        self.add_object_in_tree(related_object, tree_item)
            if hasattr(ifc_object, 'IsGroupedBy'):
                for rel in ifc_object.IsGroupedBy:
                    if hasattr(rel, 'RelatedObjects'):
                        for related_object in rel.RelatedObjects:
                            self.add_object_in_tree(related_object, tree_item)

    def set_object_name_edit(self, item, column):
        """
        Send the change back to the item

        :param item: QTreeWidgetItem
        :param int column: Column index
        :return:
        """
        if item.text(1) == 'File':
            return
        ifc_object = item.data(0, Qt.UserRole)
        if ifc_object is not None:
            if hasattr(ifc_object, "Name"):
                ifc_object.Name = item.text(0)
                # warn other views/widgets
                items = self.object_tree.selectedItems()
                self.send_selection_set.emit(items)

    def check_object_name_edit(self, item, column):
        """
        Check whether this item can be edited

        :param item: QTreeWidgetItem
        :param column: Column index
        :return:
        """
        if item.text(1) == 'File':
            return

        tmp = item.flags()
        if column == 0:
            item.setFlags(tmp | Qt.ItemIsEditable)
        elif tmp & Qt.ItemIsEditable:
            item.setFlags(tmp ^ Qt.ItemIsEditable)

    def toggle_decomposition(self):
        self.follow_decomposition = not self.follow_decomposition
        self.regenerate_tree()

    def toggle_chooser(self, text):
        self.root_class = self.root_class_chooser.currentText()
        self.regenerate_tree()

    def prepare_chooser(self):
        buffer = self.root_class_chooser.currentText()
        self.root_class_chooser.clear()
        for _, file in self.ifc_files.items():
            for t in file.wrapped_data.types():
                if self.root_class_chooser.findText(t, Qt.MatchFixedString) == -1:  # require exact matching!
                    self.root_class_chooser.addItem(t)

        # Add all available classes in the Combobox
        self.root_class_chooser.setEditable(False)
        self.root_class_chooser.setCurrentText(buffer)
        self.root_class_chooser.model().sort(0, Qt.AscendingOrder)

    def regenerate_tree(self):
        self.object_tree.clear()
        for filename, file in self.ifc_files.items():
            self.add_objects(filename)


if __name__ == '__main__':
    app = 0
    if QApplication.instance():
        app = QApplication.instance()
    else:
        app = QApplication(sys.argv)

    w = IFCTreeWidget()
    w.resize(600, 800)
    filename = sys.argv[1]
    if os.path.isfile(filename):
        w.load_file(filename)
        w.show()
    sys.exit(app.exec_())
