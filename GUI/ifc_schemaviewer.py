import sys
import os.path
from PyQt5.QtWidgets import *
import ifcopenshell


class SchemaViewer(QWidget):
    """
    Tree View to show the inheritance tree of IFC classes
    from the schema (choice between IFC2X3 and IFC4).
    """

    def __init__(self):
        QWidget.__init__(self)

        # Prepare Tree Widgets in a stretchable layout
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)

        # Schema Chooser
        self.current_schema = 'IFC2X3'
        self.schema_chooser = QComboBox()
        self.schema_chooser.addItems(['IFC2X3', 'IFC4'])
        self.schema_chooser.activated[str].connect(self.set_schema)
        hbox.addWidget(self.schema_chooser)

        # Column Count Chooser
        self.columns = 5
        self.column_chooser = QSpinBox()
        self.column_chooser.setValue(self.columns)
        self.column_chooser.valueChanged.connect(self.set_columns)
        hbox.addWidget(self.column_chooser)

        # Main Tree
        self.object_tree = QTreeWidget()
        vbox.addWidget(self.object_tree)

        self.reload_schema()

    def set_columns(self, columns):
        self.columns = columns
        self.reload_schema()

    def set_schema(self, ifc_schema):
        self.current_schema = ifc_schema
        self.reload_schema()

    def reload_schema(self):
        self.object_tree.setColumnCount(self.columns)
        labels = ['IFC Entity Class']
        for s in range(self.columns):
            labels.append("Attribute" + str(s + 1))
        self.object_tree.setHeaderLabels(labels)

        self.object_tree.clear()
        schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(self.current_schema)
        for e in schema.entities():
            self.add_class_in_tree(e)
        self.object_tree.expandToDepth(0)

    def add_class_in_tree(self, entity, parent_item=None, level=0):
        """
        :param entity: IFC Entity Class
        :param parent_item:
        :type parent_item: QTreeWidgetItem
        :return:
        """
        e = entity
        e_index = e.index_in_schema()
        e_name = e.name()

        # parent = e.supertype()
        # while parent is not None:
        #    parent = parent.supertype()

        e_super = e.supertype()
        # At level 0, we only load non-rooted classes
        # At other levels, we dive deeper, recursively
        if level > 0 or (level == 0 and e_super is None):
            buffer = [str(entity.name())]
            attributes = e.all_attributes()
            c = e.attribute_count()
            for a in range(e.attribute_count()):
                attribute = e.attribute_by_index(a)
                a_name = attribute.name() if hasattr(attribute, 'name') else "<name>"
                # a_type = attribute.type_of_attribute().declared_type().name() if hasattr(attribute.type_of_attribute(), 'declared_type') else "<type>"
                # a_optional = str(attribute.optional()) if hasattr(attribute, 'optional') else "<optional>"
                buffer.append(a_name)
                # child = QTreeWidgetItem([a_name])
                # item.addChild(child)

            item = QTreeWidgetItem(buffer)
            if parent_item is not None:
                parent_item.addChild(item)
            else:
                self.object_tree.addTopLevelItem(item)

            # sub types
            e_subs = e.subtypes()
            for s in e.subtypes():
                self.add_class_in_tree(s, item, level+1)


if __name__ == '__main__':
    app = 0
    if QApplication.instance():
        app = QApplication.instance()
    else:
        app = QApplication(sys.argv)

    w = SchemaViewer()
    w.resize(600, 800)
    w.show()
    sys.exit(app.exec_())
