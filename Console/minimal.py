import sys
import ifcopenshell


# Our Print Hierarchy function (recursive)
def print_hierarchy(entity, level):
    print("{0}{1} [{2}]".format('.  ' * level, entity.Name, entity.is_a()))

    # using IfcRelAggregates to get spatial decomposition of spatial structure elements
    if entity.is_a('IfcObjectDefinition'):
        for rel in entity.IsDecomposedBy:
            related_objects = rel.RelatedObjects
            for item in related_objects:
                print_hierarchy(item, level + 1)

    # only spatial elements can contain building elements
    if entity.is_a('IfcSpatialStructureElement'):
        # using IfcRelContainedInSpatialElement to get contained elements
        for rel in entity.ContainsElements:
            contained_elements = rel.RelatedElements
            for element in contained_elements:
                print_hierarchy(element, level + 1)

# Our Main function
def main():
    ifc_file = ifcopenshell.open(sys.argv[1])
    items = ifc_file.by_type('IfcProject')
    print_hierarchy(items[0], 0)


if __name__ == "__main__":
    main()