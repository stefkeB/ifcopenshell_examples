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
        self.check_a = QCheckBox("Attr")
        self.check_a.setToolTip("Display all attributes")
        self.check_a.setChecked(self.follow_attributes)
        self.check_a.toggled.connect(self.toggle_attributes)
        hbox.addWidget(self.check_a)
        # Option: Display Properties
        self.check_p = QCheckBox("Props")
        self.check_p.setToolTip("Display DefinedByProperties (incl. quantities)")
        self.check_p.setChecked(self.follow_properties)
        self.check_p.toggled.connect(self.toggle_properties)
        hbox.addWidget(self.check_p)
        # Option: Display Associations
        check_associations = QCheckBox("Assoc")
        check_associations.setToolTip("Display associations, such as materials and classifications")
        check_associations.setChecked(self.follow_associations)
        check_associations.toggled.connect(self.toggle_associations)
        hbox.addWidget(check_associations)
        # Option: Display Assignments
        check_assignments = QCheckBox("Assign")
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
        self.property_tree = QTreeView()  # instead of QTreeWidget
        self.model = None
        self.reset()

        vbox.addWidget(self.property_tree)
        # self.property_tree.setColumnCount(3)
        # self.property_tree.setHeaderLabels(["Name", "Value", "ID/Type"])
        # self.property_tree.itemDoubleClicked.connect(self.check_value_edit)
        # self.property_tree.itemChanged.connect(self.set_value_edit)

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
                model = item.data(0, Qt.UserRole)
                if model is None:
                    break
                self.add_file_header(model)
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
        :param parent_item: QStandardItem used to put attributes underneath
        :param recursion: To avoid infinite recursion, the recursion level is checked
        """
        for att_idx in range(0, len(ifc_object)):
            # https://github.com/jakob-beetz/IfcOpenShellScriptingTutorial/wiki/02:-Inspecting-IFC-instance-objects
            att_name = ifc_object.attribute_name(att_idx)
            att_value = str(ifc_object[att_idx])
            att_type = ifc_object.attribute_type(att_name)
            if not self.show_all and (att_type == ('ENTITY INSTANCE' or 'AGGREGATE OF ENTITY INSTANCE')):
                att_value = ''
            attribute_item0 = QStandardItem(att_name)
            attribute_item1 = QStandardItem(att_value)
            attribute_item1.setToolTip(att_value)
            attribute_item2 = QStandardItem(att_type)
            attribute_item1.setData(ifc_object, Qt.UserRole)  # remember the owner of this attribute

            if att_type == 'ENUMERATION':
                enums = get_enums_from_object(ifc_object, att_name)
                attribute_item1.setStatusTip(' - '.join(enums))
                attribute_item1.setToolTip(' - '.join(enums))

            parent_item.appendRow([attribute_item0, attribute_item1, attribute_item2])

            # Skip?
            if not self.show_all:
                if att_name == 'OwnerHistory' or 'Representation' or 'ObjectPlacement':
                    continue

            # Recursive call to display the attributes of ENTITY INSTANCES and AGGREGATES
            attribute = ifc_object[att_idx]
            if attribute is not None and recursion < 20:
                if att_type == 'ENTITY INSTANCE':
                    self.add_attributes_in_tree(attribute, attribute_item0, recursion + 1)
                if att_type == 'AGGREGATE OF DOUBLE':
                    attribute_item0.setText(attribute_item0.text() + ' [' + str(len(attribute)) + ']')
                    for counter, value in enumerate(attribute):
                        nested_item0 = QStandardItem("[" + str(counter) + "]")
                        nested_item1 = QStandardItem(str(value))
                        nested_item2 = QStandardItem("DOUBLE")
                        # nested_item1.setData(nested_entity, Qt.UserRole)  # remember the owner of this attribute
                        attribute_item0.appendRow([nested_item0, nested_item1, nested_item2])
                if att_type == 'AGGREGATE OF ENTITY INSTANCE':
                    attribute_item0.setText(attribute_item0.text() + ' [' + str(len(attribute)) + ']')
                    for counter, nested_entity in enumerate(attribute):
                        nested_item0 = QStandardItem("[" + str(counter) + "]")
                        nested_item1 = QStandardItem(self.get_friendly_ifc_name(nested_entity))
                        nested_item2 = QStandardItem("#" + str(nested_entity.id()))
                        nested_item1.setData(nested_entity, Qt.UserRole)  # remember the owner of this attribute
                        attribute_item0.appendRow([nested_item0, nested_item1, nested_item2])
                        try:
                            self.add_attributes_in_tree(nested_entity, nested_item0,
                                                        recursion + 1)  # forced high depth
                        except:
                            print('Except nested Entity Instance')
                            pass

    def add_properties_in_tree(self, property_set, parent_item):
        """
        Fill the property tree with the properties of a particular property set

        :param property_set: IfcPropertySet containing individual properties
        :param parent_item: QStandardItem used to put properties underneath
        """
        for prop in property_set.HasProperties:
            if self.show_all:
                self.add_attributes_in_tree(prop, parent_item)
            else:
                unit = str(prop.Unit) if hasattr(prop, 'Unit') else ''
                prop_value = '<not handled>'
                if prop.is_a('IfcPropertySingleValue'):
                    prop_value = str(prop.NominalValue.wrappedValue)
                    prop_item0 = QStandardItem(prop.Name)
                    prop_item1 = QStandardItem(prop_value)
                    prop_item2 = QStandardItem(unit)
                    prop_item1.setData(prop, Qt.UserRole)
                    parent_item.appendRow([prop_item0, prop_item1, prop_item2])
                elif prop.is_a('IfcComplexProperty'):
                    property_item0 = QStandardItem(prop.Name)
                    # property_item1 = QStandardItem('')
                    property_item2 = QStandardItem(unit)
                    parent_item.appendRow([property_item0, None, property_item2])
                    for nested_prop in prop.HasProperties:
                        nested_unit = str(nested_prop.Unit) if hasattr(nested_prop, 'Unit') else ''
                        prop_nested_item0 = QStandardItem(nested_prop.Name)
                        prop_nested_item1 = QStandardItem(str(nested_prop.NominalValue.wrappedValue))
                        prop_nested_item2 = QStandardItem(nested_unit)
                        prop_nested_item1.setData(nested_prop, Qt.UserRole)
                        property_item0.appendRow([prop_nested_item0, prop_nested_item1, prop_nested_item2])
                else:
                    property_item0 = QStandardItem(prop.Name)
                    property_item1 = QStandardItem('<not handled>')
                    property_item2 = QStandardItem(unit)
                    property_item1.setData(prop, Qt.UserRole)
                    parent_item.appendRow([property_item0, property_item1, property_item2])

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

                prop_item0 = QStandardItem(quantity.Name)
                prop_item1 = QStandardItem(quantity_value)
                prop_item2 = QStandardItem(unit)
                parent_item.appendRow([prop_item0, prop_item1, prop_item2])

    def add_file_header(self, ifc_file):
        """
        Fill the property tree with the Header data from the file(s)
        which contains the current selected entities
        """
        self.loaded_objects_and_files.append(ifc_file)
        header_item = QStandardItem("Header")
        header_item.setData(ifc_file, Qt.UserRole)
        self.model.invisibleRootItem().appendRow([header_item])

        header = ifc_file.wrapped_data.header
        FILE_DESCRIPTION_item = QStandardItem("FILE_DESCRIPTION")
        header_item.appendRow([FILE_DESCRIPTION_item])
        for desc in header.file_description.description:
            # desc = ...[...:...]"
            key = desc.split("[")[0]
            description = desc[len(key) + 1:-1]
            tree_item1 = QStandardItem(key)
            tree_item2 = QStandardItem(description)
            tree_item1.setToolTip(description)
            FILE_DESCRIPTION_item.appendRow([tree_item1, tree_item2])
        FILE_DESCRIPTION_item.appendRow(
            [QStandardItem("implementation_level"),
             QStandardItem(str(header.file_description.implementation_level))])

        FILE_NAME_item = QStandardItem("FILE_NAME")
        header_item.appendRow([FILE_NAME_item])
        FILE_NAME_item.appendRow([QStandardItem("name"), QStandardItem(str(header.file_name.name))])
        FILE_NAME_item.appendRow([QStandardItem("time_stamp"), QStandardItem(str(header.file_name.time_stamp))])
        for author in header.file_name.author:
            FILE_NAME_item.appendRow([QStandardItem("author"), QStandardItem(str(author))])
        for organization in header.file_name.organization:
            FILE_NAME_item.appendRow([QStandardItem("organization"), QStandardItem(str(organization))])
        FILE_NAME_item.appendRow(
            [QStandardItem("preprocessor_version"), QStandardItem(str(header.file_name.preprocessor_version))])
        FILE_NAME_item.appendRow(
            [QStandardItem("originating_system"), QStandardItem(str(header.file_name.originating_system))])
        FILE_NAME_item.appendRow([QStandardItem("authorization"), QStandardItem(str(header.file_name.authorization))])

        FILE_SCHEMA_item = QStandardItem("FILE_SCHEMA")
        header_item.appendRow([FILE_SCHEMA_item])
        for schema_identifiers in header.file_schema.schema_identifiers:
            FILE_SCHEMA_item.appendRow(
                [QStandardItem("schema_identifiers"), QStandardItem(str(schema_identifiers))])

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
            attributes_item1 = QStandardItem("Attributes")
            attributes_item2 = QStandardItem(self.get_friendly_ifc_name(ifc_object))
            attributes_item3 = QStandardItem(my_id)
            self.model.invisibleRootItem().appendRow([attributes_item1, attributes_item2, attributes_item3])
            self.add_attributes_in_tree(ifc_object, attributes_item1)

            # inv_attributes_item = QTreeWidgetItem(["Inverse Attributes", self.get_friendly_ifc_name(ifc_object), my_id])
            # self.property_tree.addTopLevelItem(inv_attributes_item)
            # self.add_inverseattributes_in_tree(ifc_object, inv_attributes_item)

        # Has Assignments
        if self.follow_assignments and hasattr(ifc_object, 'HasAssignments'):
            buffer = "HasAssignments [" + str(len(ifc_object.HasAssignments)) + "]"
            assignments_item0 = QStandardItem(buffer)
            assignments_item1 = QStandardItem(self.get_friendly_ifc_name(ifc_object))
            self.model.invisibleRootItem().appendRow([assignments_item0, assignments_item1])
            counter = 0
            for assignment in ifc_object.HasAssignments:
                ass_name = assignment.Name if assignment.Name is not None else '[' + str(counter) + ']'
                ass_item0 = QStandardItem(ass_name)
                ass_item0.setData(assignment, Qt.UserRole)
                ass_item1 = QStandardItem(self.get_friendly_ifc_name(assignment))
                ass_item2 = QStandardItem(assignment.GlobalId)
                assignments_item0.appendRow([ass_item0, ass_item1, ass_item2])
                self.add_attributes_in_tree(assignment, ass_item0)
                counter += 1

        # Defined By (for type, properties & quantities)
        # using attributes (show all)
        if self.show_all and (self.follow_defines or self.follow_properties) and hasattr(ifc_object,
                                                                                         'IsDefinedBy'):
            item0 = QStandardItem("IsDefinedBy [" + str(len(ifc_object.IsDefinedBy)) + "]")
            item1 = QStandardItem(self.get_friendly_ifc_name(ifc_object))
            self.model.invisibleRootItem().appendRow([item0, item1])
            counter = 0
            for definition in ifc_object.IsDefinedBy:
                if definition.is_a('IfcRelDefinesByProperties') and not self.follow_properties:
                    continue
                if definition.is_a('IfcRelDefinesByType') and not self.follow_defines:
                    continue
                def_name = definition.Name if definition.Name is not None else '[' + str(counter) + ']'
                def_item0 = QStandardItem(def_name)
                def_item0.setData(definition, Qt.UserRole)
                def_item1 = QStandardItem(self.get_friendly_ifc_name(definition))
                def_item2 = QStandardItem(definition.GlobalId)
                item0.appendRow([def_item0, def_item1, def_item2])
                self.add_attributes_in_tree(definition, def_item0)
                counter += 1
        # more streamlined display
        if not self.show_all and (self.follow_defines or self.follow_properties) and hasattr(ifc_object, 'IsDefinedBy'):
            for definition in ifc_object.IsDefinedBy:
                if self.follow_defines and definition.is_a('IfcRelDefinesByType'):
                    type_object = definition.RelatingType
                    s = self.get_friendly_ifc_name(type_object)
                    type_item0 = QStandardItem(type_object.Name)
                    type_item0.setData(type_item0, Qt.UserRole)
                    type_item1 = QStandardItem(s)
                    type_item2 = QStandardItem(type_object.GlobalId)
                    type_item0.setData(type_object, Qt.UserRole)
                    self.model.invisibleRootItem().appendRow([type_item0, type_item1, type_item2])
                if self.follow_properties and definition.is_a('IfcRelDefinesByProperties'):
                    property_set = definition.RelatingPropertyDefinition
                    prop_item0 = QStandardItem(property_set.Name)
                    prop_item0.setData(property_set, Qt.UserRole)
                    prop_item1 = QStandardItem(self.get_friendly_ifc_name(property_set))
                    prop_item2 = QStandardItem(property_set.GlobalId)
                    self.model.invisibleRootItem().appendRow([prop_item0, prop_item1, prop_item2])
                    # the individual properties/quantities
                    if property_set.is_a('IfcPropertySet'):
                        self.add_properties_in_tree(property_set, prop_item0)
                    elif property_set.is_a('IfcElementQuantity'):
                        self.add_quantities_in_tree(property_set, prop_item0)

        # Associations (Materials, Classification, ...)
        if self.follow_associations and hasattr(ifc_object, 'HasAssociations'):
            item0 = QStandardItem("Associations [" + str(len(ifc_object.HasAssociations)) + "]")
            item1 = QStandardItem(self.get_friendly_ifc_name(ifc_object))
            self.model.invisibleRootItem().appendRow([item0, item1])
            for association in ifc_object.HasAssociations:
                def_item0 = QStandardItem(association.Name)
                def_item0.setData(association, Qt.UserRole)
                def_item1 = QStandardItem(self.get_friendly_ifc_name(association))
                def_item2 = QStandardItem(association.GlobalId)
                item0.appendRow([def_item0, def_item1, def_item2])
                # and one step deeper
                if association.is_a('IfcRelAssociatesMaterial'):
                    relating_material = association.RelatingMaterial
                    # other (non Root) entities
                    if not self.show_all:  # streamlined display
                        if relating_material.is_a('IfcMaterialList'):
                            for mat in relating_material.Materials:
                                mat_item0 = QStandardItem(mat.Name)
                                mat_item0.setData(mat, Qt.UserRole)
                                mat_item1 = QStandardItem(self.get_friendly_ifc_name(mat))
                                mat_item2 = QStandardItem(str('#' + mat.id()))
                                def_item0.appendRow([mat_item0, mat_item1, mat_item2])
                                self.add_attributes_in_tree(mat, mat_item0)
                        elif relating_material.is_a('IfcMaterialLayerSet'):
                            # self.add_attributes_in_tree(relating_material, item)
                            for layer in relating_material.MaterialLayers:
                                mat_item0 = QStandardItem(layer.Name)
                                mat_item0.setData(layer, Qt.UserRole)
                                mat_item1 = QStandardItem(self.get_friendly_ifc_name(layer))
                                mat_item2 = QStandardItem(str('#' + layer.id()))
                                def_item0.appendRow([mat_item0, mat_item1, mat_item2])
                                self.add_attributes_in_tree(layer, mat_item0)
                        else:
                            self.add_attributes_in_tree(relating_material, def_item0)
                    else:  # generic attributes following
                        self.add_attributes_in_tree(relating_material, def_item0)
                elif association.is_a('IfcRelAssociatesClassification'):
                    relating_classification = association.RelatingClassification
                    self.add_attributes_in_tree(relating_classification, def_item0)

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
        w0 = 200
        w1 = 200
        w2 = 50
        if self.model is not None:
            w0 = self.property_tree.columnWidth(0)
            w1 = self.property_tree.columnWidth(1)
            w2 = self.property_tree.columnWidth(2)
            self.model.clear()
        self.model = QStandardItemModel(0, 3, self)
        self.property_tree.setModel(self.model)
        self.property_tree.setColumnWidth(0, w0)
        self.property_tree.setColumnWidth(1, w1)
        self.property_tree.setColumnWidth(2, w2)
        self.model.setHeaderData(0, Qt.Horizontal, "Name")
        self.model.setHeaderData(1, Qt.Horizontal, "Value")
        self.model.setHeaderData(2, Qt.Horizontal, "ID/Type")
        self.loaded_objects_and_files.clear()

    def regenerate(self):
        buffer_list = self.loaded_objects_and_files[:]  # copy items in new list
        self.reset()
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

    def set_value_edit(self, item, column):
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

    def check_value_edit(self, item, column):
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


class QCustomDelegate(QItemDelegate):
    def paint(self, painterQPainter, optionQStyleOptionViewItem, indexQModelIndex):
        column = indexQModelIndex.column()
        if column == 3:
            painterQPainter.fillRect(optionQStyleOptionViewItem.rect, QColor(191, 222, 185))
            # currentQAbstractItemModel = indexQModelIndex.model()
            # iconQModelIndex           = currentQAbstractItemModel.index(indexQModelIndex.row(), 1, indexQModelIndex.parent())
            # pathQString               = currentQAbstractItemModel.data(iconQModelIndex, Qt.EditRole).toString()
            # iconQPixmap               = QPixmap(pathQString)
            # if not iconQPixmap.isNull():
            #     painterQPainter.drawPixmap (
            #         optionQStyleOptionViewItem.rect.x(),
            #         optionQStyleOptionViewItem.rect.y(),
            #         iconQPixmap.scaled(20, 20, Qt.KeepAspectRatio))
        else:
            QItemDelegate.paint(self, painterQPainter, optionQStyleOptionViewItem, indexQModelIndex)


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
