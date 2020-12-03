import json
import uuid
import struct
from ClassRegistry import create_entity
from IfcBase import Omitted, Reference, EnumValue, omitted


class StatementFileReader:
    """
    Base class for those who process the input as series of semicolon-delimited statements
    """

    def __init__(self, comment_open="/*", comment_close="*/", string_delimiter="'"):
        """
        Initialise the state machine
        """
        self.comment_open = comment_open
        self.comment_close = comment_close
        self.string_delimiter = string_delimiter
        self.reset_state()


    def reset_state(self):
        """
        Reset the reading/parsing state machine
        """
        # state vars for consolidating input
        self.in_comment = False
        self.in_string_literal = False
        self.chunk_buf = ""
        self.string_literal_until = 0
        # state var for collecting statements
        self.statement_buf = ""
        self.statement_until = 0


    def read_chunk(self):
        """
        Read one non-comment chunk from the input, chunk delimiters being newline, comment boundary and string literal boundary.
        String literals are transcoded before returning them.
        Returns None at the end of file.
        """
        while True:
            if not self.in_string_literal:
                # read more if needed
                if not self.chunk_buf:
                    self.chunk_buf = self.fd.readline()
                    if not self.chunk_buf:
                        return None

                if self.in_comment:
                    # wait for comment end, discard everything up to that
                    comment_end = self.chunk_buf.find(self.comment_close)
                    if comment_end == -1:
                        self.chunk_buf = ""
                        continue

                    # end of comment found
                    self.chunk_buf = self.chunk_buf[comment_end + len(self.comment_close):]
                    self.in_comment = False

                comment_start = self.chunk_buf.find(self.comment_open)
                string_literal_start = self.chunk_buf.find(self.string_delimiter)

                if (comment_start != -1) and ((string_literal_start == -1) or (comment_start < string_literal_start)):
                    # comment starts first
                    result = self.chunk_buf[:comment_start]
                    self.chunk_buf = self.chunk_buf[comment_start + len(self.comment_open):]
                    self.in_comment = True
                elif (string_literal_start != -1) and ((comment_start == -1) or (string_literal_start < comment_start)):
                    # string literal starts first
                    result = self.chunk_buf[:string_literal_start]
                    self.chunk_buf = self.chunk_buf[string_literal_start + len(self.string_delimiter):]
                    self.in_string_literal = True
                    self.string_literal_until = 0
                    # don't return @result here. if it's empty, just skip and go on
                else:
                    # plain stuff
                    result = self.chunk_buf
                    self.chunk_buf = ""

            else: # self.in_string_literal
                string_literal_end = self.chunk_buf.find(self.string_delimiter, self.string_literal_until)
                if string_literal_end == -1:
                    # delimiter not found, read more
                    new_chunk = self.fd.readline()
                    if not new_chunk:
                        # FIXME: unclosed string literal, now return as it is
                        result = self.transcode_string_literal(self.chunk_buf)
                        self.reset_state()
                        return result;
                    self.chunk_buf = self.chunk_buf + new_chunk
                    continue

                # check if it is a '', which marks the apostrophe itself (facepalm)
                if ((string_literal_end + 1) < len(self.chunk_buf)) and (self.chunk_buf[string_literal_end + 1] == self.string_delimiter):
                    self.string_literal_until = string_literal_end + 1 + len(self.string_delimiter)
                    continue

                # end of literal found
                result = self.transcode_string_literal(self.chunk_buf[:string_literal_end])
                if (string_literal_end + 1) < len(self.chunk_buf):
                    self.chunk_buf = self.chunk_buf[string_literal_end + 1:]
                else:
                    self.chunk_buf = ""
                self.in_string_literal = False
                self.string_literal_until = 0
                return result; # DO return it, even the empty string will result in ''

            result = result.strip("\r\n")
            if result:
                return result


    def read_statement(self, permit_eof=True, zap_whitespaces=False):
        """
        Read one statement from the input, remove the trailing semicolon
        """
        while True:
            semicolon_pos = self.statement_buf.find(";", self.statement_until)
            if semicolon_pos != -1:
                result = self.statement_buf[:semicolon_pos].rstrip()
                self.statement_buf = self.statement_buf[semicolon_pos + 1:].lstrip()
                self.statement_until = 0
                if zap_whitespaces:
                    return " ".join(result.split())
                else:
                    return result

            new_chunk = self.read_chunk()
            if new_chunk.startswith('TYPE IfcActionRequestTypeEnum'):
                print()
            if new_chunk == None: # EOF
                if not self.statement_buf:
                    # no leftover, return None to signal the end
                    if permit_eof:
                        return None
                    raise EOFError()

                # FIXME: unfinished statement at EOF
                result = self.statement_buf
                self.reset_state()
                if zap_whitespaces:
                    return " ".join(result.split())
                else:
                    return result.strip()

            self.statement_until = len(self.statement_buf)
            if new_chunk[0] == "\"": # it was a string literal
                self.statement_until += len(new_chunk) # don't check semicolon in
            self.statement_buf = self.statement_buf + new_chunk


    def transcode_string_literal(self, s):
        """
        Interpret 's' as ISO 10303-11 string, and return it as quoted json-escaped utf8 string.
        As it should've been right from the start, if you ask me...
        """
        pos = 0
        while True:
            # resolve ''-s to '-s (we may assume that they occur only in pairs)
            pos = s.find(self.string_delimiter, pos)
            if pos == -1:
                break
            s = s[:pos] + s[pos + len(self.string_delimiter):] # leave only the second one
            pos += 1

        # Don't blame me, that's how they 'invented' (or rather 'unvented') it...
        # http://www.buildingsmart-tech.org/downloads/accompanying-documents/guidelines/IFC2x%20Model%20Implementation%20Guide%20V2-0b.pdf
        pos = len(s) - 3
        endpos = -1
        while pos > 0:
            if s[pos:pos + 3] == "\\S\\":
                # FIXME: handle missing/invalid arg
                s = s[:pos] + unichr(ord(pos[s + 3]) + 0x80) + s[pos + 4:]
                pos -= 3
            elif s[pos:pos + 3] == "\\X\\":
                # FIXME: handle missing/invalid arg
                s = s[:pos] + unichr(int(pos[s + 3:s + 5], base=16)) + s[pos + 5:]
                pos -= 3
            elif s[pos:pos + 4] == "\\X0\\":
                s = s[:pos] + s[pos + 4:]
                endpos = pos
                pos -= 3
            elif s[pos:pos + 4] == "\\X2\\":
                if endpos < pos + 4:
                    raise SyntaxError("Unterminated X2 escape block in {val}".format(val=s))
                s = s[:pos] + "".join(unichr(int(s[i:i + 4], base=16)) for i in xrange(pos + 4, endpos, 4)) + s[endpos:]
                endpos = -1
                pos -= 3
            elif s[pos:pos + 4] == "\\X4\\":
                if endpos < pos + 4:
                    raise SyntaxError("Unterminated X4 escape block in {val}".format(val=s))
                s = s[:pos] + "".join(unichr(int(s[i:i + 8], base=16)) for i in xrange(pos + 4, endpos, 8)) + s[endpos:]
                endpos = -1
                pos -= 3
            else:
                pos -= 1
        # OK, now wipe your eyes and proceed...

        return json.dumps(s)


###############################################################
# Parser primitives
#

def find_matching_paren_pair(s):
    """
    Find the first matching pair of parentheses and return their positions
    """
    paren_level = -1
    open_pos = 0
    for i in range(0, len(s)):
        if s[i] == "(":
            paren_level += 1
            if paren_level == 0:
                open_pos = i
        elif s[i] == ")":
            if paren_level == 0:
                return (open_pos, i)
            paren_level -= 1
    raise SyntaxError("Unterminated list '{val}'".format(val=s))


def parse_expression(s):
    """
    Splits an expression that can be:
    - string (quoted)
    - integer (number, without dot)
    - real (number, with one dot)
    - None ($)
    - enumvalue (.VALUE.)
    - omitted (*)
    - reference (#N)
    - list (parenthesis-delimited, comma-separated)
    """
    s = s.strip()
    #print("parse_expression('{val}')".format(val=s))
    if s[0] == "$": # unset
        return None
    elif s[0] == "*": # omitted
        return omitted
    elif s[0] == "#": # reference
        return Reference(int(s[1:]))
    elif s[0] == ".": # enum value
        if s == ".T.":
            return True
        elif s == ".F.":
            return False
        elif s == ".U.":
            return None
        elif s[-1] != ".":
            raise SyntaxError("Unterminated enum value '{val}'".format(val=s))
        return EnumValue(s[1:-1])
    elif s[0] == "\"": # string
        if s[-1] != "\"":
            raise SyntaxError("Unterminated string value '{val}'".format(val=s))
        return json.loads(s)
    elif s[0] == "(": # list
        items = []
        paren_level = -1
        item_start = 0
        within_quote = False
        after_backslash = False
        for i in xrange(0, len(s)):
            if within_quote:
                if after_backslash:
                    after_backslash = False
                elif s[i] == "\\":
                    after_backslash = True
                elif s[i] == "\"":
                    within_quote = False
            elif s[i] == "\"":
                within_quote = True
            elif s[i] == "(":
                paren_level += 1
                if paren_level == 0:
                    item_start = i + 1
            elif (s[i] == ",") and (paren_level == 0): # top-level comma
                items.append(parse_expression(s[item_start:i]))
                item_start = i + 1
            elif s[i] == ")":
                if paren_level == 0:
                    if i != len(s) - 1:
                        raise SyntaxError("Junk after list '{val}'".format(val=s[i + 1:]))
                    if item_start < i:
                        items.append(parse_expression(s[item_start:i]))
                    return items
                paren_level -= 1
        raise SyntaxError("Unterminated list '{val}'".format(val=s))
    elif (s[0] == "+") or (s[0] == "-") or (("0" <= s[0]) and (s[0] <= "9")): # number
        if s.find(".") == -1:
            return int(s)
        else:
            return float(s)
    else: # entity
        return parse_entity(s)


def parse_entity(s):
    """
    Parse a "TYPE(whatever1, whatever2, ...)" string into an Entity instance (or one of its subtypes)
    The arguments are parsed recursively.
    """
    # split s as "TYPE(REST"
    open_pos = s.find("(")
    if open_pos == -1:
        raise SyntaxError("Invalid entity specification '{val}'".format(val=s))
    rtype = s[:open_pos].strip()
    args = parse_expression(s[open_pos:])
    args.reverse() # passed in *reverse* order so the classes can just args.pop() their argument off of it
    return create_entity(rtype, args)


# num_to_IFC_symbol = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
IFC_symbol_to_num = {
    "0": 0x00, "1": 0x01, "2": 0x02, "3": 0x03, "4": 0x04, "5": 0x05, "6": 0x06, "7": 0x07,
    "8": 0x08, "9": 0x09, "A": 0x0a, "B": 0x0b, "C": 0x0c, "D": 0x0d, "E": 0x0e, "F": 0x0f,
    "G": 0x10, "H": 0x11, "I": 0x12, "J": 0x13, "K": 0x14, "L": 0x15, "M": 0x16, "N": 0x17,
    "O": 0x18, "P": 0x19, "Q": 0x1a, "R": 0x1b, "S": 0x1c, "T": 0x1d, "U": 0x1e, "V": 0x1f,
    "W": 0x20, "X": 0x21, "Y": 0x22, "Z": 0x23, "a": 0x24, "b": 0x25, "c": 0x26, "d": 0x27,
    "e": 0x28, "f": 0x29, "g": 0x2a, "h": 0x2b, "i": 0x2c, "j": 0x2d, "k": 0x2e, "l": 0x2f,
    "m": 0x30, "n": 0x31, "o": 0x32, "p": 0x33, "q": 0x34, "r": 0x35, "s": 0x36, "t": 0x37,
    "u": 0x38, "v": 0x39, "w": 0x3a, "x": 0x3b, "y": 0x3c, "z": 0x3d, "_": 0x3e, "$": 0x3f
    }

#    "03ysyxbDL43OX0YOp9OPQ_" -> {03F36F3B-94D5-440D-8840-898CC96196BE}
#
#    0 -> v[ 0] = 0 = 00 0000 \ (0000)00 000011 = (0000) 00000011 = 03
#    3 -> v[ 1] = 3 = 00 0011 /
#    y -> v[ 2] =60 = 11 1100 \
#    s -> v[ 3] =54 = 11 0110  \ 111100 110110 111100 111011 =
#    y -> v[ 4] =60 = 11 1100  / 11110011 01101111  00111011 = F36F3B
#    x -> v[ 5] =59 = 11 1011 /
#    b -> v[ 6] =37 = 10 0101 \
#    D -> v[ 7] =13 = 00 1101  \ 100101 001101 010101 000100 =
#    L -> v[ 8] =21 = 01 0101  / 10010100 11010101  01000100 = 94D544
#    4 -> v[ 9] = 4 = 00 0100 /
#    3 -> v[10] = 3 = 00 0011 \
#    O -> v[11] =24 = 01 1000  \ 000011 011000 100001 000000 =
#    X -> v[12] =33 = 10 0001  / 00001101 10001000  01000000 = 0D8840
#    0 -> v[13] = 0 = 00 0000 /
#    Y -> v[14] =34 = 10 0010 \
#    O -> v[15] =24 = 01 1000  \ 100010 011000 110011 001001 =
#    p -> v[16] =51 = 11 0011  / 10001001 10001100  11001001 = 898CC9
#    9 -> v[17] = 9 = 00 1001 /
#    O -> v[18] =24 = 01 1000 \
#    P -> v[19] =25 = 01 1001  \ 011000 011001 011010 111110 =
#    Q -> v[20] =26 = 01 1010  / 01100001 10010110  10111110 = 6196BE
#    _ -> v[21] =62 = 11 1110 /

def parse_uuid(s):
    """
    Parses an IFC-encoded uuid. Don't blame me, I wasn't there when they unvented it...
    """
    v = map(lambda c: IFC_symbol_to_num[c], s)
    i = 0
    b = []
    while True:
        b.append(((v[i] & 0x03) << 6) + v[i + 1])
        if i == 20:
            break
        b.append((v[i + 2] << 2) + (v[i + 3] >> 4))
        b.append(((v[i + 3] & 0x0f) << 4) + (v[i + 4] >> 2))
        i += 4
    return uuid.UUID(bytes=struct.pack("BBBBBBBBBBBBBBBB", *b))


class IfcJSONEncoder(json.JSONEncoder):
    """
    JSONEncoder subclass that leverages an object's `__json__()` method,
    if available, to obtain its default JSON representation.
    https://stackoverflow.com/a/24030569

    """
    def default(self, obj):
        if hasattr(obj, '__json__'):
            return obj.__json__()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        return json.JSONEncoder.default(self, obj)

# vim: set sw=4 ts=4 et:
