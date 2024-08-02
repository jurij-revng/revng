###- This template file is distributed under the MIT License. See LICENSE.md for details. -###
###- The notice below applies to the generated files. -###

# This file is distributed under the MIT License. See LICENSE.md for details.
# This file is autogenerated! Do not edit it directly
import random
import sys
from dataclasses import dataclass, field
from typing import List

from revng.tupletree import (
    EnumBase,
    Reference,
    StructBase,
    AbstractStructBase,
    dataclass_kwargs,
    no_default,
    typedlist_factory,
    force_constructor_kwarg,
    force_kw_only,
    DiffSet
)
from revng.tupletree import YamlLoader as _ExternalYamlLoader
from revng.tupletree import YamlDumper as _ExternalYamlDumper
from revng.tupletree import DiffYamlLoader as _DiffExternalYamlLoader
from revng.tupletree import DiffYamlDumper as _DiffExternalYamlDumper
##- for t in generator.external_types ##
from .external import 't'
## endfor ##

##- if schema.base_namespace == 'model' -##
##- for import in get_mixins_imports() ##
'import'
##- endfor -##
##- endif ##

# Every subclass of YamlLoader can register its own independent loaders
class YamlLoader(_ExternalYamlLoader):
    pass

# Every subclass of YamlDumper can register its own independent dumpers
class YamlDumper(_ExternalYamlDumper):
    pass


class DiffYamlLoader(YamlLoader):
    pass


class DiffYamlDumper(YamlDumper):
    pass


def random_id():
    return random.randint(2 ** 10 + 1, 2 ** 64 - 1)


## for enum in enums ##
class 'enum.name'(EnumBase):
    Invalid = "Invalid"
    ## for member in enum.members ##
    ##- if member.doc ##
    '-member.doc | docstring'
    ## endif ##
    '-member.name' = "'member.name'"
    ## endfor ##
## endfor ##

## for t in generator.string_types ##
't' = str
## endfor ##

## for struct in structs ##
@dataclass(**dataclass_kwargs)
class 'struct.name'(
    ##- if struct.inherits -##
    'struct.inherits.name',
    ##- endif -##
    ##- if struct.abstract -##
    AbstractStructBase,
    ##- else -##
    StructBase,
    ##- endif -##
    ##- if schema.base_namespace == 'model' -##
    '- struct.name | get_mixins'
    ##- endif -##
):
    'struct.doc | docstring'

    ##- for field in struct.required_fields ##
    ## if field.doc ##
    '-field.doc | docstring'
    ## endif ##
    '-field.name': "'field | python_type'"
    ##- if field.is_guid -##
    = field(default_factory=random_id)
    ##- elif field is sequence_field -##
    = field(default_factory=typedlist_factory('field | python_type'))
    ##- elif field is reference_field -##
    = field(default_factory=lambda: Reference(""))
    ##- elif struct.inherits -##
    = field(default=no_default)
    ##- endif ##

    ##- endfor ##

    ##- for field in struct.optional_fields ##
    ## if field.doc ##
    '-field.doc | docstring'
    ## endif ##
    '-field.name': "'field | python_type'" = field(
        metadata={"optional": True, "default_value": lambda: '- field | default_value '},
        ## if field.is_guid ##default_factory=random_id,## endif ##
        ## if field is simple_field ##
        default_factory=lambda: '- field | default_value '
        ## elif field is sequence_field ##
        default_factory=typedlist_factory('field | python_type')
        ## elif field is reference_field ##
        default_factory=lambda: Reference("")
        ## endif ##
    )
    ##- endfor ##

    def __hash__(self):
        return id(self)

    ## if struct.key_fields | length > 0 ##
    @staticmethod
    def parseKey(key):
        parts = key.split("-")
        return { ' struct | key_parser ' }

    keyed = True
    def key(self):
        return ' struct | gen_key '
    ## endif ##

## endfor ##

## for struct in structs ##
## if struct.abstract -##
'struct.name'._children = {
        ##- for child in struct.children -##
        "'-child.name'": '-child.name' ##- if not loop.last -## , ##- endif -##
        ##- endfor -##
    }

### Override child's constructor so that the 'Kind' kwarg is always consistent -###
## for child in struct.children -##
force_constructor_kwarg('child.name', "Kind", 'struct.name'Kind.'child.name')
## endfor ##

##- endif ##
## endfor ##
if sys.version_info < (3, 10, 0):
##- for struct in structs ##
    force_kw_only('struct.name')
##- endfor ##

TypeHints = {}
##- for struct in structs ##
TypeHints['-struct.name'] = {
    ##- for field in struct.fields ##
    "'-field.name'": 'field | type_hint',
    ## endfor ##
    ##- if struct.inherits ##
    ##- for field in struct.inherits.fields ##
    "'-field.name'": 'field | type_hint' ##-if not loop.last -##,##- endif -##
    ##- endfor ##,
    ##- endif ##
}
##- endfor ##

## for enum in enums ##
YamlDumper.add_representer('enum.name', 'enum.name'.yaml_representer)
##- endfor ##
## for struct in structs ##
YamlDumper.add_representer('struct.name', 'struct.name'.yaml_representer)
##- endfor ##
## if generator.root_type ##
# Allows to deserialize YAML as a 'generator.root_type' even if the root of the YAML document is
# not tagged
YamlLoader.add_constructor("!'generator.root_type'", 'generator.root_type'.yaml_constructor)
YamlLoader.add_path_resolver("!'generator.root_type'", [])
## endif ##
DiffYamlLoader.add_constructor("!DiffSet", DiffSet.yaml_constructor)
DiffYamlLoader.add_path_resolver("!DiffSet", [])
