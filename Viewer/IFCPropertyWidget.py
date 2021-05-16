import sys
import os.path
import re

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
    - V2 = Configurable display options (Properties, Associations, Attributes + Full detail)
    - V3 = Refining, add Assignments
    - V4 = Editing Attributes (STRING, DOUBLE, INT and ENUMERATION)
    """

    send_update_object = pyqtSignal(object)

    def __init__(self):
        QWidget.__init__(self)
        # The list of the currently loaded objects
        self.loaded_objects_and_files = []

        # Main Settings
        self.follow_attributes = False
        self.follow_properties = True
        self.follow_associations = False
        self.follow_assignments = False
        self.follow_defines = False
        self.show_all = False

        # Widgets Setup
        vbox = QVBoxLayout()
        self.setLayout(vbox)

        # Series of buttons and check boxes in a horizontal layout
        buttons = QWidget()
        vbox.addWidget(buttons)
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        buttons.setLayout(hbox)
        # Option: Display Attributes
        self.check_a = QCheckBox("Attributes")
        self.check_a.setToolTip("Display all attributes")
        self.check_a.setChecked(self.follow_attributes)
        self.check_a.toggled.connect(self.toggle_attributes)
        hbox.addWidget(self.check_a)
        # Option: Display Properties
        self.check_p = QCheckBox("Properties")
        self.check_p.setToolTip("Display DefinedByProperties (incl. quantities)")
        self.check_p.setChecked(self.follow_properties)
        self.check_p.toggled.connect(self.toggle_properties)
        hbox.addWidget(self.check_p)
        # Option: Display Associations
        check_associations = QCheckBox("Associations")
        check_associations.setToolTip("Display associations, such as materials and classifications")
        check_associations.setChecked(self.follow_associations)
        check_associations.toggled.connect(self.toggle_associations)
        hbox.addWidget(check_associations)
        # Option: Display Assignments
        check_assignments = QCheckBox("Assignments")
        check_assignments.setToolTip("Display assignments, such as control, actor, process, group")
        check_assignments.setChecked(self.follow_assignments)
        check_assignments.toggled.connect(self.toggle_assignments)
        hbox.addWidget(check_assignments)
        # Option: Display Full Detail
        check_full_detail = QCheckBox("Full")
        check_full_detail.setToolTip("Show the full attributes hierarchy")
        check_full_detail.setChecked(self.show_all)
        check_full_detail.toggled.connect(self.toggle_show_all)
        hbox.addWidget(check_full_detail)
        # Stretchable Spacer
        spacer = QSpacerItem(10, 10, QSizePolicy.Expanding)
        hbox.addSpacerItem(spacer)

        # Property Tree
        self.property_tree = QTreeWidget()
        vbox.addWidget(self.property_tree)
        self.property_tree.setColumnCount(3)
        self.property_tree.setHeaderLabels(["Name", "Value", "ID/Type"])
        self.property_tree.itemDoubleClicked.connect(self.check_object_name_edit)
        self.property_tree.itemChanged.connect(self.set_object_name_edit)

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

    # Filling the tree with information

    def add_attributes_in_tree(self, ifc_object, parent_item, recursion=0):
        """
        Fill the property tree with the attributes of an object. When the "show all"
        option is activated, this will enable recursive attribute display. This can
        potentially go very deep and take a long time with deep structures or
        large geometry.

        :param ifc_object: IfcPropertySet containing individual properties
        :param parent_item: QTreeWidgetItem used to put attributes underneath
        :param recursion: To avoid infinite recursion, the recursion level is checked
        """
        for att_idx in range(0, len(ifc_object)):
            # https://github.com/jakob-beetz/IfcOpenShellScriptingTutorial/wiki/02:-Inspecting-IFC-instance-objects
            att_name = ifc_object.attribute_name(att_idx)
            att_value = str(ifc_object[att_idx])
            att_type = ifc_object.attribute_type(att_name)
            if not self.show_all and (att_type == ('ENTITY INSTANCE' or 'AGGREGATE OF ENTITY INSTANCE')):
                att_value = ''
            attribute_item = QTreeWidgetItem([att_name, att_value, att_type])
            attribute_item.setData(1, Qt.UserRole, ifc_object)  # remember the owner of this attribute

            if att_type == 'ENUMERATION':
                enums = get_enums_from_object(ifc_object, att_name)
                attribute_item.setStatusTip(1, ' - '.join(enums))
                attribute_item.setToolTip(1, ' - '.join(enums))

            parent_item.addChild(attribute_item)

            # Skip?
            if not self.show_all:
                if att_name == 'OwnerHistory' or 'Representation' or 'ObjectPlacement':
                    continue

            # Recursive call to display the attributes of ENTITY INSTANCES and AGGREGATES
            attribute = ifc_object[att_idx]
            if attribute is not None and recursion < 20:
                if att_type == 'ENTITY INSTANCE':
                    self.add_attributes_in_tree(attribute, attribute_item, recursion + 1)
                if att_type == 'AGGREGATE OF ENTITY INSTANCE':
                    counter = 0
                    attribute_item.setText(0, attribute_item.text(0) + ' [' + str(len(attribute)) + ']')
                    for nested_entity in attribute:
                        my_name = "[" + str(counter) + "]"
                        my_value = self.get_friendly_ifc_name(nested_entity)
                        my_type = "#" + str(nested_entity.id())
                        nested_item = QTreeWidgetItem([my_name, my_value, my_type])
                        attribute_item.addChild(nested_item)
                        try:
                            self.add_attributes_in_tree(nested_entity, nested_item,
                                                        recursion + 1)  # forced high depth
                        except:
                            print('Except nested Entity Instance')
                            pass
                        counter += 1

    def add_properties_in_tree(self, property_set, parent_item):
        """
        Fill the property tree with the properties of a particular property set

        :param property_set: IfcPropertySet containing individual properties
        :param parent_item: QTreeWidgetItem used to put properties underneath
        """
        for prop in property_set.HasProperties:
            if self.show_all:
                self.add_attributes_in_tree(prop, parent_item)
            else:
                unit = str(prop.Unit) if hasattr(prop, 'Unit') else ''
                prop_value = '<not handled>'
                if prop.is_a('IfcPropertySingleValue'):
                    prop_value = str(prop.NominalValue.wrappedValue)
                    prop_item = QTreeWidgetItem([prop.Name, prop_value, unit])
                    prop_item.setData(1, Qt.UserRole, prop)
                    parent_item.addChild(prop_item)
                elif prop.is_a('IfcComplexProperty'):
                    property_item = QTreeWidgetItem([prop.Name, '', unit])
                    parent_item.addChild(property_item)
                    for nested_prop in prop.HasProperties:
                        nested_unit = str(nested_prop.Unit) if hasattr(nested_prop, 'Unit') else ''
                        property_nested_item = QTreeWidgetItem(
                            [nested_prop.Name, str(nested_prop.NominalValue.wrappedValue), nested_unit])
                        property_nested_item.setData(1, Qt.UserRole, nested_prop)
                        property_item.addChild(property_nested_item)
                        # self.add_attributes_in_tree(nested_prop, property_nesteditem)
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
            if self.show_all:
                self.add_attributes_in_tree(quantity, parent_item)
            else:
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
        self.loaded_objects_and_files.append(ifc_file)
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

        :param ifc_object: The IFC Entity instance to show
        """
        self.loaded_objects_and_files.append(ifc_object)

        # Attributes
        if self.follow_attributes:
            my_id = ifc_object.GlobalId if hasattr(ifc_object, "GlobalId") else str("#{}").format(ifc_object.id())
            attributes_item = QTreeWidgetItem(["Attributes", self.get_friendly_ifc_name(ifc_object), my_id])
            self.property_tree.addTopLevelItem(attributes_item)
            self.add_attributes_in_tree(ifc_object, attributes_item)

            # inv_attributes_item = QTreeWidgetItem(["Inverse Attributes", self.get_friendly_ifc_name(ifc_object), my_id])
            # self.property_tree.addTopLevelItem(inv_attributes_item)
            # self.add_inverseattributes_in_tree(ifc_object, inv_attributes_item)

        # Has Assignments
        if self.follow_assignments and hasattr(ifc_object, 'HasAssignments'):
            buffer = "HasAssignments [" + str(len(ifc_object.HasAssignments)) + "]"
            assignments_item = QTreeWidgetItem([buffer, self.get_friendly_ifc_name(ifc_object)])
            self.property_tree.addTopLevelItem(assignments_item)
            counter = 0
            for assignment in ifc_object.HasAssignments:
                ass_name = assignment.Name if assignment.Name is not None else '[' + str(counter) + ']'
                ass_item = QTreeWidgetItem([ass_name, self.get_friendly_ifc_name(assignment), assignment.GlobalId])
                assignments_item.addChild(ass_item)
                self.add_attributes_in_tree(assignment, ass_item)
                counter += 1

        # Defined By (for type, properties & quantities)
        # using attributes (show all)
        if self.show_all and (self.follow_defines or self.follow_properties) and hasattr(ifc_object,
                                                                                         'IsDefinedBy'):
            buffer = "IsDefinedBy [" + str(len(ifc_object.IsDefinedBy)) + "]"
            item = QTreeWidgetItem([buffer, self.get_friendly_ifc_name(ifc_object), ''])
            self.property_tree.addTopLevelItem(item)
            counter = 0
            for definition in ifc_object.IsDefinedBy:
                if definition.is_a('IfcRelDefinesByProperties') and not self.follow_properties:
                    continue
                if definition.is_a('IfcRelDefinesByType') and not self.follow_defines:
                    continue
                def_name = definition.Name if definition.Name is not None else '[' + str(counter) + ']'
                def_item = QTreeWidgetItem(
                    [def_name, self.get_friendly_ifc_name(definition), definition.GlobalId])
                item.addChild(def_item)
                self.add_attributes_in_tree(definition, def_item)
                counter += 1
        # more streamlined display
        if not self.show_all and (self.follow_defines or self.follow_properties) and hasattr(ifc_object, 'IsDefinedBy'):
            for definition in ifc_object.IsDefinedBy:
                if self.follow_defines and definition.is_a('IfcRelDefinesByType'):
                    type_object = definition.RelatingType
                    s = self.get_friendly_ifc_name(type_object)
                    type_item = QTreeWidgetItem([type_object.Name, s, type_object.GlobalId])
                    self.property_tree.addTopLevelItem(type_item)
                if self.follow_properties and definition.is_a('IfcRelDefinesByProperties'):
                    property_set = definition.RelatingPropertyDefinition
                    s = self.get_friendly_ifc_name(property_set)
                    # the individual properties/quantities
                    if property_set.is_a('IfcPropertySet'):
                        properties_item = QTreeWidgetItem([property_set.Name, s, property_set.GlobalId])
                        self.property_tree.addTopLevelItem(properties_item)
                        self.add_properties_in_tree(property_set, properties_item)
                    elif property_set.is_a('IfcElementQuantity'):
                        quantities_item = QTreeWidgetItem([property_set.Name, s, property_set.GlobalId])
                        self.property_tree.addTopLevelItem(quantities_item)
                        self.add_quantities_in_tree(property_set, quantities_item)

        # Associations (Materials, Classification, ...)
        if self.follow_associations and hasattr(ifc_object, 'HasAssociations'):
            associations_item = QTreeWidgetItem(
                ["Associations [" + str(len(ifc_object.HasAssociations)) + "]"])
            self.property_tree.addTopLevelItem(associations_item)
            for association in ifc_object.HasAssociations:
                s = self.get_friendly_ifc_name(association)
                item = QTreeWidgetItem([association.Name, s, association.GlobalId])
                associations_item.addChild(item)
                # and one step deeper
                if association.is_a('IfcRelAssociatesMaterial'):
                    relating_material = association.RelatingMaterial
                    # other (non Root) entities
                    if not self.show_all:  # streamlined display
                        if relating_material.is_a('IfcMaterialList'):
                            for mat in relating_material.Materials:
                                s = self.get_friendly_ifc_name(mat)
                                mat_item = QTreeWidgetItem([mat.Name, s, "#" + str(mat.id())])
                                item.addChild(mat_item)
                                self.add_attributes_in_tree(mat, mat_item)
                        elif relating_material.is_a('IfcMaterialLayerSet'):
                            # self.add_attributes_in_tree(relating_material, item)
                            for layer in relating_material.MaterialLayers:
                                s = self.get_friendly_ifc_name(layer)
                                layer_item = QTreeWidgetItem(["<no name>", s, "#" + str(layer.id())])
                                item.addChild(layer_item)
                                self.add_attributes_in_tree(layer, layer_item)
                        else:
                            self.add_attributes_in_tree(relating_material, item)
                    else:  # generic attributes following
                        self.add_attributes_in_tree(relating_material, item)
                elif association.is_a('IfcRelAssociatesClassification'):
                    relating_classification = association.RelatingClassification
                    self.add_attributes_in_tree(relating_classification, item)

        self.property_tree.expandAll()

    def camel_case_split(self, str):
        return re.findall(r'[A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$))', str)

    def get_friendly_ifc_name(self, ifc_object):
        # Trick to split the IfcClass into separate words
        s = ' '.join(self.camel_case_split(str(ifc_object.is_a())))
        s = s[4:]
        return s

    # Configuring the tree

    def reset(self):
        self.property_tree.clear()
        self.loaded_objects_and_files.clear()

    def regenerate(self):
        self.property_tree.clear()
        buffer_list = self.loaded_objects_and_files[:]  # copy items in new list
        self.loaded_objects_and_files.clear()
        for item in buffer_list:
            # if file
            if hasattr(item, "id"):
                self.add_object_data(item)
            else:
                self.add_file_header(item)

    def toggle_attributes(self):
        self.follow_attributes = not self.follow_attributes
        self.regenerate()

    def toggle_properties(self):
        self.follow_properties = not self.follow_properties
        self.regenerate()

    def toggle_associations(self):
        self.follow_associations = not self.follow_associations
        self.regenerate()

    def toggle_assignments(self):
        self.follow_assignments = not self.follow_assignments
        self.regenerate()

    def toggle_defines(self):
        self.follow_defines = not self.follow_defines
        self.regenerate()

    def toggle_show_all(self):
        self.show_all = not self.show_all
        self.regenerate()

    # Tree Editing

    def set_object_name_edit(self, item, column):
        """
        Send the change back to the item

        :param item: QTreeWidgetItem
        :param int column: Column index
        :return:
        """
        if column == 1 and item.text(2) in ['STRING', 'DOUBLE', 'ENUMERATION', 'INT']:
            att_name = item.text(0)
            att_new_value = item.text(1)
            # if item.text(2) == 'ENUMERATION':
            #    att_old_value = item.data(1, Qt.UserRole + 1)
            #    combo = self.combo
            #    att_new_value = self.combo.currentText()
            #    # self.combo.setParent(None)
            #    # self.combo = None
            ifc_object = item.data(1, Qt.UserRole)
            if ifc_object is not None:
                att_index = ifc_object.wrapped_data.get_argument_index(att_name)
                att_value = ifc_object.wrapped_data.get_argument(att_index)
                # att_type = ifc_object.wrapped_data.get_argument_type(att_index)
                att_type = ifc_object.attribute_type(att_index)

                print("Attribute", att_index, "current:", att_value, "new:", att_new_value)
                if att_value != att_new_value and hasattr(ifc_object, att_name):
                    try:
                        val = att_new_value  # default as STRING
                        if att_type == 'INT':
                            val = int(att_new_value)
                            setattr(ifc_object, item.text(0), val)
                        if att_type == 'DOUBLE':
                            val = float(att_new_value)
                            setattr(ifc_object, item.text(0), val)
                        if att_type == 'ENUMERATION':
                            schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name('IFC2x3')
                            e_class = schema.declaration_by_name(ifc_object.is_a())
                            attribute = e_class.attribute_by_index(att_index)
                            enum = attribute.type_of_attribute().declared_type().enumeration_items()
                            if val in enum:
                                print('Valid enum value')
                                setattr(ifc_object, item.text(0), val)
                            else:
                                print('Invalid enum value')
                                item.setText(1, str(att_value))
                        if att_type == 'STRING':
                            setattr(ifc_object, item.text(0), att_value)
                    except:
                        print("Could not set Attribute :", item.text(0), " with value ", att_new_value)
                        print("So we reset it to ", att_value)
                        item.setText(1, str(att_value))
                        pass
                    # Warn other views, but only needed if Name is changed
                    if att_name == "Name":
                        self.send_update_object.emit(ifc_object)

    def check_object_name_edit(self, item, column):
        """
        Check whether this item can be edited

        :param item: QTreeWidgetItem
        :param column: Column index
        :return:
        """
        if item.text(0) == 'GlobalId': return  # We don't want to allow changing this
        ifc_object = item.data(1, Qt.UserRole)
        if ifc_object is not None:
            if column == 1 and item.text(2) in ['STRING', 'DOUBLE', 'ENUMERATION', 'INT']:
                tmp = item.flags()
                if column == 1:
                    item.setFlags(tmp | Qt.ItemIsEditable)
                    # Get my index
                    #if item.text(2) == 'ENUMERATION':
                    #    tree = item.treeWidget()
                    #    index = tree.indexFromItem(item, 1)
                    #    enums = get_enums_from_object(ifc_object, item.text(0))

                        # Insert a ComboBox
                        # self.combo = QComboBox()
                        # self.combo.addItems(enums)
                        # self.combo.setCurrentText(item.text(1))
                        # item.setData(1, Qt.UserRole + 1, item.text(1))  # current value
                        # # item.setData(1, Qt.UserRole + 2, self.combo)  # the combo box
                        # # item.setText(1, '')
                        # tree.setIndexWidget(index, self.combo)
                        # self.combo.activated.connect(tree.itemChanged)


                elif tmp & Qt.ItemIsEditable:
                    item.setFlags(tmp ^ Qt.ItemIsEditable)


class PopupView(QWidget):
    def __init__(self, parent=None):
        super(PopupView, self).__init__(parent)
        self.setWindowFlags(Qt.Popup)


def get_enums_from_object(ifc_object, att_name):
    """
    Only works for IFC2X3 at the moment
    """
    if hasattr(ifc_object, att_name):
        att_index = ifc_object.wrapped_data.get_argument_index(att_name)
        att_value = ifc_object.wrapped_data.get_argument(att_index)
        # att_type = ifc_object.wrapped_data.get_argument_type(att_index)
        att_type = ifc_object.attribute_type(att_index)
        if att_type == 'ENUMERATION':
            schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name('IFC2x3')
            e_class = schema.declaration_by_name(ifc_object.is_a())
            attribute = e_class.attribute_by_index(att_index)
            return attribute.type_of_attribute().declared_type().enumeration_items()

class ItemDelegate(QItemDelegate):
    def __init__(self, parent):
        super(ItemDelegate, self).__init__(parent)

    def createEditor(self, parent, option, index):
        return PopupView(parent)

    def updateEditorGeometry(self, editor, option, index):
        editor.move(QCursor.pos())


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
