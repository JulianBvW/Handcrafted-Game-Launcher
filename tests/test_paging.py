'''When scrolling moves between hero and library, on a clock of our own.

    /usr/bin/python3 tests/test_paging.py
'''

from harness import check, report, sandbox, section

from handcrafted.paging import LOCK, PAUSE, Pager

folder = sandbox()


class Hand:
    '''Scrolls a Pager, with time moving only when told to.'''

    def __init__(self, page='hero', has_hero=True):
        self.pager = Pager()
        self.page = page
        self.has_hero = has_hero
        self.now = 1000.0

    def scroll(self, dy, wheel=True, at_top=True, after=0.02):
        self.now += after
        self.asked = False

        def top():
            self.asked = True
            return at_top
        target, swallowed = self.pager.feed(dy, wheel, self.page, top,
                                            self.has_hero, self.now)
        if target is not None:
            self.page = target
        return target, swallowed

    def rest(self):
        self.now += PAUSE + 0.05


section('From the hero')

hand = Hand()
check('one notch down goes to the library',
      hand.scroll(1.0) == ('library', True))
hand = Hand()
check('a quarter notch does not', hand.scroll(0.25) == (None, True))
for _ in range(3):
    result = hand.scroll(0.25)
check('four of them do', result == ('library', True), result)
hand = Hand()
check('39 px of touchpad do not',
      hand.scroll(39, wheel=False) == (None, True))
check('the 40th does', hand.scroll(1, wheel=False) == ('library', True))
hand = Hand()
check('up does nothing, and is not passed on',
      hand.scroll(-3.0) == (None, True))
hand = Hand()
hand.scroll(0.5)
hand.rest()
check('half a notch, a pause, half a notch: two small movements, '
      'not one', hand.scroll(0.5) == (None, True))

section('The lock')

hand = Hand()
hand.scroll(1.0)
check('right after the change, scrolling up is swallowed',
      hand.scroll(-5.0, after=0.1) == (None, True) and hand.page == 'library')
check('and down too, rather than scrolling the new page',
      hand.scroll(2.0, at_top=False, after=0.1) == (None, True))
hand.now += LOCK
hand.rest()
check('once it is over, down scrolls the list',
      hand.scroll(1.0, at_top=False) == (None, False))

hand = Hand()
hand.scroll(1.0)
for _ in range(60):  # 1.2 s of swiping on, without a pause
    result = hand.scroll(1.0, at_top=False)
check('a swipe that goes on past the lock still scrolls nothing',
      result == (None, True), result)
check('nor does turning round in it lead back',
      hand.scroll(-1.0) == (None, True) and hand.page == 'library')
hand.rest()
check('only a new movement does', hand.scroll(-1.0) == ('hero', True))

hand = Hand()
hand.scroll(1.0)
hand.rest()
# A new movement, begun while still locked, going on past the lock.
for _ in range(15):
    hand.scroll(-1.0, at_top=False, after=0.05)
check('a movement begun in the lock counts as its own once it is over',
      hand.scroll(-1.0, at_top=False, after=0.05) == (None, False))
check('so reaching the top on its way stops it there',
      hand.scroll(-1.0, at_top=True, after=0.05) == (None, True)
      and hand.page == 'library')

section('From the library')

hand = Hand('library')
check('down never changes the page',
      hand.scroll(5.0) == (None, False) and hand.page == 'library')
check('nor asks whether the list is at its top', not hand.asked)
hand.rest()
check('up, with the list not at its top, scrolls the list',
      hand.scroll(-1.0, at_top=False) == (None, False))
hand.rest()
check('up, with the list at its top all along, goes to the hero',
      hand.scroll(-1.0) == ('hero', True))

hand = Hand('library')
hand.scroll(-1.0, at_top=False)
hand.scroll(-1.0, at_top=False)
check('up, reaching the top during the movement, stops there',
      hand.scroll(-1.0) == (None, True) and hand.page == 'library')
check('however long the movement goes on',
      all(hand.scroll(-1.0) == (None, True) for _ in range(20)))
hand.rest()
check('a new movement after a pause goes to the hero',
      hand.scroll(-1.0) == ('hero', True))

hand = Hand('library')
check('a touchpad needs its 40 px going up as well',
      hand.scroll(-20, wheel=False) == (None, True))
check('and then goes', hand.scroll(-20, wheel=False) == ('hero', True))

section('Without a hero')

hand = Hand('library', has_hero=False)
check('up at the top goes nowhere, and is passed on',
      hand.scroll(-3.0) == (None, False) and hand.page == 'library')

report(folder)
