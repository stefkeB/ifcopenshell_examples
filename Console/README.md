# Minimal Console Example

This is a first, very basic example of a minimal console IFC application, written in Python and using the ifcopenshell library.


## First steps - preparation

Create a file called `minimal.py`.


Let's start with importing the necessary Python libraries and provide a main function, so we can run a program from a terminal. The only thing this does right now is reading a file from the arguments and open it using ifcopenshell. There is no error catching, so you best provide it with a valid file and format.

```
python minimal.py IfcOpenHouse.ifc
```

This is the starting point of the source code in the Python file.

```python
import sys
import ifcopenshell

# Our Main function
def main():
    ifc_file = ifcopenshell.open(sys.argv[1])

if __name__ == "__main__":
    main()    
```


## Print the Spatial Hierarchy

We will ask for the one and only `IfcProject`, which returns a list of items, but it should actually only contain a single item. Nonetheless, we prefer to write this as such so whenever you query another class, it will still work when multiple items are returned.

Our `print_hierarchy`function has two arguments:

- `entity` is a reference to any IFC entity, which in this case is the `IfcProject`. From that entity we get its `Name` attribute and its class using the method `.is_a()`, which will print `IfcProject`in this example. We place everything into a formatted string, using the `print` method Python provides.

- `level` is an integer which adds an indent before the string. At zero, there is no indent, but when we increase it, we repeatedly print `.  ` (a dot and two spaces).

```python
import sys
import ifcopenshell

# Our Print Hierarchy function
def print_hierarchy(entity, level):
    print("{0}{1} [{2}]".format('.  ' * level, entity.Name, entity.is_a()))

# Our Main function
def main():
    ifc_file = ifcopenshell.open(sys.argv[1])
    items = ifc_file.by_type('IfcProject')
    print_hierarchy(items[0], 0)

if __name__ == "__main__":
    main()    
```

When you run it now, you'll get a list of the one and only project instance.

```
IfcOpenHouse [IfcProject]
```


## Follow the two main relations

To get the actual spatial hierarchy, we will not only print the object, but recursively call the same function for our all our children. There are two relations in the IFC-scheme we can follow here.

We place them inside the `print_hierarchy` function, so be sure to respect the indentation.

### Is Decomposed By for regular objects

The first thing we need to do is to check the *decomposition* of the entity. This can be retrieved from the `.IsDecomposedBy` attribute, which refers to a list of elements. And thus we need a `for` loop to run through them. We check first to see if we have an entity of class `IfcObjectDefinition` as otherwise it would not have this attribute.

Actually, this is not entirely true. In IFC such lists are kept inside an `IfcRelationship` class and we don't know in advance how many of these we may have. So the call to `.IsDecomposedBy` does not return elements, but rather a list of relations, from which we can get to the actual related objects. So in the second nested `for` loop, we will ask the related objects from the attribute `.RelatedObjects`. And then we feed them into our print_hierarchy function. This is the recursive step, so we increase the level with 1 to get a nicely formatted indent.

```python
# Our Print Hierarchy function (recursive)
def print_hierarchy(entity, level):
    print("{0}{1} [{2}]".format('.  ' * level, entity.Name, entity.is_a()))
    
    if entity.is_a('IfcObjectDefinition'):
        for rel in entity.IsDecomposedBy:
            related_objects = rel.RelatedObjects
            for item in related_objects:
                print_hierarchy(item, level + 1)
```

When we run the script now, we get a nicely indented result:

```
IfcOpenHouse [IfcProject]
.  None [IfcSite]
.  .  None [IfcBuilding]
.  .  .  None [IfcBuildingStorey]
```

Notice that this particular example does not have names for the Site and Building and Building Storey entities, so their name is returned as `None`.



### ContainsElements for Spatial Structure Elements

We can expand this in a very similar way to also retrieve the Spatially contained elements. That way we can get to the actual elements which reside on each Building Storey.

If the entity is of class `IfcSpatialStructureElement` then it has an attribute `.ContainsElements` which, in a very similar way, returns a relationship from which we can get to the related elements via the attribute `.RelatedElements`, which is again a list of elements. Beware that in this case, the wording is slightly different.


```python
    if entity.is_a('IfcSpatialStructureElement'):
        # using IfcRelContainedInSpatialElement to get contained elements
        for rel in entity.ContainsElements:
            contained_elements = rel.RelatedElements
            for element in contained_elements:
                print_hierarchy(element, level + 1)
```

Run the script again and now we get a much deeper output. We get all elements on the Building Storey. Not only that, but we also get their children, as they use the same .IsDecomposedBy relationship. So our recursion effectively gets us through both the `.ContainsElements` and `.IsDecomposedBy` relationships.

```
IfcOpenHouse [IfcProject]
.  None [IfcSite]
.  .  None [IfcBuilding]
.  .  .  None [IfcBuildingStorey]
.  .  .  .  South wall [IfcWallStandardCase]
.  .  .  .  Footing [IfcFooting]
.  .  .  .  Roof [IfcRoof]
.  .  .  .  .  South roof [IfcSlab]
.  .  .  .  .  North roof [IfcSlab]
.  .  .  .  North wall [IfcWallStandardCase]
.  .  .  .  East wall [IfcWallStandardCase]
.  .  .  .  West wall [IfcWallStandardCase]
.  .  .  .  None [IfcStairFlight]
.  .  .  .  None [IfcDoor]
.  .  .  .  None [IfcWindow]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcPlate]
.  .  .  .  None [IfcWindow]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcPlate]
.  .  .  .  None [IfcWindow]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcPlate]
.  .  .  .  None [IfcWindow]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcPlate]
.  .  .  .  None [IfcWindow]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcMember]
.  .  .  .  .  None [IfcPlate]
```


That's it. You can now test this code with other files using the same code.
Here is the full listing or you can [download the file here](minimal.py).


```python
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
```