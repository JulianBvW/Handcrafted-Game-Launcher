'''When scrolling moves the window between the hero and the library.

The rule (DESIGN §13): in the hero, any scroll down goes to the library.
In the library, a scroll up goes back to the hero -- but only once the
list under the pointer cannot go any further up. Scrolling down in the
library only ever scrolls the rail or the detail column.

Two things keep one movement of the hand from doing two things. After a
change of page, everything is swallowed for a while, and beyond that until
the movement ends, so the rest of it neither changes back nor scrolls the
new page. And a list that only reached its top during a movement does not
hand the rest of that movement on to the hero: going up takes a new
movement, after a pause. Otherwise a quick flick to the top of a long list
would overshoot into the hero.

Free of GTK, with the clock passed in, so every rule can be checked
without a display.
'''

LOCK = 0.9           # seconds after a change of page in which nothing counts
PAUSE = 0.25         # seconds without scrolling that end a movement
# How far a movement has to go, in the unit GTK reports it in. Wheel units
# are notches: a mouse wheel sends 1 per notch, a hi-res one quarters, and
# on X11 a touchpad sends fractions of a notch too. Surface units are
# pixels, from touchpads on Wayland.
WHEEL_STEP = 1.0
SURFACE_STEP = 40.0


class Pager:
    def __init__(self):
        self._locked_until = float('-inf')
        self._last = float('-inf')  # time of the last scroll event
        self._sum = 0.0             # how far this movement went, one way
        self._began_at_top = None   # the list was at its top all along
        self._changed = False       # this movement already changed the page

    def feed(self, dy, wheel, page, at_top, has_hero, now):
        '''One scroll event: `dy` > 0 is down, `wheel` whether it comes in
        notches rather than pixels, `page` 'hero' or 'library', `at_top` a
        function telling whether the list under the pointer is scrolled to
        its top (or there is none) -- asked only when it matters -- and
        `now` in seconds.

        Returns (page to change to or None, whether to swallow the event).
        An event not swallowed scrolls whatever is under the pointer.'''
        if now - self._last > PAUSE:
            # A new movement, even if it starts while still locked.
            self._sum = 0.0
            self._began_at_top = None  # not asked yet
            self._changed = False
        self._last = now
        if now < self._locked_until or self._changed:
            return None, True
        if not has_hero:
            return None, False

        step = WHEEL_STEP if wheel else SURFACE_STEP
        if page == 'hero':
            # Nothing on the hero scrolls, so nothing here is passed on.
            return self._towards('library', dy, step, now), True

        if dy >= 0:
            self._sum = 0.0
            return None, False
        top = at_top()
        if self._began_at_top is None:
            self._began_at_top = top
        if not top:
            self._began_at_top = False
            return None, False
        if not self._began_at_top:
            # Arrived at the top during this movement: the rest of it
            # stops here.
            return None, True
        return self._towards('hero', -dy, step, now), True

    def _towards(self, page, amount, step, now):
        if amount <= 0:
            self._sum = 0.0
            return None
        self._sum += amount
        if self._sum < step:
            return None
        self._sum = 0.0
        self._locked_until = now + LOCK
        self._changed = True
        return page
