#!/usr/bin/python
"""Connand-line script to hook you up to the MUD of your choice."""
from pymudclient.net.telnet import TelnetClientFactory
from pymudclient.modules import load_file
from pymudclient import __version__
import argparse
from pymudclient.library.imperian.imperian_gui import ImperianGui

parser = argparse.ArgumentParser(version = "%(prog)s " + __version__, 
                                 prog = 'pymudclient')

known_guis = ['gtk']
gui_help = ("The GUI to use. Available options: %s. Default: %%(default)s" %
                     ', '.join(known_guis))

parser.add_argument('-g', '--gui', default = 'gtk', help = gui_help,
                    choices = known_guis)
parser.add_argument('-d','--directory', help="Module directory", dest='module_directory', default="",type=str)
parser.add_argument('-s','--settings', help='Settings directory', dest='settings_directory',default='',type=str)
parser.add_argument("modulename", help = "The module to import")
parser.add_argument("--profile", action = "store_true",  default = False,
                    help = "Whether to profile exection. Default: False")

def main():   
    """Launch the client.

    This is the main entry point. This will first initialise the GUI, then
    load the main module specified on the command line.
    """
    
    options = parser.parse_args()
    if options.module_directory != "":
        directory = options.module_directory
        import sys
        sys.path.append(directory)
    if options.gui == 'gtk':
        from twisted.internet import gtk2reactor
        gtk2reactor.install()
    
    from twisted.internet import reactor    
    modclass = load_file(options.modulename)
    factory = TelnetClientFactory(modclass.name, modclass.encoding, 
                                  options.modulename, reactor)

    if options.gui == 'gtk':
        from pymudclient.gui.gtkgui import configure
        factory.realm.gui = ImperianGui(factory.realm)

    configure(factory)
    factory.realm.module_settings_dir=options.settings_directory
    modinstance = factory.realm.load_module(modclass)
    factory.realm.gmcp_handler = modinstance.gmcp_handler
    

    modinstance.is_main(factory.realm)

    from twisted.internet import reactor

    #pylint kicks up a major fuss about these lines, but that's because 
    #Twisted does some hackery with the reactor namespace.
    #pylint: disable-msg=E1101

    reactor.connectTCP(modclass.host, modclass.port, factory)
    if not options.profile:
        reactor.run()
    else:
        import cProfile
        cProfile.runctx("reactor.run()", globals(), locals(),
                        filename = "pymudclient.prof")

if __name__ == '__main__':
    main()
