import sys
import ifcopenshell
import ifcopenshell.geom


def parse_shape(shape):
    geometry = shape.geometry
    print("id(shape):", str(shape.id))
    print("id(geom): ", str(geometry.id))
    vertices = [geometry.verts[i: i + 3] for i in range(0, len(geometry.verts), 3)]
    print("vertices: ", vertices)
    edges = [geometry.edges[i: i + 2] for i in range(0, len(geometry.edges), 2)]
    print("edges:    ", edges)
    faces = [geometry.faces[i: i + 3] for i in range(0, len(geometry.faces), 3)]
    print("faces:    ", faces)
    normals = [geometry.normals[i: i + 3] for i in range(0, len(geometry.normals), 3)]
    print("normals:    ", normals)
    mat_ids = [geometry.material_ids[i: i + 3] for i in range(0, len(geometry.material_ids), 3)]
    print("mat_ids:    ", mat_ids)


# iterating all geometric representations
def geometry_iterator(ifc_file, settings):
    iterator = ifcopenshell.geom.iterator(settings, ifc_file)
    iterator.initialize()
    while True:
        shape = iterator.get()
        product = shape.product
        print("Product #" + str(product.id()))
        parse_shape(shape)
        if not iterator.next():
            break


# Our Main function
def main():
    ifc_file = ifcopenshell.open(sys.argv[1])
    settings = ifcopenshell.geom.settings()
    settings.set(settings.WELD_VERTICES, False)  # false = generate normals
    geometry_iterator(ifc_file, settings)


if __name__ == "__main__":
    main()
