import sys
from PyQt5.QtWidgets import *
import ifcopenshell


class SchemaViewer(QWidget):
    """
    Tree View to show the inheritance tree of IFC classes
    from the schema (choice between IFC2X3 and IFC4).
    - V1 = Single Tree (object tree with basic spatial hierarchy)
    - V2 = Add Types and Enumerations
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
        self.schema_chooser.addItems(['IFC2X3', 'IFC4', 'IFC4x1','IFC4x2','IFC4x3_rc1','IFC4x3_rc2','IFC4x3_rc3','IFC4x3_rc4'])
        self.schema_chooser.activated[str].connect(self.set_schema)
        hbox.addWidget(self.schema_chooser)

        # Column Count Chooser
        self.columns = 2
        self.column_chooser = QSpinBox()
        self.column_chooser.setValue(self.columns)
        self.column_chooser.valueChanged.connect(self.set_columns)
        hbox.addWidget(self.column_chooser)

        # option show entities
        self.show_entities = True
        self.check_ent = QCheckBox("Entities")
        self.check_ent.setToolTip("Display all Entities")
        self.check_ent.setChecked(self.show_entities)
        self.check_ent.toggled.connect(self.toggle_show_entities)
        hbox.addWidget(self.check_ent)
        # option show types
        self.show_types = False
        self.check_types = QCheckBox("Types")
        self.check_types.setToolTip("Display all Types")
        self.check_types.setChecked(self.show_types)
        self.check_types.toggled.connect(self.toggle_show_types)
        hbox.addWidget(self.check_types)
        # option show enumerations
        self.show_enums = False
        self.check_enums = QCheckBox("Enumerations")
        self.check_enums.setToolTip("Display all Enumerations")
        self.check_enums.setChecked(self.show_enums)
        self.check_enums.toggled.connect(self.toggle_show_enums)
        hbox.addWidget(self.check_enums)
        # option show selects
        self.show_selects = False
        self.check_selects = QCheckBox("Selects")
        self.check_selects.setToolTip("Display all Select Types")
        self.check_selects.setChecked(self.show_selects)
        self.check_selects.toggled.connect(self.toggle_show_selects)
        hbox.addWidget(self.check_selects)

        # Stretchable Spacer
        spacer = QSpacerItem(10, 10, QSizePolicy.Expanding)
        hbox.addSpacerItem(spacer)

        # Object Tree
        self.object_tree = QTreeWidget()
        vbox.addWidget(self.object_tree)

        self.reload_schema()

    def set_columns(self, columns):
        self.columns = columns
        self.reload_schema()

    def set_schema(self, ifc_schema):
        self.current_schema = ifc_schema
        self.reload_schema()

    def toggle_show_entities(self):
        self.show_entities = not self.show_entities
        self.reload_schema()

    def toggle_show_types(self):
        self.show_types = not self.show_types
        self.reload_schema()

    def toggle_show_selects(self):
        self.show_selects = not self.show_selects
        self.reload_schema()

    def toggle_show_enums(self):
        self.show_enums = not self.show_enums
        self.reload_schema()

    def reload_schema(self):
        self.object_tree.setColumnCount(self.columns)
        labels = ['IFC Entity (class)']
        for s in range(self.columns):
            labels.append(str(s + 1))
        self.object_tree.setHeaderLabels(labels)

        self.object_tree.clear()
        # root_item = QTreeWidgetItem(["SCHEMA", ifc_schema])
        # self.object_tree.addTopLevelItem(root_item)
        schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(self.current_schema)
        # for e in schema.entities():
        #    self.add_class_in_tree(e)

        for d in schema.declarations():
            self.add_declaration_in_tree(d)

        self.object_tree.expandToDepth(0)
        # self.object_tree.expandAll()

    def add_declaration_in_tree(self, declaration, parent_item=None, level=0):
        d = declaration
        d_index = d.index_in_schema()
        d_name = d.name()

        if d.as_entity() is not None:
            e = d.as_entity()
            if self.show_entities:
                self.add_class_in_tree(e)

        if d.as_type_declaration() is not None:
            t = d.as_type_declaration()
            if self.show_types:  # or self.show_selects and level > 0:
                t_val = str(t)
                t_tip = ''
                if t.declared_type().as_simple_type() is not None:
                    t_val = str(t.declared_type().as_simple_type())
                    t_tip = 'type_declaration:simple_type'
                if t.declared_type().as_named_type() is not None:
                    t_val = str(t.declared_type().as_named_type())
                    t_tip = 'type_declaration:name_type'
                if t.declared_type().as_aggregation_type() is not None:
                    t_val = str(t.declared_type().as_aggregation_type())
                    t_tip = 'type_declaration:aggregation_type'
                item = QTreeWidgetItem([d_name, t_val, t_tip])
                item.setToolTip(0, t_tip)
                if parent_item is not None:
                    parent_item.addChild(item)
                else:
                    self.object_tree.addTopLevelItem(item)

        if d.as_enumeration_type() is not None:
            e = d.as_enumeration_type()
            if self.show_enums:
                buffer = [d_name]
                for enum in e.enumeration_items():
                    buffer.append(enum)
                item = QTreeWidgetItem(buffer)
                item.setToolTip(0, 'enumeration_type:\n' + ', '.join(buffer[1:]))
                if parent_item is not None:
                    parent_item.addChild(item)
                else:
                    self.object_tree.addTopLevelItem(item)

        if d.as_select_type() is not None:
            s = d.as_select_type()
            if self.show_selects or level > 0:
                item = QTreeWidgetItem([d_name])
                item.setToolTip(0, 'select_type')
                if parent_item is not None:
                    parent_item.addChild(item)
                else:
                    self.object_tree.addTopLevelItem(item)
                for sub in s.select_list():
                    self.add_declaration_in_tree(sub, item, level+1)

    def add_class_in_tree(self, entity, parent_item=None, level=0):
        """
        Recursive function to fill the tree with entity declarations

        :param entity: IFC Entity Class
        :param parent_item: item to which our item is attached
        :type parent_item: QTreeWidgetItem
        :param: level: depth of the tree at this point
        :param: level: int
        :return:
        """
        # At level 0, we only load non-rooted classes
        # At other levels, we dive deeper, recursively
        if level > 0 or (level == 0 and entity.supertype() is None):
            buffer = [str(entity.name())]
            attributes = entity.all_attributes()
            c = entity.attribute_count()
            for a in range(entity.attribute_count()):
                attribute = entity.attribute_by_index(a)
                a_name = attribute.name() if hasattr(attribute, 'name') else "<name>"
                # a_type = attribute.type_of_attribute().declared_type().name() if hasattr(attribute.type_of_attribute(), 'declared_type') else "<type>"
                # a_optional = str(attribute.optional()) if hasattr(attribute, 'optional') else "<optional>"
                buffer.append(a_name)

            item = QTreeWidgetItem(buffer)
            if parent_item is not None:
                parent_item.addChild(item)
            else:
                self.object_tree.addTopLevelItem(item)

            # sub types
            for s in entity.subtypes():
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
