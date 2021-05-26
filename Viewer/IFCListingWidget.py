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

# region Utility Functions

def get_type_name(element):
    """Retrieve name of the relating Type"""
    if hasattr(element, 'IsDefinedBy') is False:
        return None

    for definition in element.IsDefinedBy:
        if definition.is_a('IfcRelDefinesByType'):
            return definition.RelatingType.Name


def get_attribute_by_name(element, attribute_name):
    """simple function to return the string value of an attribute"""
    # exceptions for id, class, type
    if attribute_name == "id":
        return str(element.id())
    elif attribute_name == "class":
        return element.is_a()
    elif attribute_name == "type":
        return get_type_name(element)

    for att_idx in range(0, len(element)):
        # https://github.com/jakob-beetz/IfcOpenShellScriptingTutorial/wiki/02:-Inspecting-IFC-instance-objects
        att_name = element.attribute_name(att_idx)
        if att_name == attribute_name:
            try:
                return str(element.wrap_value(element.wrapped_data.get_argument(att_name)))
            except:
                return None


def get_property_or_quantity_by_name(element, prop_or_quantity_name):
    """simple function to return the string value of a property or quantity"""
    if hasattr(element, 'IsDefinedBy') is False:
        return None

    for definition in element.IsDefinedBy:
        if definition.is_a('IfcRelDefinesByProperties'):
            if hasattr(definition.RelatingPropertyDefinition, "HasProperties"):
                for prop in definition.RelatingPropertyDefinition.HasProperties:
                    if prop.Name == prop_or_quantity_name and prop.is_a('IfcPropertySingleValue'):
                        return str(prop.NominalValue.wrappedValue)
            if hasattr(definition.RelatingPropertyDefinition, "Quantities"):
                for quantity in definition.RelatingPropertyDefinition.Quantities:
                    if quantity.Name == prop_or_quantity_name:
                        if quantity.is_a('IfcQuantityLength'):
                            return str(quantity.LengthValue)
                        elif quantity.is_a('IfcQuantityArea'):
                            return str(quantity.AreaValue)
                        elif quantity.is_a('IfcQuantityVolume'):
                            return str(quantity.VolumeValue)
                        elif quantity.is_a('IfcQuantityCount'):
                            return str(quantity.CountValue)
                        else:
                            return None


def takeoff_element(element, header):
    """
    Take off element attributes, properties or quantities, from a given header.
    Use the exact name (e.g., "GlobalId" for the GUID).

    You can also state "id" for the STEP-ID, "class" to get the IFC entity class
    and "type" to get the name of a linked type.

    :param element: IFC Entity Reference
    :param header: list of strings to indicate attribute, property or quantity
    :return: List of strings with the actual values
    """
    columns = []
    for column in header:
        # first try if it is an attribute
        result = get_attribute_by_name(element, column)
        if result is None:  # maybe it is a property or quantity
            result = get_property_or_quantity_by_name(element, column)
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
        self.object_table = QTableWidget()
        vbox.addWidget(self.object_table)
        self.default_header()

    def close_files(self):
        self.ifc_files.clear()
        self.reset()

    def reset(self):
        self.object_table.clear()
        model = self.object_table.model()
        model.removeRows(0, model.rowCount())
        self.object_table.setColumnCount(len(self.header))
        self.object_table.setHorizontalHeaderLabels(self.header)

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
            if self.object_table.rowCount() == 0:
                self.take_off()
            # export table to CSV
            for r in range(self.object_table.rowCount()):
                record = []
                for c in range(self.object_table.columnCount()):
                    item = self.object_table.item(r, c)
                    record.append(item.text())
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
        self.object_table.setColumnCount(len(self.header))
        self.object_table.setHorizontalHeaderLabels(self.header)

    def toggle_chooser(self, text):
        self.root_class = self.root_class_chooser.currentText()
        self.reset()

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
            for item in items:
                record = takeoff_element(item, self.header)
                # add an empty row
                row = self.object_table.rowCount()
                self.object_table.insertRow(row)
                for column, cell in enumerate(record):
                    new_item = QTableWidgetItem(cell)
                    new_item.setFlags(new_item.flags() ^ Qt.ItemIsEditable)
                    new_item.setData(Qt.UserRole, item)
                    new_item.setToolTip('#' + str(item.id()))
                    self.object_table.setItem(row, column, new_item)

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
