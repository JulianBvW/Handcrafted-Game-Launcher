'''Playtime and dates as the interface shows them.

Through gettext rather than the C locale: strftime('%b') would follow
whatever LC_TIME happens to be, independent of the language the interface
was set to. Month names and the date pattern are translatable texts of
their own instead. Untranslated, everything is English.

Timestamps are Unix seconds, as library.py stores them. Days are counted
in local calendar days, not in blocks of 24 hours: something played at
23:50 is "Yesterday" at 00:10.
'''

import time
from datetime import date

from .i18n import _, ngettext


def _month(number):
    # Spelt out one by one so xgettext can find every name.
    return (_('Jan'), _('Feb'), _('Mar'), _('Apr'), _('May'), _('Jun'),
            _('Jul'), _('Aug'), _('Sep'), _('Oct'), _('Nov'),
            _('Dec'))[number - 1]


def playtime(seconds):
    '''`0h`, `45m`, `23h 40m`. Leftover seconds are dropped.'''
    minutes = max(0, int(seconds)) // 60
    hours, minutes = divmod(minutes, 60)
    if hours:
        return _('{hours}h {minutes}m').format(hours=hours, minutes=minutes)
    if minutes:
        return _('{minutes}m').format(minutes=minutes)
    return _('0h')


def last_played(timestamp, now=None):
    '''`Never`, `Today`, `Yesterday`, `3 days ago`, ... `2 years ago`.

    A timestamp in the future -- a clock that was set back -- counts as
    today rather than producing "-1 days ago".
    '''
    if timestamp is None:
        return _('Never')
    now = time.time() if now is None else now
    days = (date.fromtimestamp(now) - date.fromtimestamp(timestamp)).days

    if days <= 0:
        return _('Today')
    if days == 1:
        return _('Yesterday')
    if days < 7:
        return ngettext('{n} day ago', '{n} days ago', days).format(n=days)
    if days < 14:
        return _('Last week')
    if days < 30:
        weeks = days // 7
        return ngettext('{n} week ago', '{n} weeks ago',
                        weeks).format(n=weeks)
    if days < 60:
        return _('Last month')
    if days < 365:
        # Capped, so the five days before a year are not "12 months ago".
        months = min(days // 30, 11)
        return ngettext('{n} month ago', '{n} months ago',
                        months).format(n=months)
    if days < 730:
        return _('Last year')
    years = days // 365
    return ngettext('{n} year ago', '{n} years ago', years).format(n=years)


def added(timestamp):
    '''`5 Mar 2026`, without a leading zero.'''
    day = date.fromtimestamp(timestamp)
    return _('{day} {month} {year}').format(
        day=day.day, month=_month(day.month), year=day.year)
