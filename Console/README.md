# Console Examples

## Console Example (minimal.py)

This is a very basic example of a minimal console IFC application, written in Python and using the IfcOpenShell library.

It opens a file and returns the Spatial Hierachy, starting from the one and only `IfcProject` entity.

## Print Hierachy (IFCOSPrintHierachy.py)

More advanced console example, which expands the minimal example with the full list of all properties, quantities and type.

## Geometry (geometry_minimal.py)

A minimalistic example of parsing all geometric representations, using the iterator from the IfcOpenShell `geom` library, to get to the polygonal mesh representations. This uses the `OpenCascade` libraries to get to the individual vertices, edges, faces and normals.
