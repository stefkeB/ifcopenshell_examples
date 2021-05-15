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


class IFCPropertyWidget(QWidget):
    """
    A Widget containing all information from one object from one file.
    This is concerned with attributes, properties, quantities
    and associated materials, classifications.
    - V1 = Spin-off from IFCTreeWidget
    """
    def __init__(self):
        QWidget.__init__(self)
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        self.property_tree = QTreeWidget()
        vbox.addWidget(self.property_tree)
        self.property_tree.setColumnCount(3)
        self.property_tree.setHeaderLabels(["Name", "Value", "ID/Type"])

    def set_from_selected_items(self, items):
        """
        Fill the Property Tree from a selection of QTreeWidgetItems.
        Can be used to link from the Object Tree Widget

        :param items: List of QTreeWidgetItems (containing data in column 1)

        """
        self.reset()
        for item in items:
            # our very first item is the File, so show the Header only
            if item.text(1) == "File":
                ifc_file = item.data(0, Qt.UserRole)
                if ifc_file is None:
                    break
                self.add_file_header(ifc_file)
            else:
                ifc_object = item.data(0, Qt.UserRole)
                if ifc_object is None:
                    break
                self.add_object_data(ifc_object)

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

    def add_file_header(self, ifc_file):
        """
        Fill the property tree with the Header data from the file(s)
        which contains the current selected entities
        """
        header_item = QTreeWidgetItem(["Header"])
        self.property_tree.addTopLevelItem(header_item)

        header = ifc_file.wrapped_data.header
        FILE_DESCRIPTION_item = QTreeWidgetItem(["FILE_DESCRIPTION", "", ""])
        header_item.addChild(FILE_DESCRIPTION_item)
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
        header_item.addChild(FILE_NAME_item)
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
        header_item.addChild(FILE_SCHEMA_item)
        for schema_identifiers in header.file_schema.schema_identifiers:
            FILE_SCHEMA_item.addChild(
                QTreeWidgetItem(["schema_identifiers", str(schema_identifiers), ""]))

        self.property_tree.expandAll()

    def add_object_data(self, ifc_object):
        """
        Fill the property tree with all data from object
        """
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

    def reset(self):
        self.property_tree.clear()


if __name__ == '__main__':
    app = 0
    if QApplication.instance():
        app = QApplication.instance()
    else:
        app = QApplication(sys.argv)

    w = IFCPropertyWidget()
    w.resize(600, 800)
    filename = sys.argv[1]
    if os.path.isfile(filename):
        ifc_file = ifcopenshell.open(filename)
        w.add_file_header(ifc_file)
        entities = ifc_file.by_type('IfcProject')
        for entity in entities:
            w.add_object_data(entity)
        w.show()
    sys.exit(app.exec_())
