#!/usr/bin/env python
import json
import argparse
import Ifc.Ifc_All  # DON'T forget this, it registers all the non-trivial IFC entity types
from Ifc import Database
from Ifc.Misc import IfcJSONEncoder

ap = argparse.ArgumentParser(
        formatter_class = argparse.ArgumentDefaultsHelpFormatter,
        description = "Convert an Express schema to a python module containing parser classes",
        )
ap.add_argument("-f", "--datafile", required=True, help = "the input ifc data file")
ap.add_argument("-H", "--header", action="store_true", help = "dump the IFC header or not")
ap.add_argument("-j", "--json", action="store_true", help = "output in JSON format")
args = vars(ap.parse_args())

ifcdb = Database()
ifcdb.read_data_file(args["datafile"])

if args["json"]:
    result = { "entities": [] }
    if args["header"]:
        result["header"] = ifcdb.header

    for idx in sorted(ifcdb.entities.keys()):
        result["entities"].append({"idx": idx, "entity": ifcdb.entities[idx]})

    print json.dumps(result, cls=IfcJSONEncoder)

else: # !args["json"]

    if args["header"]:
        print "\nIFC Header:"
        print ifcdb.header

    print "\nIFC Data:"
    for idx in sorted(ifcdb.entities.keys()):
        print "{i}: {e}".format(i=idx, e=ifcdb.entities[idx])

# vim: set sw=4 ts=4 et:
