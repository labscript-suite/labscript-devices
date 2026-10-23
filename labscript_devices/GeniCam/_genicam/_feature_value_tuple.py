from collections import namedtuple
from enum import Enum


# The purpose of provising these homemade types instead of using Harvester is to
# not forcing the installation of Harvester on BLACS computer simply because I need
# a few Enum types (only the worker computer needs Harvester)

FeatureValueTuple = namedtuple("FeatureValueTuple", ["name", "value", "type", "entries",
                               "access_mode", "visibility"])


class FeatureType(Enum):
    Value = 0
    Base = 1
    Integer = 2
    Boolean = 3
    Command = 4
    Float = 5
    String = 6
    Register = 7
    Category = 8
    Enumeration = 9
    EnumEntry = 10
    Port = 11

class FeatureAccessMode(Enum):
    NI = 0
    NA = 1
    WO = 2
    RO = 3
    RW = 4

class FeatureVisibility(Enum):
    Beginner = 0
    Expert = 1
    Guru = 2
    Invisible = 3

