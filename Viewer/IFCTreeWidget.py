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
	Second version of the Basic Tree View
	- V1 = Single Tree (object tree with basic spatial hierarchy)
	- V2 = Double Tree (object with type, properties/quantities + attributes)
	"""
	def __init__(self):
		QWidget.__init__(self)
		self.ifc_file = None
		# Prepare Tree Widgets in a stretchable layout
		vbox = QVBoxLayout()
		self.setLayout(vbox)
		# Object Tree
		self.object_tree = QTreeWidget()
		vbox.addWidget(self.object_tree)
		self.object_tree.setColumnCount(3)
		self.object_tree.setHeaderLabels(["Name", "Class", "ID"])
		self.object_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
		self.object_tree.selectionModel().selectionChanged.connect(self.add_data)
		# Property Tree
		self.property_tree = QTreeWidget()
		vbox.addWidget(self.property_tree)
		self.property_tree.setColumnCount(3)
		self.property_tree.setHeaderLabels(["Name", "Value", "ID/Type"])

	def load_file(self, filename):
		# Import the IFC File
		if self.ifc_file is None:
			self.ifc_file = ifcopenshell.open(filename)
		root_item = QTreeWidgetItem(
			[self.ifc_file.wrapped_data.header.file_name.name, 'File', ""])
		for item in self.ifc_file.by_type('IfcProject'):
			self.add_object_in_tree(item, root_item)
		# Finish the GUI
		self.object_tree.addTopLevelItem(root_item)
		self.object_tree.expandToDepth(3)

	# Attributes
	def add_attributes_in_tree(self, ifc_object, parent_item):
		# the individual attributes
		for att_idx in range(0, len(ifc_object)):
			# https://github.com/jakob-beetz/IfcOpenShellScriptingTutorial/wiki/02:-Inspecting-IFC-instance-objects
			att_name = ifc_object.attribute_name(att_idx)
			att_value = str(ifc_object[att_idx])
			att_type = ifc_object.attribute_type(att_name)
			attribute_item = QTreeWidgetItem([att_name, att_value, att_type])
			parent_item.addChild(attribute_item)

	# PropertySet
	def add_properties_in_tree(self, property_set, parent_item):
		# the individual properties
		for prop in property_set.HasProperties:
			unit = str(prop.Unit) if hasattr(prop, 'Unit') else ''
			prop_value = '<not handled>'
			if prop.is_a('IfcPropertySingleValue'):
				prop_value = str(prop.NominalValue.wrappedValue)
			parent_item.addChild(QTreeWidgetItem([prop.Name, prop_value, unit]))

	# QuantitySet
	def add_quantities_in_tree(self, quantity_set, parent_item):
		# the individual quantities
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

	def add_data(self):
		self.property_tree.clear()
		items = self.object_tree.selectedItems()
		for item in items:
			# the GUID is in the third column
			buffer = item.text(2)
			if not buffer:
				break

			# find the related object in our IFC file
			ifc_object = self.ifc_file.by_guid(buffer)
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

	def add_object_in_tree(self, ifc_object, parent_item):
		tree_item = QTreeWidgetItem([ifc_object.Name, ifc_object.is_a(), ifc_object.GlobalId])
		parent_item.addChild(tree_item)
		if hasattr(ifc_object, 'ContainsElements'):
			for rel in ifc_object.ContainsElements:
				for element in rel.RelatedElements:
					self.add_object_in_tree(element, tree_item)
		if hasattr(ifc_object, 'IsDecomposedBy'):
			for rel in ifc_object.IsDecomposedBy:
				for related_object in rel.RelatedObjects:
					self.add_object_in_tree(related_object, tree_item)


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