#!/usr/bin/env python
from Misc import StatementFileReader, parse_entity
from IfcBase import IfcEntity, IfcGenericEntity, STEPHeader
import STEP_Header_Parts
import time
import sys

class Database(StatementFileReader):
    """
    Read a textfile and parse it into a list of entities
    """

    def __init__(self):
        """
        Initialise the parser
        """
        StatementFileReader.__init__(self, comment_open="/*", comment_close="*/")
        self.header = None
        self.entities = {}


    def read_data_file(self, filename):
        """
        Open a file and read its header, right up until the "DATA" statement.
        """
        self.fd = open(filename, "r")
        self.reset_state()

        # read format statement
        s = self.read_statement(permit_eof=False)
        if s != "ISO-10303-21":
            raise SyntaxError("Unknown format '{fmt}'".format(fmt=s))

        # read everything until "DATA"
        in_header = False
        self.header = STEPHeader()
        while True:
            s = self.read_statement(permit_eof=False)
            if s == "DATA":
                break

            if s == "HEADER":
                in_header = True
            elif s == "ENDSEC":
                in_header = False
            elif in_header:
                # parse the statement and use it as header definition
                e = parse_entity(s)
                self.header.add(e)


        last_printout_time = time.time()
        # read all entities from the input
        while True:
            s = self.read_statement()
            if s == None:
                break
            #print "Statement: {s}".format(s=s)

            if s == "ENDSEC":
                break
           
            # split to 'Index=Entity'
            equal_pos = s.find("=")
            if s[0] != "#" or  equal_pos == -1:
                raise SyntaxError("Invalid entity definition '{val}'".format(val=s))

            index = int(s[1:equal_pos])
            entity = parse_entity(s[equal_pos + 1:])

            if index > 0:
                self.entities[index] = entity

            now = time.time()
            if (last_printout_time + 1) <= now:
                last_printout_time = now
                sys.stderr.write("  index={i}\n".format(i=index))

            #print "  type={t}".format(t=entity.rtype)
            #print "  args={a}".format(a=entity.args)

        self.fd.close()

# vim: set sw=4 ts=4 et:
