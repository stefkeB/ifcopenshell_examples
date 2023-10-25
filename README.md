# IfcOpenShell Examples

Series of examples on how to use IfcOpenShell https://github.com/IfcOpenShell/IfcOpenShell as a general-purpose IFC library.

Primary focus is on Python examples, with and without interface.
See the Wiki for more in-depth explanation for the different examples.

A second objective is to collect all examples into one, more comprehensive IFC-viewer.

# Setup
use pip to install pyside6 to get PySide6, PySide6-Essentials and PySide6-Addons.
```
micromamba create -n bim python=3.11
micromamba activate bim
pip install pyside6 lark ifcopenshell
python 3D/qt3d_minimal.py IfcOpenHouse_IFC4.ifc
```
test qt3d_minimal.py with [IfcOpenHouse_IFC4.ifc](https://github.com/aothms/IfcOpenHouse)
```
python 3D/qt3d_minimal.py IfcOpenHouse_IFC4.ifc
```



