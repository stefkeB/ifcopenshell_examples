import sys
import os.path
import csv

try:
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import *
except Exception:
    from PySide2.QtGui import *
    from PySide2.QtCore import *
    from PySide2.QtWidgets import *

import ifcopenshell
from IFCCustomDelegate import *

# region Utility Functions


def get_type_name(element):
    """Retrieve name of the relating Type"""
    result = {}
    if hasattr(element, 'IsDefinedBy') is False:
        return result

    for definition in element.IsDefinedBy:
        if definition.is_a('IfcRelDefinesByType'):
            relating_type = definition.RelatingType
            # result['ifc_object'] = element
            result['ifc_sub_object'] = relating_type
            # result['att_name'] = 'Name'
            result['att_value'] = relating_type.Name
            result['att_type'] = relating_type.attribute_type(2)
            result['att_idx'] = 2
            result['IsEditable'] = True
            return result


def get_attribute_by_name(element, attribute_name):
    """simple function to return the string value of an attribute"""
    result = {}
    # result['ifc_object'] = element
    result['ifc_sub_object'] = element
    # result['att_name'] = attribute_name
    result['IsEditable'] = False
    # exceptions for id, class, type
    if attribute_name == "id":
        # att = getattr(element, 'id')
        result['att_value'] = element.id()
        return result  # str(element.id()), element
    elif attribute_name == "class":
        result['att_value'] = element.is_a()
        return result
    elif attribute_name == "type":
        return get_type_name(element)

    for att_idx in range(0, len(element)):
        att_name = element.attribute_name(att_idx)
        if att_name == attribute_name:
            try:
                att = element[att_idx]
                # att = element.wrapped_data.get_argument(att_name)
                result['att_value'] = str(element.wrap_value(att))
                result['att_type'] = element.attribute_type(att_idx)
                result['att_idx'] = att_idx
                result['IsEditable'] = True
                return result
            except:
                return result


def get_property_or_quantity_by_name(element, prop_or_quantity_name):
    """simple function to return the string value of a property or quantity"""
    result = {}
    # result['object'] = element
    # result['att_name'] = prop_or_quantity_name
    result['IsEditable'] = False
    if hasattr(element, 'IsDefinedBy') is False:
        return result

    # result['ifc_sub_object'] = element
    for definition in element.IsDefinedBy:
        if definition.is_a('IfcRelDefinesByProperties'):
            if hasattr(definition.RelatingPropertyDefinition, "HasProperties"):
                for prop in definition.RelatingPropertyDefinition.HasProperties:
                    if prop.Name == prop_or_quantity_name and prop.is_a('IfcPropertySingleValue'):
                        result['ifc_sub_object'] = prop
                        result['att_value'] = prop.NominalValue.wrappedValue
                        result['att_type'] = prop.attribute_type(2)
                        result['att_idx'] = 2  # NominalValue
                        result['IsEditable'] = True
                        return result  # str(prop.NominalValue.wrappedValue), prop
            if hasattr(definition.RelatingPropertyDefinition, "Quantities"):
                for quantity in definition.RelatingPropertyDefinition.Quantities:
                    if quantity.Name == prop_or_quantity_name:
                        result['ifc_sub_object'] = quantity
                        result['att_type'] = quantity.attribute_type(3)
                        result['att_idx'] = 3  # Quantity Value
                        result['IsEditable'] = False
                        if quantity.is_a('IfcQuantityLength'):
                            result['att_value'] = quantity.LengthValue
                            return result
                        elif quantity.is_a('IfcQuantityArea'):
                            result['att_value'] = quantity.AreaValue
                            return result
                        elif quantity.is_a('IfcQuantityVolume'):
                            result['att_value'] = quantity.VolumeValue
                            return result
                        elif quantity.is_a('IfcQuantityCount'):
                            result['att_value'] = quantity.CountValue
                            return result
                        else:
                            return result


def takeoff_element(element, header):
    """
    Take off element attributes, properties or quantities, from a given header.
    Use the exact name (e.g., "GlobalId" for the GUID, "Name", "Description").

    You can also state "id" for the STEP-ID, "class" to get the IFC entity class
    and "type" to get the name of a linked type.

    :param element: IFC Entity Reference
    :param header: list of strings to indicate attribute, property or quantity
    :return: List of dicts with the actual values
    """
    columns = []
    for search_value in header:
        # first try if it is an attribute
        result = get_attribute_by_name(element, search_value)
        if result is None:  # maybe it is a property or quantity
            result = get_property_or_quantity_by_name(element, search_value)
        columns.append(result)
    return columns

# endregion

# region Header Editor


class StringListEditor(QWidget):
    """
    Generic List Widget to edit a list of Strings.
    Could be applied in different places.
    """
    def __init__(self):
        QWidget.__init__(self)

        # Prepare Widgets in a stretchable layout
        vbox = QVBoxLayout()
        self.setLayout(vbox)

        # Series of buttons and check boxes in a horizontal layout
        buttons = QWidget()
        vbox.addWidget(buttons)
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        buttons.setLayout(hbox)

        # Button : Apply
        apply = QPushButton("Apply")
        apply.setToolTip("Apply the List")
        apply.clicked.connect(self.apply)
        hbox.addWidget(apply)
        # Button : Insert
        insert = QPushButton("Insert")
        insert.setToolTip("Insert Item into the List\nid, class, type or any\nattribute, property or quantity name")
        insert.clicked.connect(self.insert_item)
        hbox.addWidget(insert)
        # Button : Remove
        remove = QPushButton("Remove")
        remove.setToolTip("Remove selected List Item")
        remove.clicked.connect(self.remove_item)
        hbox.addWidget(remove)
        # Stretchable Spacer
        spacer = QSpacerItem(10, 10, QSizePolicy.Expanding)
        hbox.addSpacerItem(spacer)

        # List of Strings
        self.label_list = QListWidget()
        vbox.addWidget(self.label_list)
        self.label_list.setDragDropMode(QListWidget.InternalMove)

    apply_labels = pyqtSignal(object)

    def set_labels(self, labels):
        # self.labels = labels
        self.label_list.clear()
        self.label_list.addItems(labels)
        for index in range(self.label_list.count()):
            item = self.label_list.item(index)
            item.setFlags(item.flags() | Qt.ItemIsEditable)

    def apply(self):
        labels = []
        for item in range(self.label_list.count()):
            labels.append(self.label_list.item(item).text())
        self.apply_labels.emit(labels)

    def insert_item(self):
        new_item = QListWidgetItem("<edit me>")
        new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)

        selection = self.label_list.selectedItems()
        if not selection:
            self.label_list.insertItem(0, new_item)
        for item in selection:
            position = self.label_list.row(item)
            self.label_list.insertItem(position, new_item)
            return

    def remove_item(self):
        selection = self.label_list.selectedItems()
        if not selection: return
        for item in selection:
            self.label_list.takeItem(self.label_list.row(item))

# endregion

# region IFC Listing Widget


class IFCListingWidget(QWidget):
    """
    Fifth version of the IFC Tree Widget/View
    - V1 = Take off Table + Takeoff Button + CSV export + Header Editor
    - V2 = From Table Widget to Table View
    - V3 = Metadata into Takeoff Item to support editing with Delegate
    """
    def __init__(self):
        QWidget.__init__(self)
        # A dictionary referring to our files, based on name
        self.ifc_files = {}

        # Main Settings
        self.root_class = 'IfcElement'
        self.header = []  # list of strings

        # Prepare Main Widgets in a stretchable layout
        vbox = QVBoxLayout()
        self.setLayout(vbox)

        # Series of buttons and check boxes in a horizontal layout
        buttons = QWidget()
        vbox.addWidget(buttons)
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        buttons.setLayout(hbox)

        # Button : Take Off
        takeoff = QPushButton("Take Off")
        takeoff.setToolTip("Generate the Takeoff")
        takeoff.pressed.connect(self.take_off)
        hbox.addWidget(takeoff)
        # Button : Reset
        reset = QPushButton("Reset")
        reset.setToolTip("Reset the Takeoff")
        reset.pressed.connect(self.reset)
        hbox.addWidget(reset)
        # Button : Export to CSV
        export = QPushButton("Export")
        export.setToolTip("Export to CSV")
        export.pressed.connect(self.export)
        hbox.addWidget(export)
        # Stretchable Spacer
        spacer = QSpacerItem(10, 10, QSizePolicy.Expanding)
        hbox.addSpacerItem(spacer)
        # Root Class Chooser
        self.root_class_chooser = QComboBox()
        self.root_class_chooser.setToolTip("Select the IFC class to filter on")
        self.root_class_chooser.setMinimumWidth(80)
        self.root_class_chooser.addItem('IfcElement')
        self.root_class_chooser.addItem('IfcProduct')
        self.root_class_chooser.addItem('IfcWall')
        self.root_class_chooser.addItem('IfcWindow')
        self.root_class_chooser.setEditable(True)
        self.root_class_chooser.activated.connect(self.toggle_chooser)
        hbox.addWidget(self.root_class_chooser)
        # Button : Edit Header
        edit = QPushButton("Edit...")
        edit.setToolTip("Edit the Header Columns")
        edit.pressed.connect(self.edit)
        hbox.addWidget(edit)
        self.header_editor = None
        # Button : Default
        default = QPushButton("Default")
        default.setToolTip("Set default headers")
        default.pressed.connect(self.default_header)
        hbox.addWidget(default)

        # Listing Widget
        self.object_table = QTableView()
        self.model = None
        delegate = QCustomDelegate(self)
        self.object_table.setItemDelegate(delegate)
        vbox.addWidget(self.object_table)
        self.default_header()

    #region Files & UI methods

    def load_file(self, filename):
        """
        Load the IFC file passed as filename.

        :param filename: Full path to the IFC file
        :type filename: str
        """
        ifc_file = None
        if filename in self.ifc_files:
            ifc_file = self.ifc_files[filename]
        else:  # Load as new file
            ifc_file = ifcopenshell.open(filename)
            self.ifc_files[filename] = ifc_file

    def close_files(self):
        self.ifc_files.clear()
        self.reset()

    def reset(self):
        if self.model is not None:
            self.model.clear()
        self.model = QStandardItemModel(0, len(self.header), self)
        self.object_table.setModel(self.model)
        for c, h in enumerate(self.header):
            self.model.setHeaderData(c, Qt.Horizontal, h)

        self.object_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.object_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.object_table.selectionModel().selectionChanged.connect(self.send_selection)

    def edit(self):
        # open a dialog with a StringList edit widget
        if self.header_editor is None:
            self.header_editor = StringListEditor()
        self.header_editor.set_labels(self.header)
        self.header_editor.apply_labels.connect(self.set_headers)
        self.header_editor.show()

    def export(self):
        savepath = QFileDialog.getSaveFileName(self, caption="Save CSV File",
                                    filter="CSV files (*.csv)")
        if savepath[0] != '':
            # Write to CSV file
            csv_file = open(savepath[0], 'w')
            qto_writer = csv.writer(csv_file, delimiter=';')
            qto_writer.writerow(self.header)

            # take off if not done already
            if self.model.rowCount() == 0:
                self.take_off()
            # export table to CSV
            for r in range(self.model.rowCount()):
                record = []
                for c in range(self.model.columnCount()):
                    index = self.model.index(r, c)
                    item_data = index.data(Qt.DisplayRole)
                    record.append(str(item_data))
                qto_writer.writerow(record)
            csv_file.close()

    def set_headers(self, labels):
        self.header = labels
        self.reset()

    def default_header(self):
        self.header.clear()
        # prepare takeoff by listing names of attributes (hardcoded)
        attributes = ["id", "GlobalId", "class", "PredefinedType", "ObjectType", "type", "Name"]
        # names of properties (anything goes)
        properties = ["LoadBearing", "IsExternal", "Reference"]
        # names of quantities (anything goes)
        quantities = ["Length", "Height", "Width", "Perimeter", "Area", "Volume", "Depth",
                      "NetSideArea", "GrossArea", "NetArea", "GrossVolume", "NetVolume"]
        # concatenate
        self.header.extend(attributes + properties + quantities)
        self.reset()

    def toggle_chooser(self, text):
        self.root_class = self.root_class_chooser.currentText()
        self.reset()

    # endregion

    # region Take Off

    def take_off(self):
        self.reset()
        if len(self.header) == 0:
            return
        for _, file in self.ifc_files.items():
            try:
                items = file.by_type(self.root_class)
            except:
                dlg = QMessageBox(self.parent())
                dlg.setWindowTitle("Invalid IFC Class!")
                dlg.setStandardButtons(QMessageBox.Close)
                dlg.setIcon(QMessageBox.Critical)
                dlg.setText(str("{} is not a valid IFC class name.\n"
                                "\nSuggestions are IfcElement or IfcWall.\n"
                                "We will reset it to 'IfcElement'").format(
                    self.root_class))
                dlg.exec_()
                wrong_value = self.root_class
                index_of_wrong = self.root_class_chooser.findText(wrong_value)
                self.root_class_chooser.removeItem(index_of_wrong)
                self.root_class = 'IfcElement'
                self.root_class_chooser.setCurrentText(self.root_class)
                return
            for ifc_object in items:
                record = takeoff_element(ifc_object, self.header)
                # add an empty row
                row = []
                # and fill it with QStandardItems
                for column, cell in enumerate(record):
                    if cell is not None:
                        # we receive a Dict with all required metadata
                        # but some keys may not exist!
                        # ifc_object = cell['ifc_object']
                        ifc_sub_object = cell['ifc_sub_object'] if 'ifc_sub_object' in cell.keys() else None
                        att_name = self.header[column]  # cell['att_name']
                        att_value = cell['att_value'] if 'att_value' in cell.keys() else None
                        att_type = cell['att_type'] if 'att_type' in cell.keys() else None
                        att_idx = cell['att_idx'] if 'att_idx' in cell.keys() else None
                        if ifc_sub_object is not None and att_idx != '' and att_idx is not None:
                            att_name = ifc_sub_object.attribute_name(int(att_idx))
                        editable = cell['IsEditable'] if 'IsEditable' in cell.keys() else False

                        new_item = QStandardItem(str(att_value))
                        if not editable:
                            new_item.setFlags(new_item.flags() ^ Qt.ItemIsEditable)  # make uneditable
                        else:
                            new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)  # make editable
                        new_item.setData(ifc_object, Qt.UserRole)
                        new_item.setData(att_name, Qt.UserRole + 1)  # name
                        new_item.setData(att_value, Qt.UserRole + 2)  # value
                        new_item.setData(att_type, Qt.UserRole + 3)  # type
                        new_item.setData(att_idx, Qt.UserRole + 4)  # index
                        new_item.setData(ifc_sub_object, Qt.UserRole + 5)  # sub object
                        buffer = "ifc_object:\t#" + str(ifc_object.id())
                        buffer += "\natt_name:\t" + str(att_name)
                        buffer += "\natt_value:\t" + str(att_value)
                        buffer += "\natt_type:\t" + str(att_type)
                        buffer += "\natt_idx:\t\t" + str(att_idx)
                        new_item.setToolTip(entity_summary(ifc_object))
                        if column != 0:
                            new_item.setToolTip(buffer)
                        row.append(new_item)
                    else:
                        row.append(QStandardItem())
                self.model.appendRow(row)

    # endregion

    # region Selection Methods

    select_object = pyqtSignal(object)
    deselect_object = pyqtSignal(object)
    send_selection_set = pyqtSignal(object)

    def send_selection(self, selected_items, deselected_items):
        # selection_model = self.object_table.selectionModel()
        # items = selection_model.selectedItems()
        # self.send_selection_set.emit(items)
        # for item in items:
        for index in selected_items.indexes():
            if index.column() == 0:  # only for first column, to avoid repeats
                entity = index.data(Qt.UserRole)
                if hasattr(entity, "GlobalId"):
                    GlobalId = entity.GlobalId
                    if GlobalId != '':
                        self.select_object.emit(GlobalId)
                        print("IFCListingWidget.send_selection.select_object ", GlobalId)

        # send the deselected items as well
        for index in deselected_items.indexes():
            if index.column() == 0:  # only for first column, to avoid repeats
                entity = index.data(Qt.UserRole)
                if hasattr(entity, "GlobalId"):
                    GlobalId = entity.GlobalId
                    if GlobalId != '':
                        self.deselect_object.emit(GlobalId)
                        print("IFCListingWidget.send_selection.deselect_object ", GlobalId)

    def receive_selection(self, ids):
        print("IFCListingWidget.receive_selection ", ids)
        selection_model = self.object_table.selectionModel()
        # check if already selected
        index = selection_model.currentIndex()
        entity = index.data(Qt.UserRole)
        if entity is not None and hasattr(entity, "GlobalId"):
            if entity.GlobalId == ids:
                return
        selection_model.clearSelection()
        if not len(ids):
            return

        for r in range(self.model.rowCount()):
            index = self.model.index(r, 0)  # only for first column, to avoid repeats
            entity = index.data(Qt.UserRole)
            if entity is not None and hasattr(entity, "GlobalId"):
                if entity.GlobalId == ids:
                    self.object_table.selectRow(r)
                    # selection_model.select(index, QItemSelectionModel.Rows)
                    self.object_table.scrollTo(index)

    # endregion

# endregion


if __name__ == '__main__':
    app = 0
    if QApplication.instance():
        app = QApplication.instance()
    else:
        app = QApplication(sys.argv)

    w = IFCListingWidget()
    w.setWindowTitle('IFC Listing')
    w.resize(600, 800)
    # input 2 = CSV with headers
    if len(sys.argv) > 2:
        if os.path.isfile(sys.argv[2]):
            csv_file = open(sys.argv[2])
            reader = csv.reader(csv_file, delimiter=';')
            row1 = next(reader)
            header = []
            for e in row1:
                header.append(str(e))
            w.set_headers(header)
    # input 1 = the IFC file to load
    if os.path.isfile(sys.argv[1]):
        w.load_file(sys.argv[1])
    # finally display the window & execute the app
    w.show()
    sys.exit(app.exec_())
