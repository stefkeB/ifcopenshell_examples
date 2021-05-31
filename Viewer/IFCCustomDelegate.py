# import sys
# import os.path
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


# region Utility Methods

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


def get_enums_from_object(ifc_object, att_name):
    """
    Check the schema to get the list of enumerations
    for one particular attribute of a class.

    As we don't know the schema from the object (or do we?)
    we try both the IFC2x3 and IFC4 schemes.

    :param ifc_object: instance of an IFC object
    :type ifc_object: entity_instance
    :param att_name: name of the attribute
    :type att_name: str
    """
    if hasattr(ifc_object, att_name):
        att_index = ifc_object.wrapped_data.get_argument_index(att_name)
        # att_value = ifc_object.wrapped_data.get_argument(att_index)
        # att_type = ifc_object.wrapped_data.get_argument_type(att_index)
        att_type = ifc_object.attribute_type(att_index)
        if att_type == 'ENUMERATION':
            try:
                schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name('IFC2x3')
                e_class = schema.declaration_by_name(ifc_object.is_a())
                attribute = e_class.attribute_by_index(att_index)
                return attribute.type_of_attribute().declared_type().enumeration_items()
            except:
                pass
            try:
                schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name('IFC4')
                e_class = schema.declaration_by_name(ifc_object.is_a())
                attribute = e_class.attribute_by_index(att_index)
                return attribute.type_of_attribute().declared_type().enumeration_items()
            except:
                pass


def camel_case_split(string):
    return re.findall(r'[A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$))', string)


def get_friendly_ifc_name(ifc_object):
    # Trick to split the IfcClass into separate words
    s = ' '.join(camel_case_split(str(ifc_object.is_a())))
    s = s[4:]
    return s

# endregion

# region Delegates & Editing


def str2bool(v):
    return str(v).lower() in ("yes", "y", "true", "t", ".t.", "1")


class QCustomDelegate(QItemDelegate):
    # https://stackoverflow.com/questions/41207485/how-to-create-combo-box-qitemdelegate
    # https://stackoverflow.com/questions/18068439/pyqt-simplest-working-example-of-a-combobox-inside-qtableview

    send_update_object = pyqtSignal(object)

    def __init__(self, parent):
        QItemDelegate.__init__(self, parent)
        self.allowed_column = -1

    def set_allowed_column(self, col):
        self.allowed_column = col

    def createEditor(self, widget, option, index):
        """
        Create a Combobox for enumerations
        Create a LineEdit for strings and double
        Create a Spinbox for integers
        Create a Checkbox for Bool
        But do nothing for other data types
        """
        # model = index.model()
        # row = index.row()
        column = index.column()
        # parent = index.parent()
        if column == self.allowed_column or self.allowed_column == -1:
            att_current_value = index.data(Qt.DisplayRole)
            ifc_object = index.data(Qt.UserRole)
            att_name = index.data(Qt.UserRole + 1)
            att_value = index.data(Qt.UserRole + 2)
            att_type = index.data(Qt.UserRole + 3)
            att_index = index.data(Qt.UserRole + 4)
            ifc_sub_object = index.data(Qt.UserRole + 5)
            target = ifc_object
            if ifc_sub_object is not None:
                target = ifc_sub_object
            if target is not None and att_name not in ['GlobalId', 'id', 'type', 'class']:
                # Check Properties (even if we don't know the unit...)
                if target.is_a('IfcPropertySingleValue'):
                    attribute = target.wrapped_data.get_argument('NominalValue')
                    if attribute.is_a('IfcBoolean'):
                        check = QCheckBox(widget)
                        check.setText(target.wrapped_data.get_argument('Name'))  # use the Name of the Property
                        check.setAutoFillBackground(True)
                        check.setChecked(str2bool(att_current_value))
                        return check
                    else:
                        return QItemDelegate.createEditor(self, widget, option, index)  # default
                if att_type == 'ENTITY INSTANCE':
                    return None
                if att_type in ['ENUMERATION']:
                    enums = get_enums_from_object(target, att_name)
                    combo = QComboBox(widget)
                    combo.setAutoFillBackground(True)
                    combo.addItems(enums)
                    combo.setCurrentText(att_current_value)
                    return combo
                if att_type in ['INT']:
                    spin = QSpinBox(widget)
                    spin.setRange(-1e6, 1e6)
                    spin.setValue(int(att_current_value))
                    return spin
                if att_type in ['DOUBLE']:
                    spin = QDoubleSpinBox(widget)
                    spin.setRange(-1e10, 1e10)
                    if att_current_value is None or att_current_value == 'None':
                        spin.setValue(0.0)
                    else:
                        v = att_current_value
                        v2 = float(att_current_value)
                        spin.setValue(float(att_current_value))
                    return spin
                if att_type in ['BOOL']:
                    check = QCheckBox(widget)
                    check.setText(att_name)
                    check.setAutoFillBackground(True)
                    check.setChecked(str2bool(att_current_value))
                    return check
                if att_type in ['STRING']:
                    return QItemDelegate.createEditor(self, widget, option, index)  # default = QLineEdit

                # return QItemDelegate.createEditor(self, widget, option, index)  # default
        return None

    def setModelData(self, editor, model, index):
        """This is the data stored into the field"""
        if isinstance(editor, QComboBox):
            model.setData(index, editor.itemText(editor.currentIndex()))
        if isinstance(editor, QLineEdit):
            model.setData(index, editor.text())
        if isinstance(editor, QSpinBox) or isinstance(editor, QDoubleSpinBox):
            model.setData(index, editor.valueFromText(editor.cleanText()))
        if isinstance(editor, QCheckBox):
            model.setData(index, editor.isChecked())

        column = index.column()
        if column == self.allowed_column or self.allowed_column == -1:
            att_new_value = index.data(Qt.DisplayRole)
            ifc_object = index.data(Qt.UserRole)
            att_name = index.data(Qt.UserRole + 1)
            att_value = index.data(Qt.UserRole + 2)
            att_type = index.data(Qt.UserRole + 3)
            att_index = index.data(Qt.UserRole + 4)
            ifc_sub_object = index.data(Qt.UserRole + 5)
            # TODO: editing property in the Listing View? Get property as sub_object
            target = ifc_object
            if ifc_sub_object is not None:
                target = ifc_sub_object
            if target is not None:
                # PropertySingleValue > wrapped value
                if target.is_a('IfcPropertySingleValue'):
                    try:
                        attribute = target.wrapped_data.get_argument('NominalValue')
                        # attribute = getattr(ifc_object, 'NominalValue')
                        if str(att_new_value) == '':
                            # attribute.setArgumentAsNull(0)  # crashes?
                            target.setArgumentAsNull(3)
                        else:
                            if attribute.is_a('IfcAreaMeasure') or attribute.is_a('IfcLengthMeasure')\
                                    or attribute.is_a('IfcVolumeMeasure'):
                                attribute.setArgumentAsDouble(0, float(att_new_value))
                            elif attribute.is_a('IfcText') or attribute.is_a('IfcLabel'):
                                attribute.setArgumentAsString(0, str(att_new_value))
                            elif attribute.is_a('IfcBoolean'):
                                att_new_value = str2bool(att_new_value)
                                attribute.setArgumentAsBool(0, att_new_value)
                            else:
                                setattr(attribute, 'wrappedValue', att_new_value)
                            model.setData(index, att_new_value)
                    except:
                        print("Could not set Attribute :", att_name, " with value ", att_new_value)
                        print("So we reset it to ", str(target.NominalValue.wrappedValue))
                        model.setData(index, str(att_value))
                        pass
                else:
                    # regular attributes > based on attribute index
                    print("Attribute", att_index, "current:", att_value, "new:", att_new_value)
                    if att_value != att_new_value and hasattr(target, att_name):
                        try:
                            if att_type == 'ENTITY INSTANCE':
                                print('Can not set instance from string')
                            if att_type == 'INT':
                                setattr(target, att_name, int(att_new_value))
                            if att_type == 'DOUBLE':
                                setattr(target, att_name, float(att_new_value))
                            if att_type == 'BOOL':
                                setattr(target, att_name, bool(att_new_value))
                            if att_type == 'ENUMERATION':
                                enum = get_enums_from_object(target, att_name)
                                if att_new_value in enum:
                                    print('Valid enum value')
                                    setattr(target, att_name, att_new_value)
                                else:
                                    print('Invalid enum value')
                                    model.setData(index, str(att_value))
                            if att_type == 'STRING':
                                setattr(target, att_name, att_new_value)
                        except:
                            print("Could not set Attribute :", att_name, " with value ", att_new_value)
                            print("So we reset it to ", att_value)
                            model.setData(index, str(att_value))
                            pass
                        # Warn other views, but only needed if Name is changed
                        if att_name == "Name":
                            self.send_update_object.emit(target)

        else:
            QItemDelegate.setModelData(self, editor, model, index)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def paint(self, painter, styleoptions, index):
        """
        Add a greenish background color to indicate editable cells
        """
        # model = index.model()
        row = index.row()
        column = index.column()
        # parent = index.parent()
        if column == self.allowed_column or self.allowed_column == -1:
            ifc_object = index.data(Qt.UserRole)
            att_name = index.data(Qt.UserRole + 1)
            # att_value = index.data(Qt.UserRole + 2)
            att_type = index.data(Qt.UserRole + 3)
            # att_index = index.data(Qt.UserRole + 4)
            ifc_sub_object = index.data(Qt.UserRole + 5)
            target = ifc_object
            if ifc_sub_object is not None:
                target = ifc_sub_object
            if target is not None:
                if att_name != 'GlobalId'\
                        and att_type in ['STRING', 'DOUBLE', 'ENUMERATION', 'INT', 'BOOL']\
                        and not target.is_a('IfcPhysicalQuantity'):
                    # add a greenish background color to indicate editable cells
                    painter.fillRect(styleoptions.rect, QColor(191, 222, 185, 30))
                elif target.is_a('IfcPropertySingleValue'):
                    painter.fillRect(styleoptions.rect, QColor(191, 185, 222, 30))

        # But also do the regular paint
        QItemDelegate.paint(self, painter, styleoptions, index)

# endregion
