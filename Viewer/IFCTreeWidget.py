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


class IFCTreeWidget(QWidget):
    """
    Fifth version of the IFC Tree Widget/View
    - V1 = Single Tree (object + basic hierarchy)
    - V2 = Double Tree (object with type, properties/quantities + attributes)
    - V3 = Support for Selection Signals (to be linked to 3D view)
    - V4 = Object Tree with references + Property tree with Header data
    - V5 = Editing the name of objects + keeping multiple files in a dictionary
    """
    def __init__(self):
        QWidget.__init__(self)
        # A dictionary referring to our files, based on name
        self.ifc_files = {}
        # Prepare Tree Widgets in a stretchable layout
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        # Object Tree
        self.object_tree = QTreeWidget()
        vbox.addWidget(self.object_tree)
        self.object_tree.setColumnCount(2)
        self.object_tree.setHeaderLabels(["Name", "Class"])
        self.object_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.object_tree.selectionModel().selectionChanged.connect(self.add_data)
        self.object_tree.selectionModel().selectionChanged.connect(self.send_selection)
        self.object_tree.itemDoubleClicked.connect(self.check_object_name_edit)
        self.object_tree.itemChanged.connect(self.set_object_name_edit)
        # Property Tree
        self.property_tree = QTreeWidget()
        vbox.addWidget(self.property_tree)
        self.property_tree.setColumnCount(3)
        self.property_tree.setHeaderLabels(["Name", "Value", "ID/Type"])

    select_object = pyqtSignal(object)
    deselect_object = pyqtSignal(object)

    def send_selection(self, selected_items, deselected_items):
        items = self.object_tree.selectedItems()
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

    def close_files(self):
        self.ifc_files.clear()
        self.property_tree.clear()
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

        root_item = QTreeWidgetItem([filename, 'File'])
        root_item.setData(0, Qt.UserRole, ifc_file)
        for item in ifc_file.by_type('IfcProject'):
            self.add_object_in_tree(item, root_item)
        # Finish the GUI
        self.object_tree.addTopLevelItem(root_item)
        self.property_tree.clear()
        self.object_tree.expandToDepth(3)

    def add_attributes_in_tree(self, ifc_object, parent_item):
        """
        Fill the property tree with the attributes of an object

        :param ifc_object: IfcPropertySet containing individual properties
        :param parent_item: QTreeWidgetItem used to put attributes underneath
        """
        for att_idx in range(0, len(ifc_object)):
            # https://github.com/jakob-beetz/IfcOpenShellScriptingTutorial/wiki/02:-Inspecting-IFC-instance-objects
            att_name = ifc_object.attribute_name(att_idx)
            att_value = str(ifc_object[att_idx])
            att_type = ifc_object.attribute_type(att_name)
            attribute_item = QTreeWidgetItem([att_name, att_value, att_type])
            parent_item.addChild(attribute_item)

    def add_properties_in_tree(self, property_set, parent_item):
        """
        Fill the property tree with the properties of a particular property set

        :param property_set: IfcPropertySet containing individual properties
        :param parent_item: QTreeWidgetItem used to put properties underneath
        """
        for prop in property_set.HasProperties:
            unit = str(prop.Unit) if hasattr(prop, 'Unit') else ''
            prop_value = '<not handled>'
            if prop.is_a('IfcPropertySingleValue'):
                prop_value = str(prop.NominalValue.wrappedValue)
                parent_item.addChild(QTreeWidgetItem([prop.Name, prop_value, unit]))
            elif prop.is_a('IfcComplexProperty'):
                property_item = QTreeWidgetItem([prop.Name, '', unit])
                parent_item.addChild(property_item)
                for nested_prop in prop.HasProperties:
                    nested_unit = str(nested_prop.Unit) if hasattr(nested_prop, 'Unit') else ''
                    property_nested_item = QTreeWidgetItem(
                        [nested_prop.Name, str(nested_prop.NominalValue.wrappedValue), nested_unit])
                    property_item.addChild(property_nested_item)
            else:
                property_item = QTreeWidgetItem([prop.Name, '<not handled>', unit])
                parent_item.addChild(property_item)

    def add_quantities_in_tree(self, quantity_set, parent_item):
        """
        Fill the property tree with the quantities

        :param quantity_set: IfcQuantitySet containing individual quantities
        :param parent_item: QTreeWidgetItem used to put quantities underneath
        """
        for quantity in quantity_set.Quantities:
            unit = str(quantity.Unit) if hasattr(quantity, 'Unit') else ''
            quantity_value = '<not handled>'
            if quantity.is_a('IfcQuantityLength'):
                quantity_value = str(quantity.LengthValue)
            elif quantity.is_a('IfcQuantityArea'):
                quantity_value = str(quantity.AreaValue)
            elif quantity.is_a('IfcQuantityVolume'):
                quantity_value = str(quantity.VolumeValue)
            elif quantity.is_a('IfcQuantityCount'):
                quantity_value = str(quantity.CountValue)
            parent_item.addChild(QTreeWidgetItem([quantity.Name, quantity_value, unit]))

    def add_header_in_tree(self, parent_item):
        """
        Fill the property tree with the Header data from the file(s)
        which contains the current selected entities

        :param parent_item: QTreeWidgetItem used to put the header data underneath
        """
        items = self.object_tree.selectedItems()
        for item in items:
            ifc_file = self.get_ifc_file_from_treeitem(item)
            header = ifc_file.wrapped_data.header
            FILE_DESCRIPTION_item = QTreeWidgetItem(["FILE_DESCRIPTION", "", ""])
            parent_item.addChild(FILE_DESCRIPTION_item)
            for desc in header.file_description.description:
                # desc = ...[...:...]"
                key = desc.split("[")[0]
                description = desc[len(key) + 1:-1]
                tree_item = QTreeWidgetItem([key, description])
                tree_item.setToolTip(1, description)
                FILE_DESCRIPTION_item.addChild(tree_item)
            FILE_DESCRIPTION_item.addChild(
                QTreeWidgetItem(["implementation_level", str(header.file_description.implementation_level)]))

            FILE_NAME_item = QTreeWidgetItem(["FILE_NAME"])
            parent_item.addChild(FILE_NAME_item)
            FILE_NAME_item.addChild(QTreeWidgetItem(["name", str(header.file_name.name), ""]))
            FILE_NAME_item.addChild(QTreeWidgetItem(["time_stamp", str(header.file_name.time_stamp), ""]))
            for author in header.file_name.author:
                FILE_NAME_item.addChild(QTreeWidgetItem(["author", str(author)]))
            for organization in header.file_name.organization:
                FILE_NAME_item.addChild(QTreeWidgetItem(["organization", str(organization)]))
            FILE_NAME_item.addChild(
                QTreeWidgetItem(["preprocessor_version", str(header.file_name.preprocessor_version)]))
            FILE_NAME_item.addChild(
                QTreeWidgetItem(["originating_system", str(header.file_name.originating_system)]))
            FILE_NAME_item.addChild(QTreeWidgetItem(["authorization", str(header.file_name.authorization)]))

            FILE_SCHEMA_item = QTreeWidgetItem(["FILE_SCHEMA", "", ""])
            parent_item.addChild(FILE_SCHEMA_item)
            for schema_identifiers in header.file_schema.schema_identifiers:
                FILE_SCHEMA_item.addChild(
                    QTreeWidgetItem(["schema_identifiers", str(schema_identifiers), ""]))

    def add_data(self):
        """
        Fill the property tree with data from the current selected entities
        """
        self.property_tree.clear()
        items = self.object_tree.selectedItems()
        for item in items:
            # our very first item is the File, so show the Header only
            # TODO: beware that this may be called twice, when two items have been selected
            if item.text(1) == "File":
                header_item = QTreeWidgetItem(["Header"])
                self.property_tree.addTopLevelItem(header_item)
                self.add_header_in_tree(header_item)
                self.property_tree.expandAll()
                break
            # get the object
            ifc_object = item.data(0, Qt.UserRole)
            if ifc_object is None:
                break

            # Attributes
            attributes_item = QTreeWidgetItem(["Attributes", "", ifc_object.GlobalId])
            self.property_tree.addTopLevelItem(attributes_item)
            self.add_attributes_in_tree(ifc_object, attributes_item)

            # Properties & Quantities
            if hasattr(ifc_object, 'IsDefinedBy'):
                for definition in ifc_object.IsDefinedBy:
                    if definition.is_a('IfcRelDefinesByType'):
                        type_object = definition.RelatingType
                        type_item = QTreeWidgetItem([type_object.Name,
                                                     type_object.is_a(),
                                                     type_object.GlobalId])
                        self.property_tree.addTopLevelItem(type_item)
                    if definition.is_a('IfcRelDefinesByProperties'):
                        property_set = definition.RelatingPropertyDefinition
                        # the individual properties/quantities
                        if property_set.is_a('IfcPropertySet'):
                            properties_item = QTreeWidgetItem([property_set.Name,
                                                               property_set.is_a(),
                                                               property_set.GlobalId])
                            self.property_tree.addTopLevelItem(properties_item)
                            self.add_properties_in_tree(property_set, properties_item)
                        elif property_set.is_a('IfcElementQuantity'):
                            quantities_item = QTreeWidgetItem([property_set.Name,
                                                               property_set.is_a(),
                                                               property_set.GlobalId])
                            self.property_tree.addTopLevelItem(quantities_item)
                            self.add_quantities_in_tree(property_set, quantities_item)

            self.property_tree.expandAll()

    def entity_summary(self, entity):
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

    def get_ifc_file_from_treeitem(self, tree_item):
        """
        Find the file to which the current item in the tree belongs.
        We find the top level item and check its file reference.

        :param tree_item: QTreeWidgetItem to start looking from
        :return: The IFC File as a reference.
        """
        # Beware that we may have multiple files
        # So start from the filename of the TopLevelItem
        while tree_item.parent():
            tree_item = tree_item.parent()
        return tree_item.data(0, Qt.UserRole)

    def add_object_in_tree(self, ifc_object, parent_item):
        """
        Fill the Object Tree recursively with Objects and their
        children, as defined by the relationships

        :param ifc_object: an IFC entity instance
        :param parent_item: the parent QTreeWidgetItem
        """
        tree_item = QTreeWidgetItem([ifc_object.Name, ifc_object.is_a()])  # , ifc_object.GlobalId])
        parent_item.addChild(tree_item)
        tree_item.setData(0, Qt.UserRole, ifc_object)
        tree_item.setToolTip(0, self.entity_summary(ifc_object))
        if hasattr(ifc_object, 'ContainsElements'):
            for rel in ifc_object.ContainsElements:
                for element in rel.RelatedElements:
                    self.add_object_in_tree(element, tree_item)
        if hasattr(ifc_object, 'IsDecomposedBy'):
            for rel in ifc_object.IsDecomposedBy:
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
        self.add_data()  # refresh the tree

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
