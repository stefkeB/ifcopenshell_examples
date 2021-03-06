# GUI Treeviewer Example

These are basic examples of GUI IFC applications, written in Python and using the ifcopenshell library. The Graphical User Interface uses the Qt libraries, more in particular the PyQt5 library. As an alternative and with minimal code changes, it can also use the PySide2 libraries.


## ifc_treeviewer.py

This is not a full viewer, but uses a basic `QTreeWidget` to display the Spatial hierarchy (decomposition and containment).

![result](images/ifc_treeviewer.png)


## ifc_treeviewer2.py

This is a more advanced viewer, where a second tree is used to display type, properties, quantities and attributes of the object selected in the first tree.


![result](images/ifc_treeviewer2_complete.png)

## ifc_schemaviewer.py

A Tree view of the IFC schema. You can switch between IFC2X3 and IFC4 and lower or increase the amount of columns to display.
You can also toggle the display of the Entities, Types, Enumerations and Selects.

![result](images/ifc_schemaviewer.png)