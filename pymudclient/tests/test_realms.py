from pymudclient.realms import RootRealm
from pymudclient.colours import fg_code, bg_code, WHITE, BLACK, HexFGCode
from pymudclient.metaline import Metaline, RunLengthList, simpleml
from pymudclient.triggers import binding_trigger
from pymudclient.aliases import binding_alias
from pymudclient.net.telnet import TelnetClientFactory, TelnetClient
from mock import Mock
import time

class FooException(Exception):
    pass

class Bad:
    def __init__(self, c):
        raise FooException()

class Circular:
    def __init__(self, c):
        pass
Circular.modules = [Circular]

class FakeMatcher:
    def __init__(self, sequence):
        self.sequence = sequence
    def __eq__(self, other):
        return self.sequence == other.sequence

class WithTriggers:
    def __init__(self, c):
        c.triggers = map(FakeMatcher, [2, 1, 6, 3])
        c.aliases = map(FakeMatcher, [10, 4, 6, 9, 1, 2])
    modules = []

class TestModuleLoading:

    def setUp(self):
        self.c = RootRealm(None)

    def test_load_sorts_triggers_and_aliases(self):
        self.c.load_module(WithTriggers)
        assert self.c.triggers == map(FakeMatcher, [1, 2, 3, 6])
        assert self.c.aliases == map(FakeMatcher, [1, 2, 4, 6, 9, 10])

    def test_circular_requirements(self):
        self.c.load_module(Circular)
        assert self.c.modules_loaded == set([Circular])

    def test_removes_from_modules_loaded_on_error(self):
        try:
            self.c.load_module(Bad)
        except FooException:
            assert Bad not in self.c.modules_loaded
        else:
    	    assert False

#XXX: test clear_modules

class Test_write:

    def setUp(self):
        self.realm = RootRealm(Mock())
        self.realm.telnet = Mock()
        self.p = Mock()
        self.realm.addProtocol(self.p)
        self.noting_line = simpleml("foo", Mock(), Mock())
        
    def writer(self, match, realm):
        print 'writer called!'
        realm.write(self.noting_line)

    @property
    def lines_gotten(self):
        return [line for ((line,), kwargs) in 
                            self.p.metalineReceived.call_args_list]

    def test_from_not_a_string(self):
        self.realm.write(42)
        assert len(self.lines_gotten) == 1
        assert self.lines_gotten[0].line == '42'

    def test_from_string(self):
        self.realm.write('spam')
        assert len(self.lines_gotten) == 1
        assert self.lines_gotten[0].line == 'spam'

    def test_from_metaline(self):
        ml = Metaline('foo', None, None)
        self.realm.write(ml)
        assert self.lines_gotten == [ml]

    def test_no_colourbleed_fg(self):
        self.realm.write("eggs")
        cols = self.lines_gotten[0].fores.items()
        expected = [(0, fg_code(WHITE, False))]
        assert cols == expected, (cols, expected)

    def test_no_colourbleed_bg(self):
        self.realm.write("eggs")
        cols = self.lines_gotten[0].backs.items()
        assert cols ==  [(0, bg_code(BLACK))], cols

    def test_passes_on_wrap_default(self):
        self.realm.write("eggs")
        assert not self.lines_gotten[0].wrap

    def test_soft_line_start_default_is_off(self):
        self.realm.write("barbaz")
        assert not self.lines_gotten[0].soft_line_start

    def test_passes_on_soft_line_start(self):
        self.realm.write('foo', soft_line_start = True)
        assert self.lines_gotten[0].soft_line_start

    noting_trigger = binding_trigger('bar')(writer)
    noting_alias = binding_alias('bar')(writer)

    def test_write_writes_after_during_matching_triggers(self):
        self.realm.triggers.append(self.noting_trigger)
        inline = Metaline('bar', set(), set())
        self.realm.metalineReceived(inline)
        assert self.lines_gotten == [inline, self.noting_line], \
               self.lines_gotten

    def test_write_writes_after_during_alias_matching(self):
        self.realm.aliases.append(self.noting_alias)
        inline = Metaline('bar', RunLengthList([(0, fg_code(WHITE, False))]),
                          RunLengthList([(0, bg_code(BLACK))]),
                          soft_line_start = True)
        self.realm.send('bar')
        print self.lines_gotten
        print
        expected = [inline, self.noting_line]
        print expected
        assert self.lines_gotten == expected

    def tracer(self, match, realm):
        realm.trace("Foo")

    tracing_trigger = binding_trigger("baz")(tracer)
    tracing_alias = binding_alias("baz")(tracer)

    def test_trace_writes_after_during_matching_triggers(self):
        self.realm.tracing = True
        self.realm.triggers.append(self.tracing_trigger)
        inline = Metaline('baz', set(), set())
        self.realm.metalineReceived(inline)
        expected_lines = [simpleml("\nTRACE: %s matched!" % self.tracing_trigger,
                                   fg_code(WHITE, False), bg_code(BLACK)),
                          simpleml("\nTRACE: Foo", fg_code(WHITE, False),
                                   bg_code(BLACK))]
        print self.lines_gotten
        print
        expected = [inline] + expected_lines
        print expected
        assert self.lines_gotten == expected

    def test_trace_writes_after_during_alias_matching(self):
        self.realm.tracing = True
        self.realm.aliases.append(self.tracing_alias)
        inline = Metaline('baz', RunLengthList([(0, fg_code(WHITE, False))]),
                          RunLengthList([(0, bg_code(BLACK))]),
                          soft_line_start = True)
        self.realm.send('baz')
        expected_lines = [simpleml("\nTRACE: %s matched!" % self.tracing_alias,
                                   fg_code(WHITE, False), bg_code(BLACK)),
                          simpleml("\nTRACE: Foo", fg_code(WHITE, False),
                                   bg_code(BLACK))]
        print self.lines_gotten
        print
        expected = [inline] + expected_lines
        print expected
        assert self.lines_gotten == expected

class Test_metalineReceived:

    def setUp(self):
        self.realm = RootRealm(Mock())
        self.p = Mock()
        self.realm.addProtocol(self.p)
        self.realm.telnet = Mock()
        self.ml = simpleml('foo', sentinel.fores, sentinel.backs)
        self.ml2 = simpleml("bar", sentinel.fores, sentinel.backs)
        self.ml2_written = self.ml2.copy()
        self.ml2_written.insert(0, '\n')

    @property
    def lines_gotten(self):
        return [line for ((line,), kwargs) in 
                            self.p.metalineReceived.call_args_list]

    def test_sends_to_screen_normally(self):
        self.realm.metalineReceived(self.ml)
        assert self.lines_gotten == [self.ml]

    @binding_trigger("foo")
    def trigger_1(self, match, realm):
        realm.write(self.ml2)

    def test_write_writes_afterwards(self):
        self.realm.triggers.append(self.trigger_1)
        self.realm.metalineReceived(self.ml)
        assert self.lines_gotten == [self.ml, self.ml2_written]

    @binding_trigger("foo")
    def trigger_2(self, match, realm):
        realm.display_line = False

    def test_doesnt_display_if_asked_not_to(self):
        self.realm.triggers.append(self.trigger_2)
        self.realm.metalineReceived(self.ml)
        assert self.lines_gotten == []

    @binding_alias("spam")
    def bar_writing_alias(self, match, realm):
        realm.write("BAR BAR BAR")
        realm.send_to_mud = False
    
    @binding_trigger('foo')
    def spam_sending_trigger(self, match, realm):
        realm.send("spam")

    def test_aliases_inside_triggers_write_after_trigger_writes(self):
        self.realm.triggers.append(self.spam_sending_trigger)
        self.realm.aliases.append(self.bar_writing_alias)

        noteline = Metaline("\nBAR BAR BAR",
                            RunLengthList([(0, fg_code(WHITE, False))]),
                            RunLengthList([(0, bg_code(BLACK))]))

        self.realm.metalineReceived(self.ml)

        assert self.lines_gotten == [self.ml, noteline]

    #XXX: test trigger matching specifically instead of accidentally

class Test_send:

    def setUp(self):
        self.realm = RootRealm(Mock())
        self.p = Mock()
        self.realm.addProtocol(self.p)
        self.realm.telnet = Mock()

    @property
    def lines_gotten(self):
        return [line for ((line,), kwargs) in 
                            self.p.metalineReceived.call_args_list]

    def test_send_sends_to_the_mud(self):
        self.realm.send("bar")
        assert self.realm.telnet.sendLine.call_args_list == [(('bar',), {})]

    def test_send_echos_by_default(self):
        self.realm.send("bar")
        expected = Metaline('bar', 
                            RunLengthList([(0, fg_code(WHITE, False))]),
                            RunLengthList([(0, bg_code(BLACK))]),
                            soft_line_start = True)
        assert self.lines_gotten == [expected]

    def test_send_doesnt_echo_if_told_not_to(self):
        self.realm.send("bar", False)
        assert self.lines_gotten == []

    def test_send_uses_echoes_with_soft_line_start(self):
        self.realm.send("spam")
        expected = Metaline('spam', 
                            RunLengthList([(0, fg_code(WHITE, False))]),
                            RunLengthList([(0, bg_code(BLACK))]),
                            soft_line_start = True)
        assert self.lines_gotten == [expected]

    #TODO: (not tested yet)
    #  - test calling send in a trigger and echoing then
    #  - test recursive calls to send properly
    #  - actually test matching properly

    @binding_alias("bar")
    def our_alias_1(self, match, realm):
        print 'sending after!'
        realm.send_after("foo")

    def test_send_after_sends_afterwards(self):
        self.realm.aliases.append(self.our_alias_1)
        self.realm.send('bar')

        assert self.realm.telnet.sendLine.call_args_list == [(('bar',), {}), 
                                                             (('foo',), {})]

    def test_send_after_default_echoing_is_off(self):
        self.realm.aliases.append(self.our_alias_1)
        self.realm.send("bar")
        expected = [Metaline('bar', 
                             RunLengthList([(0, fg_code(WHITE, False))]),
                             RunLengthList([(0, bg_code(BLACK))]),
                             soft_line_start = True)]
        assert self.lines_gotten == expected

    @binding_alias('baz')
    def our_alias_2(self, match, realm):
        realm.send_after("eggs", echo = False)

    def test_send_after_doesnt_echo_if_asked_not_to(self):
        self.realm.aliases.append(self.our_alias_2)
        self.realm.send("baz")
        expected = [Metaline('baz', 
                             RunLengthList([(0, fg_code(WHITE, False))]),
                             RunLengthList([(0, bg_code(BLACK))]),
                             soft_line_start = True)]
        assert self.lines_gotten == expected

    @binding_alias("foo")
    def foo_alias_sends_bar(self, match, realm):
        print 'Foo alias going!'
        realm.send('bar', echo = True)

    @binding_alias("bar")
    def bar_alias_sends_baz(self, match, realm):
        print 'Bar alias going'
        realm.send('baz', echo = True)

    def test_sends_and_writes_in_a_consistent_order(self):
        self.realm.aliases.append(self.foo_alias_sends_bar)
        self.realm.aliases.append(self.bar_alias_sends_baz)
        self.realm.send("foo", echo = True)

        expect_write = [Metaline("baz",
                                 RunLengthList([(0, fg_code(WHITE, False))]),
                                 RunLengthList([(0, bg_code(BLACK))]),
                                 soft_line_start = True),
                        Metaline("\nbar",
                                 RunLengthList([(0, fg_code(WHITE, False))]),
                                 RunLengthList([(0, bg_code(BLACK))]),
                                 soft_line_start = True),
                        Metaline("\nfoo",
                                 RunLengthList([(0, fg_code(WHITE, False))]),
                                 RunLengthList([(0, bg_code(BLACK))]),
                                 soft_line_start = True)]
        expect_send = ['baz', 'bar', 'foo']
        sent = [line for ((line,), kwargs)
                in self.realm.telnet.sendLine.call_args_list]

        assert self.lines_gotten == expect_write
        assert sent == expect_send

    @binding_alias('spam')
    def noisy_alias(self, match, realm):
        realm.write("FOO FOO FOO")

    def test_writes_come_after_echoing(self):
        self.realm.aliases.append(self.noisy_alias)
        self.realm.send("spam")

        expecting = [Metaline("spam",
                              RunLengthList([(0, fg_code(WHITE, False))]),
                              RunLengthList([(0, bg_code(BLACK))]),
                              soft_line_start = True),
                     Metaline("\nFOO FOO FOO",
                              RunLengthList([(0, fg_code(WHITE, False))]),
                              RunLengthList([(0, bg_code(BLACK))]))]

        assert self.lines_gotten == expecting

    def test_server_echo_defaultly_False(self):
        assert not self.realm.server_echo

    def test_doesnt_echo_if_server_echo_is_True(self):
        self.realm.server_echo = True
        self.realm.send("Foo")
        assert self.lines_gotten == []

#XXX: not tested still - TriggerMatchingRealm
#also not tested: send() and default echoing in MatchingRealms

from pymudclient.gui.bindings import gui_macros

class TestOtherStuff:

    def setUp(self):
        self.realm = RootRealm(None)

    def test_gui_macros_are_defaultly_loaded(self):
        assert self.realm.macros == gui_macros

    def test_baked_in_macros_loaded_after_clear(self):
        self.realm.baked_in_macros['f'] = 'foo'
        self.realm.clear_modules()
        res = gui_macros.copy()
        res['f'] = 'foo'
        assert self.realm.macros == res

#XXX: test clear_modules

from pymudclient.gui.keychords import from_string
from mock import patch

class Test_maybe_do_macro:

    def setUp(self):
        self.realm = RootRealm(None)
        self.realm.macros[from_string('X')] = self.macro
        self.realm.macros[from_string('C-M-X')] = self.bad_macro
        self.realm.macros[from_string('Z')] = self.simulated_grumpy_user
        self.realm.macros[from_string('L')] = self.macro_returning_true
        self.macro_called_with = []

    def macro(self, realm):
        self.macro_called_with.append(realm)

    def macro_returning_true(self, realm):
        self.macro_called_with.append(realm)
        return True

    def bad_macro(self, realm):
        raise Exception

    def simulated_grumpy_user(self, realm):
        raise KeyboardInterrupt

    def test_returns_False_if_no_macro_found(self):
        res = self.realm.maybe_do_macro(from_string('Q'))
        assert not res

    def test_returns_True_if_a_macro_found(self):
        res = self.realm.maybe_do_macro(from_string('X'))
        assert res

    def test_calls_macro_with_itself(self):
        self.realm.maybe_do_macro(from_string('X'))
        assert len(self.macro_called_with) == 1
        assert self.macro_called_with[0] is self.realm

    def test_KeyboardInterrupt_is_not_caught(self):
        try:
            self.realm.maybe_do_macro(from_string('Z'))
        except KeyboardInterrupt:
            pass
        else:
            assert False

    @patch('pymudclient.realms', 'traceback')
    def test_Exception_is_caught(self, tb):
        self.realm.maybe_do_macro(from_string('C-M-X'))
        assert tb.print_exc.called

    @patch('pymudclient.realms', 'traceback')
    def test_bad_macros_still_return_True(self, tb):
        res = self.realm.maybe_do_macro(from_string('C-M-X'))
        assert res

    def test_macro_that_returns_True_tells_gui_to_keep_processing(self):
        res = self.realm.maybe_do_macro(from_string('L'))
        assert not res

class Test_addProtocol:

    def setUp(self):
        self.factory = TelnetClientFactory(None, 'ascii', None)
        self.realm = RootRealm(self.factory)
        self.realm.telnet = self.telnet = Mock(spec = TelnetClient)
        self.receiver = Mock()
        self.realm.addProtocol(self.receiver)

    def test_passes_on_connection_lost(self):
        self.realm.connectionLost()
        assert self.receiver.connectionLost.called

    @patch('pymudclient.realms', 'time')
    def test_connection_lost_writes_message(self, our_time):
        our_time.strftime.return_value = 'FOOBAR'
        self.realm.write = Mock()
        self.realm.connectionLost()
        assert self.realm.write.called
        ml = self.realm.write.call_args[0][0]
        assert ml.line == 'FOOBAR'
        assert ml.fores.items() == [(0, HexFGCode(0xFF, 0xAA, 0x00))]
        assert ml.backs.items() == [(0, bg_code(BLACK))]

    @patch('pymudclient.realms', 'time')
    def test_connection_made_writes_message(self, our_time):
        our_time.strftime.return_value = 'FOOBAR'
        self.realm.write = Mock()
        self.realm.connectionMade()
        assert self.realm.write.called
        ml = self.realm.write.call_args[0][0]
        assert ml.line == 'FOOBAR'
        assert ml.fores.items() == [(0, HexFGCode(0xFF, 0xAA, 0x00))]
        assert ml.backs.items() == [(0, bg_code(BLACK))]

    def test_passes_on_connection_made(self):
        self.realm.connectionMade()
        assert self.receiver.connectionMade.called

    def test_sends_connection_lost_and_close_in_right_order(self):
        self.realm.close()
        #simulate Twisted's 'throw-it-over-the-wall' anti-guarantee
        self.realm.connectionLost()
        calls = [mname for (mname, args, kws) in self.receiver.method_calls]
        #the metalineReceived is the closing note
        assert calls == ['metalineReceived', 'connectionLost', 'close'], calls

    def test_connection_lost_then_close_works(self):
        self.realm.connectionLost()
        self.realm.close()
        calls = [mname for (mname, args, kws) in self.receiver.method_calls]
        assert calls == ['metalineReceived', 'connectionLost', 'close'], calls

from pymudclient.modules import load_file

class DummyModule:

    triggers = []
    aliases = []
    macros = {}
    modules = []

    def __init__(self, realm):
        pass

from mock import sentinel

class Test_reload:

    def setUp(self):
        self.factory = TelnetClientFactory(None, None, sentinel.ModuleName)
        self.realm = RootRealm(self.factory)

    @patch('pymudclient.realms', 'load_file')
    def test_calls_load_file(self, our_load_file):
        our_load_file.return_value = DummyModule
        self.realm.reload_main_module()
        assert our_load_file.called

    @patch('pymudclient.realms', 'load_file')
    def test_calls_load_file_with_main_module_name(self, our_load_file):
        our_load_file.return_value = DummyModule
        self.realm.reload_main_module()
        assert our_load_file.call_args[0] == (sentinel.ModuleName,)

    @patch('pymudclient.realms', 'load_file')
    def test_clears_modules(self, our_load_file):
        our_load_file.return_value = DummyModule
        self.realm.clear_modules = Mock()
        self.realm.reload_main_module()
        assert self.realm.clear_modules.called

    @patch('pymudclient.realms', 'load_file')
    def test_calls_load_module(self, our_load_file):
        our_load_file.return_value = sentinel.Module
        self.realm.load_module = Mock()
        self.realm.reload_main_module()
        assert self.realm.load_module.called
        assert self.realm.load_module.call_args[0] == (sentinel.Module,)

class Test_trace:

    def setUp(self):
        self.factory = TelnetClientFactory(None, None, sentinel.ModuleName)
        self.realm = RootRealm(self.factory)
        self.realm.telnet = Mock()

    def test_trace_on_sets_tracing_to_True(self):
        self.realm.trace = Mock()
        self.realm.trace_on()
        assert self.realm.tracing

    def test_tracing_is_off_by_default(self):
        assert not self.realm.tracing

    def test_trace_off_sets_tracing_to_False(self):
        self.realm.tracing = True
        self.realm.trace = Mock()
        self.realm.trace_off()
        assert not self.realm.tracing

    def test_trace_on_writes_a_message(self):
        self.realm.trace = Mock()
        self.realm.trace_on()
        assert self.realm.trace.call_args_list == [(('Tracing enabled!',),
                                                    {})]

    def test_trace_on_writes_nothing_if_already_tracing(self):
        self.realm.tracing = True
        self.realm.trace = Mock()
        self.realm.trace_on()
        assert not self.realm.trace.called

    def test_trace_off_writes_a_message(self):
        self.realm.tracing = True
        self.realm.trace = Mock()
        self.realm.trace_off()
        assert self.realm.trace.call_args_list == [(('Tracing disabled!',),
                                                    {})]

    def test_trace_off_writes_nothing_if_not_already_tracing(self):
        self.realm.trace = Mock()
        self.realm.trace_off()
        assert not self.realm.trace.called

    def test_trace_delegates_to_write_if_tracing(self):
        self.realm.tracing = True
        self.realm.write = Mock()
        self.realm.trace("FOO BAR BAZ")
        print self.realm.write.call_args_list
        assert self.realm.write.call_args_list == [(("TRACE: FOO BAR BAZ",),
                                                    {})]

    def test_trace_writes_nothing_if_not_tracing(self):
        self.realm.write = Mock()
        self.realm.trace("FOO BAR BAZ")
        assert not self.realm.write.called

    @binding_trigger("Foo")
    def trace_twiddling_trigger(self, match, realm):
        realm.display_line = False
        self.realm.tracing = True
        realm.trace('Foo')
        self.realm.tracing = False
        realm.trace("Bar")

    def test_trace_remembers_tracing_when_attempted(self):
        self.realm.write = Mock()
        self.realm.triggers.append(self.trace_twiddling_trigger)
        self.realm.metalineReceived(simpleml("Foo", None, None))
        print self.realm.write.call_args_list
        assert self.realm.write.call_args_list == [(("TRACE: Foo", False),
                                                    {})]

    def test_trace_thunk_delegates_to_write_if_tracing(self):
        self.realm.tracing = True
        self.realm.write = Mock()
        self.realm.trace_thunk(lambda: "FOO BAR BAZ")
        print self.realm.write.call_args_list
        assert self.realm.write.call_args_list == [(("TRACE: FOO BAR BAZ",),
                                                    {})]

    def test_trace_thunk_writes_nothing_if_not_tracing(self):
        self.realm.write = Mock()
        self.realm.trace_thunk(lambda: "FOO BAR BAZ")
        assert not self.realm.write.called

    @binding_trigger("Foo")
    def trace_thunk_twiddling_trigger(self, match, realm):
        realm.display_line = False
        self.realm.tracing = True
        realm.trace_thunk(lambda: 'Foo')
        self.realm.tracing = False
        realm.trace_thunk(lambda: "Bar")

    def test_trace_thunk_remembers_tracing_when_attempted(self):
        self.realm.write = Mock()
        self.realm.triggers.append(self.trace_thunk_twiddling_trigger)
        self.realm.metalineReceived(simpleml("Foo", None, None))
        print self.realm.write.call_args_list
        assert self.realm.write.call_args_list == [(("TRACE: Foo", False),
                                                    {})]

class Test_write_wrapping:
    
    def setUp(self):
        self.realm = RootRealm(Mock())
        self.p = Mock()
        self.realm.addProtocol(self.p)

    def test_line_insertion_with_hard_line_end_no_sls(self):
        self.realm._last_line_end = 'hard'
        self.realm.write(simpleml("foo", sentinel.fore,
                                  sentinel.back))
        rcvd = [ml for ((ml,), _) in self.p.metalineReceived.call_args_list]
        assert rcvd == [simpleml("\nfoo", sentinel.fore, sentinel.back)]

    def test_line_insertion_with_hard_line_end_sls(self):
        self.realm._last_line_end = 'hard'
        ml = simpleml("foo", sentinel.fore, sentinel.back)
        ml.soft_line_start = True
        expected = ml.copy()
        expected.insert(0, '\n')
        self.realm.write(ml)
        rcvd = [ml for ((ml,), _) in self.p.metalineReceived.call_args_list]
        assert rcvd == [expected]

    def test_line_insertion_sle_no_sls(self):
        self.realm._last_line_end = 'soft'
        self.realm.write(simpleml("foo", sentinel.fore,
                                  sentinel.back))
        rcvd = [ml for ((ml,), _) in self.p.metalineReceived.call_args_list]
        assert rcvd == [simpleml("\nfoo", sentinel.fore, sentinel.back)]
        
    def test_line_no_insertion_sle_sls(self):
        self.realm._last_line_end = 'soft'
        ml = simpleml("foo", sentinel.fore, sentinel.back)
        ml.soft_line_start = True
        expected = ml.copy()
        self.realm.write(ml)
        rcvd = [ml for ((ml,), _) in self.p.metalineReceived.call_args_list]
        assert rcvd == [expected]

    def test_respects_no_line_end(self):
        self.realm._last_line_end = None
        ml = simpleml("foo", sentinel.fore, sentinel.back)
        expected = ml
        self.realm.write(ml)
        rcvd = [ml for ((ml,), _) in self.p.metalineReceived.call_args_list]
        assert rcvd == [expected], rcvd

    def test_last_line_end_setting(self):
        ml = simpleml("foo", sentinel.fore, sentinel.back)
        ml.line_end = sentinel.line_end
        self.realm.write(ml)
        assert self.realm._last_line_end == sentinel.line_end

    def test_last_line_end_is_defaultly_None(self):
        assert self.realm._last_line_end is None

    def test_with_wrap(self):
        ml = simpleml("bar", sentinel.fore1, sentinel.fore2)
        ml.wrapped = Mock()
        ml.wrapped.return_value = ml2 = simpleml("foo", sentinel.fore,
                                                 sentinel.back)
        self.realm.write(ml)
        assert ml.wrapped.called
        rcvd = [ml for ((ml,), _) in self.p.metalineReceived.call_args_list]
        assert rcvd == [ml2]
