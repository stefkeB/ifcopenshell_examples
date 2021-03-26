import sys
import ifcopenshell


# Indent
def indent(level):
    spacer = '.  '
    for i in range(level):
        print(spacer, end='')


# PropertySet
def print_element_properties(property_set, level):
    indent(level), print(property_set.Name)
    for prop in property_set.HasProperties:
        unit = str(prop.Unit) if hasattr(prop, 'Unit') else ''
        prop_value = '<not handled>'
        if prop.is_a('IfcPropertySingleValue'):
            prop_value = str(prop.NominalValue.wrappedValue)
        indent(level + 1)
        print(str('{0} = {1} [{2}]').format(prop.Name, prop_value, unit))


# QuantitySet
def print_element_quantities(quantity_set, level):
    indent(level), print(quantity_set.Name)
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
        indent(level + 1)
        print(str('{0} = {1} [{2}]').format(quantity.Name, quantity_value, unit))


# Our Print Entity function (recursive)
def print_entity(entity, level):
    indent(level), print('#' + str(entity.id()) + ' = ' + entity.is_a()
                         + ' "' + str(entity.Name) + '" (' + entity.GlobalId + ')')
    if hasattr(entity, 'IsDefinedBy'):
        for definition in entity.IsDefinedBy:
            if definition.is_a('IfcRelDefinesByType'):
                print_entity(definition.RelatingType, level + 1)
            if definition.is_a('IfcRelDefinesByProperties'):
                related_data = definition.RelatingPropertyDefinition
                # the individual properties/quantities
                if related_data.is_a('IfcPropertySet'):
                    print_element_properties(related_data, level + 1)
                elif related_data.is_a('IfcElementQuantity'):
                    print_element_quantities(related_data, level + 1)

    # follow Containment relation
    if hasattr(entity, 'ContainsElements'):
        for rel in entity.ContainsElements:
            for child in rel.RelatedElements:
                print_entity(child, level + 1)

    # follow Aggregation/Decomposition Relation
    if hasattr(entity, 'IsDecomposedBy'):
        for rel in entity.IsDecomposedBy:
            for child in rel.RelatedObjects:
                print_entity(child, level + 1)

# Our Main function
def main():
    ifc_file = ifcopenshell.open(sys.argv[1])
    for item in ifc_file.by_type('IfcProject'):
        print_entity(item, 0)


if __name__ == "__main__":
    main()
