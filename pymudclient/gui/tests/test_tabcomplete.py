from pymudclient.gui.tabcomplete import Trie
from mock import Mock

class Test_Adding:

    def setUp(self):
        self.trie = Trie()
        self.words = []

    def test_add_word_adds_to_the_trie(self):
        self.trie.add_word('foo')
        assert self.trie._fetch('foo') == 'foo'

    def test_add_word_is_caseless(self):
        self.trie.add_word("FOO")
        assert self.trie._fetch('foo') == 'foo'

    def test_add_line_adds_all_words_in_line(self):
        self.trie.add_line('foo bar baz')
        assert self.trie._fetch('foo') == 'foo'
        assert self.trie._fetch('bar') == 'bar'
        assert self.trie._fetch('baz') == 'baz'

    def test_add_line_adds_words_in_the_order_they_appear(self):
        self.trie.add_line('bar, baz')
        assert self.trie._fetch('ba') == 'baz'

    def test_add_line_works_nicely_with_complete(self):
        self.trie.add_line(' foo bar ')
        line, ind = self.trie.complete('fo', 2)
        assert line == 'foo'
        assert ind == 3

    #XXX: test splitting

def test_add_line_only_adds_words_not_splitting_characters():
    trie = Trie()
    trie.add_word = Mock()
    trie.add_line('foo, bar  ')
    assert trie.add_word.call_args_list == [(('foo',), {}), 
                                            (('bar',), {})]

class Test_complete_and_keys:

    def setUp(self):
        self.sample = ['barbells', 'foobinate', 'bazaar', 'spam', 
                       'spamandeggs', 'baza']
        self.trie = Trie()
        for s in self.sample:
            self.trie.add_word(s)

    def test_simple_word_replace(self):
        line, ind = self.trie.complete('foo bar baz', 5)
        assert line == 'foo barbells baz'

    def test_simple_index_setting(self):
        line, ind = self.trie.complete('foo bar baz', 5)
        assert ind == 12 #the end of barbells

    def test_nothing_happen_on_space(self):
        line = 'foo bar'
        ind = 4
        assert self.trie.complete(line, ind) == (line, ind)

    def test_one_word_not_in_tabdict(self):
        line = 'qux'
        ind = 3
        res = self.trie.complete(line, ind)
        print res
        assert res == (line, ind)

    def test_word_and_longer_word_in_tabdict(self):
        line = 'spam'
        ind = 2
        res, ind = self.trie.complete(line, ind)
        assert res == 'spamandeggs'

    def test_longer_word_not_in_tabdict(self):
        line = 'Spamandeggs'
        ind = 2
        res, ind = self.trie.complete(line, ind)
        assert res == 'Spamandeggs'

    def test_preserves_user_capitalisation(self):
        line = 'foo Bar baz'
        ind = 5
        res, ind = self.trie.complete(line, ind)
        assert res == 'foo Barbells baz', res

    def test_cursor_on_very_first_character_no_op(self):
        line = 'foo'
        ind = 0
        res, ind = self.trie.complete(line, ind)
        assert res == 'foo'
        assert ind == 0

    def test_on_long_but_unextendable_word(self):
        line = 'bazaar'
        ind = 3
        res, ind = self.trie.complete(line, ind)
        assert line == 'bazaar'
        assert ind == 6, ind

    def test_longer_word_also_in_tabdict(self):
        line = 'baza'
        ind = 3
        res, ind = self.trie.complete(line, ind)
        assert res == 'bazaar', res
        assert ind == 6

    def test_extend_special_case(self):
        line = 'baz'
        ind = 3
        res, ind = self.trie.complete(line, ind)
        assert res == 'baza', res
        assert ind == 4

    def test_does_right_thing_with_ordering(self):
        self.trie.add_word("frobble")
        self.trie.add_word("frobulate")
        self.trie.add_word("frobble")
        res, ind = self.trie.complete('frob', 4)
        assert res == 'frobble', res

    def test_retains_capitalisation(self):
        res, ind = self.trie.complete("FOoBI", 3)
        assert res == "FOoBInate"

    def test_makes_all_caps_if_all_caps_previously(self):
        res, ind = self.trie.complete("FOO", 2)
        assert res == "FOOBINATE"

    def test_doesnt_make_all_caps_if_only_one_char(self):
        res, ind = self.trie.complete("F", 1)
        assert res == "Foobinate"


def test_retrieves_shorter_but_more_recent_word_without_extend():
    trie = Trie()
    trie.add_word("zeepf")
    trie.add_word("zee")
    res, ind = trie.complete("ze", 1)
    assert res == "zee", res

    #TODO: more edge cases.

