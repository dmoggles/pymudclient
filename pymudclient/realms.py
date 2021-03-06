"""Hierarchical stacking contexts for execution."""
from code import InteractiveConsole
from pymudclient.escape_parser import EscapeParser
from pymudclient.colours import fg_code, bg_code, BLACK, WHITE, HexFGCode
from pymudclient.metaline import Metaline, simpleml
from pymudclient.triggers import TriggerMatchingRealm, TriggerBlockMatchingRealm
from pymudclient.aliases import AliasMatchingRealm
from pymudclient.modules import load_file
from pymudclient.gui.bindings import gui_macros
from pymudclient.tagged_ml_parser import taggedml
from textwrap import TextWrapper
from operator import attrgetter
import traceback
import time





class RootRealm(object):
    """The root of the realms hierarchy. This is what macros and top-level
    modules deal with.
    """

    def __init__(self, factory):
        self.factory = factory
        self.root=self
        self.telnet = None
        self.triggers = []
        self.aliases = []
        self.baked_in_macros = gui_macros.copy()
        self.macros = self.baked_in_macros.copy()
        self.modules_loaded = set()
        self._escape_parser = EscapeParser()
        self.tracing = False
        self.server_echo = False
        self.console_ns = {'realm': self}
        self.console = InteractiveConsole(self.console_ns)
        self._last_line_end = None
        self.wrapper = TextWrapper(width = 100, 
                                   drop_whitespace = False)

        self.protocols = []
        self._closing_down = False
        self.gmcp_handler = None
        self.gmcp_events=[]
        self.block_handlers=[]
        self.gmcp={}
        self.state={}
        self.module_settings_dir=''
        
        self.active_channels=['main']
        self.block=[]
        self.hide_lines=0
        self.last_line=None
        
        self.gui=None
        
        self.accessibility_mode = False
        self.event_handlers={}
        self.safe_to_send=True
    #Bidirectional, or just ambivalent, functions.
    
    def registerEventHandler(self, eventName, eventHandler):
        if not eventName in self.event_handlers:
            self.event_handlers[eventName]=[]
        self.event_handlers[eventName].append(eventHandler)
    
    
    def fireEvent(self, eventName, *args):
        if eventName in self.event_handlers:
            for eh in self.event_handlers[eventName]:
                self.factory.reactor.callLater(0, eh, *args)
                
    def get_state(self, item):
        if item in self.state:
            return self.state[item]
        else:
            return ''
        
    def set_state(self, item, value):
        self.state[item]=value
        
    def hide_next_lines(self,num_lines):
        self.hide_lines+=num_lines
        
    def clear_modules(self):
        """Restore our state to a pristine (ie, blank) condition.
        """
        #keep in place so references to these still work
        self.triggers[:] = []
        self.aliases[:] = []
        self.gmcp_events[:]=[]
        self.macros.clear()
        self.macros.update(self.baked_in_macros)
        self.modules_loaded = set()

    def reload_main_module(self):
        """Clear ourselves into a pristine state and load the main module
        again.
        """
        self.clear_modules()
        cls = load_file(self.factory.main_module_name)
        self.load_module(cls)

    def load_module(self, cls, _sort = True):
        """Load the triggers, aliases, macros and other modules of the given
        module.
        """
        if cls in self.modules_loaded:
            return
        #add now, so that we can avoid circular dependencies
        self.modules_loaded.add(cls)
        try:
            robmod = cls(self)
            for mod in robmod.modules:
                self.load_module(mod, _sort = False)
            if _sort:
                self.triggers.sort(key = attrgetter("sequence"))
                self.aliases.sort(key = attrgetter("sequence"))
                self.gmcp_events.sort(key = attrgetter("sequence"))
        except:
            self.modules_loaded.remove(cls)
            raise
        return robmod

    def close(self):
        """Close up our connection and shut up shop.
        
        It is guaranteed that, on registered connection event receivers,
        connection_lost will be called before close.
        """
        if not self._closing_down:
            #lose the connection first.
            self.telnet.close()
        else:
            #connection's already lost, we don't need to wait
            for prot in self.protocols:
                prot.close()
        self._closing_down = True

    def addProtocol(self, protocol):
        self.protocols.append(protocol)

    def connectionLost(self):
        """The link to the MUD died.

        It is guaranteed that this will be called before close on connection
        event receivers.
        """
        message = time.strftime("Connection closed at %H:%M:%S.")
        colour = HexFGCode(0xFF, 0xAA, 0x00) #lovely orange
        metaline = simpleml(message, colour, bg_code(BLACK))
        self.write(metaline)
        for prot in self.protocols:
            prot.connectionLost()
        #we might be waiting on the connection to die before we send out
        #close events
        if self._closing_down:
            for prot in self.protocols:
                prot.close()
        self._closing_down = True

    def connectionMade(self):
        """The MUD's been connected to."""
        message = time.strftime("Connection opened at %H:%M:%S.")
        colour = HexFGCode(0xFF, 0xAA, 0x00) #lovely orange
        metaline = simpleml(message, colour, bg_code(BLACK))
        self.write(metaline)
        for prot in self.protocols:
            prot.connectionMade()

    def trace_on(self):
        """Turn tracing (verbose printing to the output screen) on."""
        if not self.tracing:
            self.tracing = True
            self.trace("Tracing enabled!")

    def trace_off(self):
        """Turn tracing off."""
        if self.tracing:
            self.trace("Tracing disabled!")
            self.tracing = False

    def maybe_do_macro(self, chord):
        """Try and run a macro against the given keychord.

        A return value of True means a macro was found and run, False means
        no macro was found, or a macro returned True (meaning allow the GUI
        to continue handling the keypress).
        """
        if chord in self.macros:
            macro = self.macros[chord]
            allow_gui_continue = False
            try:
                allow_gui_continue = macro(self)
            except Exception:
                traceback.print_exc()
            return not allow_gui_continue
        else:
            return False

    #Going towards the screen

    def gmcpReceived(self, gmcp_pair):
        """Take GMCP data and do something with it"""
        for gmcp_event in self.gmcp_events:
            gmcp_event(gmcp_pair, self)

    def blockReceived(self, block):
        if len(block) > 0:
            realm = TriggerBlockMatchingRealm(block, parent = self, root = self,    
                                          send_line_to_mud = self.telnet.sendLine)
            realm.process()
     
    def setActiveChannels(self, channels):
        self.active_channels = channels       
            
    def metalineReceived(self, metaline):
        """Match a line against the triggers and perhaps display it on screen.
        """
        realm = TriggerMatchingRealm(metaline, parent = self,  root = self,
                                     send_line_to_mud = self.telnet.sendLine)
        realm.process()

    def cwrite(self, line, soft_line_start=False):
        ml=taggedml(line)
        self.write(ml, soft_line_start)
        
    def write(self, line, soft_line_start = False):
        if self.hide_lines>0:
            self.hide_lines-=1
            return
        
        """Write a line to the screen.
        
        This forcibly converts its argument to a Metaline.
        """
        if not isinstance(line, (basestring, Metaline)):
            line = str(line)
        if isinstance(line, basestring):
            metaline = simpleml(line, fg_code(WHITE, False), bg_code(BLACK))
            metaline.wrap = False
            metaline.soft_line_start = soft_line_start
        else:
            metaline = line
        #we don't need to close off the ends of the note, because thanks to
        #the magic of the ColourCodeParser, each new line is started by the
        #implied colour, so notes can't bleed out into text (though the 
        #reverse can be true).

        #this needs to be before the futzing with NLs and GA, because textwrap
        #obliterates all other newlines.
        metaline = metaline.wrapped(self.wrapper)

        #we don't actually append newlines at the end, but the start. This
        #simplifies things, because we don't use a newline where a soft line
        #end meets a soft line start, so there's only one place in this code
        #that can add newlines.
        if self._last_line_end is not None:
            if self._last_line_end == 'hard' or not metaline.soft_line_start:
                metaline.insert(0, '\n')
                
        for prot in self.protocols:
            prot.metalineReceived(metaline,self.active_channels)

        self._last_line_end = metaline.line_end

    def trace(self, line):
        """Write the argument to the screen if we are tracing, elsewise do
        nothing.
        """
        if self.tracing:
            self.write("TRACE: " + line)

    def trace_thunk(self, thunk):
        """If we're tracing, call the thunk and write its result to the
        outputs. If not, do nothing.
        """
        if self.tracing:
            self.write("TRACE: " + thunk())

    #Going towards the MUD.

    def receive_gui_line(self, string):
        """Send lines input into the GUI to the MUD.
        
        NOTE: this may have the power to execute arbitrary Python code. Thus,
        triggers and aliases should avoid using this, as they may be 
        vulnerable to injection from outside sources. Use send instead.
        """
        if string.startswith('/'):
            self.console.push(string[1:])
        else:
            for line in self._escape_parser.parse(string + '\n'):
                self.send(line)

    def safe_send(self, line, echo = True):
        if self.safe_to_send:
            self.send(line, echo)
            
            
    def send(self, line, echo = True):
        """Match aliases against the line and perhaps send it to the MUD."""
        echo = not self.server_echo and (echo and not self.accessibility_mode)
        realm = AliasMatchingRealm(line, echo, parent = self, root = self,
                                   send_line_to_mud = self.telnet.sendLine)
        realm.process()
    
    def set_timer(self, seconds, f, realm):
        return self.factory.reactor.callLater(seconds, f, realm)
    

