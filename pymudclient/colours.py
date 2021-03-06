"""Classes and constants for representing colours."""
BLACK = '0'
RED = '1'
GREEN = '2'
YELLOW = '3'
BLUE = '4'
PURPLE = '5'
CYAN = '6'
WHITE = '7'
GREY = '8'
ORANGE= '9'

NORMAL_CODES = set([BLACK, RED, GREEN, YELLOW, BLUE, PURPLE, CYAN, WHITE, GREY,ORANGE])

normal_colours = {BLACK: (0x00, 0x00, 0x00),
                  RED: (0x80, 0x00, 0x00),
                  GREEN: (0x00, 0x80, 0x00),
                  YELLOW: (0x80, 0x80, 0x00),
                  BLUE: (0x36, 0x3A, 0xEB),
                  PURPLE: (0x80, 0x00, 0x80),
                  CYAN: (0x00, 0x61, 0x61),
                  WHITE: (0xC0, 0xC0, 0xC0),
                  GREY: (0x40, 0x40, 0x40),
                  ORANGE: (0xCD, 0x66, 0x00)}

bolded_colours = {BLACK: (0x80, 0x80, 0x80),
                  RED: (0xFF, 0x00, 0x00),
                  GREEN: (0x00, 0xFF, 0x00),
                  YELLOW: (0xFF, 0xFF, 0x00),
                  BLUE: (0x81, 0x81, 0xFF),
                  PURPLE: (0xFF, 0x00, 0xFF),
                  CYAN: (0x00, 0xFF, 0xFF),
                  WHITE: (0xFF, 0xFF, 0xFF),
                  GREY: (0x80, 0x80, 0x80),
                  ORANGE: (0xFF, 0xA5, 0x00)}

_fg_cache = {}
def fg_code(code, bold):
    """Wrapper to convert a VT100 colour code to a HexFGCode."""
    if (code, bold) in _fg_cache:
        return _fg_cache[(code, bold)]
    if bold:
        dictionary = bolded_colours
    else:
        dictionary = normal_colours
    res = HexFGCode(*dictionary[code])
    _fg_cache[(code, bold)] = res
    return res

_bg_cache = {}
def bg_code(code):
    """Wrapper to convert a VT100 colour code to a HexBGCode."""
    if code in _bg_cache:
        return _bg_cache[code]
    res = HexBGCode(*normal_colours[code])
    _bg_cache[code] = res
    return res

class _HexCode(object):
    """Base class for hex colour codes.
    
    The colour attributes are in the range 0..255, where 0 is absent and 255
    is brightest.
    """

    ground = None

    def __init__(self, red, green, blue):
        self.red = red
        self.green = green
        self.blue = blue
        self.triple = (red, green, blue)
        #__hash__ gets called in an inner loop, so cache the value.
        self.as_hex = ''.join(('%x' % num).zfill(2) for num in self.triple)
        self._hashed = hash(self.ground) ^ hash(self.triple)

    def __eq__(self, other):
        return type(self) == type(other) and self.triple == other.triple

#ignore the unused arguments and could-be-a-function messages
#pylint: disable-msg=W0613,R0201

    def __lt__(self, other):
        return NotImplemented

    def __gt__(self, other):
        return NotImplemented

#pylint: enable-msg=W0613,R0201

    def __repr__(self):
        return "<%s %s>" % (type(self).__name__, self.as_hex)

    def __hash__(self):
        return self._hashed

class HexBGCode(_HexCode):
    """A hex background colour."""
    ground = 'back'

class HexFGCode(_HexCode):
    """A hex foreground colour."""
    ground = 'fore'

