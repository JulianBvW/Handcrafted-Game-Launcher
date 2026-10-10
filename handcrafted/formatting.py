'''Playtime and dates as the interface shows them.

English and independent of the locale. strftime('%b') would say "Mär" on a
German system, so the month names are spelt out here.

Timestamps are Unix seconds, as library.py stores them. Days are counted
in local calendar days, not in blocks of 24 hours: something played at
23:50 is "Yesterday" at 00:10.
'''

import time
from datetime import date

MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def playtime(seconds):
    '''`0h`, `45m`, `23h 40m`. Leftover seconds are dropped.'''
    minutes = max(0, int(seconds)) // 60
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f'{hours}h {minutes}m'
    if minutes:
        return f'{minutes}m'
    return '0h'


def last_played(timestamp, now=None):
    '''`Never`, `Today`, `Yesterday`, `3 days ago`, ... `2 years ago`.

    A timestamp in the future -- a clock that was set back -- counts as
    today rather than producing "-1 days ago".
    '''
    if timestamp is None:
        return 'Never'
    now = time.time() if now is None else now
    days = (date.fromtimestamp(now) - date.fromtimestamp(timestamp)).days

    if days <= 0:
        return 'Today'
    if days == 1:
        return 'Yesterday'
    if days < 7:
        return f'{days} days ago'
    if days < 14:
        return 'Last week'
    if days < 30:
        return f'{days // 7} weeks ago'
    if days < 60:
        return 'Last month'
    if days < 365:
        # Capped, so the five days before a year are not "12 months ago".
        return f'{min(days // 30, 11)} months ago'
    if days < 730:
        return 'Last year'
    return f'{days // 365} years ago'


def added(timestamp):
    '''`5 Mar 2026`, without a leading zero.'''
    day = date.fromtimestamp(timestamp)
    return f'{day.day} {MONTHS[day.month - 1]} {day.year}'
