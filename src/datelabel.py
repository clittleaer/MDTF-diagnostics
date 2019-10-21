"""Classes and utility methods for dealing with dates as expressed in filenames 
and paths. Intended use case is, eg, determining if a file contains data for a
given year from the filename, without having to open it and parse the header.

Note:
    These classes should *not* be used for calendar math! We currently implement
    and test comparison logic only, not anything more (eg addition, subtraction).
"""
import re
import datetime

class Date(datetime.datetime):
    """Define a date with variable level precision.

    Note: 
        Date objects are mapped to datetimes representing the start of the 
        interval implied by their precision, eg. DateTime('2000-05') maps to 
        0:00 on 1 May 2000.
    """
    # define __new__, not __init__, because datetime is immutable
    def __new__(cls, *args, **kwargs):
        if len(args) == 2 and isinstance(args[0], datetime.datetime):
            # new obj from coercing a datetime. A bit hacky, but no other 
            # portable way to copy the input datetime using one of its class 
            # methods in py2.7.
            precision = args[1]
            args = (args[0].year, args[0].month, args[0].day, args[0].hour,
                args[0].minute, args[0].second, args[0].microsecond)
        else:
            if len(args) == 1 and type(args[0]) is str:
                args = cls._parse_input_string(args[0])
            precision = len(args)
            if precision == 1:
                args = (args[0], 1, 1) # missing month & day
            elif precision == 2:
                args = (args[0], args[1], 1) # missing day
        obj = super(Date, cls).__new__(cls, *args, **kwargs) 
        assert precision <= 6 # other values not supported
        obj.precision = precision
        return obj

    @classmethod
    def _parse_input_string(cls, s):
        """Parse date strings in `YYYY-MM-DD` or `YYYYMMDDHH` formats.
        """
        if '-' in s:
            return tuple([int(ss) for ss in s.split('-')])
        ans = [int(s[0:4])]
        for i in range(4, len(s), 2):
            ans.append(int(s[i:(i+2)]))
        return tuple(ans)

    _strftimes = ('', '%Y', '%Y%m', '%Y%m%d', '%Y%m%d%H', '%Y%m%d%H%M', '%Y%m%d%H%M%S')

    def format(self):
        """Print date in YYYYMMDDHH format, with length being set automatically
        from precision. 
        
        Other formats can be obtained manually with `strftime`, or by subclassing
        and changing the _strftimes tuple.
        """
        return self.strftime(self._strftimes[self.precision])
    __str__ = format
    
    def __repr__(self):
        return "Date('{}')".format(self)   

    def __lt__(self, other):
        """Overload datetime.datetime's __lt__. Coerce to datetime.date if we're
        comparing with a datetime.date.
        """
        if isinstance(other, datetime.datetime):
            return super(Date, self).__lt__(other)
        else:
            return (self.date() < other)

    def __le__(self, other):
        """Overload datetime.datetime's __le__. Coerce to datetime.date if we're
        comparing with a datetime.date.
        """
        if isinstance(other, datetime.datetime):
            return super(Date, self).__le__(other)
        else:
            return (self.date() <= other)

    def __gt__(self, other):
        """Overload datetime.datetime's __gt__. Coerce to datetime.date if we're
        comparing with a datetime.date.
        """
        if isinstance(other, datetime.datetime):
            return super(Date, self).__gt__(other)
        else:
            return (self.date() > other)

    def __ge__(self, other):
        """Overload datetime.datetime's __ge__. Coerce to datetime.date if we're
        comparing with a datetime.date.
        """
        if isinstance(other, datetime.datetime):
            return super(Date, self).__ge__(other)
        else:
            return (self.date() >= other)

    def __eq__(self, other):
        """Overload datetime.datetime's __eq__. Require precision to match as
        well as date, but *only up to stated precision*, eg Date(2019,5) will == 
        datetime.datetime(2019,05,18).
        """
        if isinstance(other, Date) and (self.precision != other.precision):
            return False
        if isinstance(other, datetime.datetime):
            # only compare most signifcant fields of tuple representation
            return (self.timetuple()[:self.precision] == other.timetuple()[:self.precision])
        else:
            return (self.date() == other)

    def __ne__(self, other):
        return (not self.__eq__(other)) # more foolproof

    def increment(self):
        """Return a copy of Date advanced by one time unit as specified by
        the `precision` attribute.
        """
        if self.precision == 2: # nb: can't handle this with timedeltas
            if self.month == 12:
                return Date(self.year + 1, 1)
            else:
                return Date(self.year, self.month + 1)
        else:
            return self._inc_dec_common(1)

    def _to_interval_end(self):
        """Return a copy of Date advanced by one time unit as specified by
        the `precision` attribute.
        """
        temp = self.increment()
        return Date(
            # Q: does this handle leap seconds correctly?
            temp.__add__(datetime.timedelta(milliseconds = -100)),
            self.precision
        )

    def decrement(self):
        """Return a copy of Date moved back by one time unit as specified by
        the `precision` attribute.
        """
        if self.precision == 2: # nb: can't handle this with timedeltas
            if self.month == 1:
                return Date(self.year - 1, 12)
            else:
                return Date(self.year, self.month - 1)
        else:
            return self._inc_dec_common(-1)

    def _inc_dec_common(self, delta):
        if self.precision == 1:
            return Date(self.year + delta) # nb: can't handle this with timedeltas
        elif self.precision == 3:
            td = datetime.timedelta(days = delta)
        elif self.precision == 4:
            td = datetime.timedelta(hours = delta)
        elif self.precision == 5:
            td = datetime.timedelta(minutes = delta)
        elif self.precision == 6:
            td = datetime.timedelta(seconds = delta)
        else:
            # prec == 2 case handled in calling logic
            raise ValueError("Malformed input")
        return Date(self.__add__(td), self.precision)


class DateRange(object):
    """Class representing a range of dates. 

    Note:
        This is defined as a *closed* interval (containing both endpoints). 
        Eg, DateRange('1990-1999') starts at 0:00 on 1 Jan 1990 and 
        ends at 23:59 on 31 Dec 1999.
    """
    def __init__(self, start, end=None):
        if type(start) is str and (end is None):
            (start, end) = self._parse_input_string(start)
        elif isinstance(start, (list, tuple, set)) and (end is None):
            (start, end) = self._parse_input_collection(start)

        if not isinstance(start, Date):
            start = Date(start)
        if not isinstance(end, Date):
            end = Date(end)
        if start.precision != end.precision:
            start.precision = min(start.precision, end.precision)
            end.precision = min(start.precision, end.precision)

        self.start = start
        self._cmp_end = end # version with same precision, for comparisons
        self.end = end._to_interval_end()
        assert self.start < self._cmp_end

    @classmethod
    def _parse_input_string(cls, s):
        s2 = s.split('-')
        assert len(s2) == 2
        return tuple([Date(ss) for ss in s2])

    @classmethod
    def _parse_input_collection(cls, coll):
        if all(isinstance(item, DateRange) for item in coll):
            # given a bunch of DateRanges, return interval containing them
            # ONLY IF ranges are continguous and nonoverlapping
            dt_ranges = sorted(coll, key=lambda dtr: dtr.start)
            for i in range(0, len(dt_ranges) - 1):
                if (dt_ranges[i]._cmp_end.increment() != dt_ranges[i+1].start) \
                    or (dt_ranges[i+1].start.decrement() != dt_ranges[i]._cmp_end):
                    raise ValueError("Date Ranges not contiguous and nonoverlapping.")
            return (dt_ranges[0].start, dt_ranges[-1]._cmp_end)
        elif all(isinstance(item, Date) for item in coll):
            # given a bunch of Dates, return interval containing them
            return (min(coll), max(coll))
        elif len(coll) == 2 and (type(coll) is not set):
            # assume two entries meant to be start and end
            return tuple([Date(item) for item in coll])
        else:
            raise ValueError("Malformed input")

    def format(self):
        return '{}-{}'.format(self.start, self.end)
    __str__ = format

    def __repr__(self):
        return "DateRange('{}')".format(self)

    def __eq__(self, other):
        return (self.start == other.start) and (self.end == other.end)

    def __ne__(self, other):
        return (not self.__eq__(other)) # more foolproof

    def __contains__(self, item): 
        return self.overlaps(item)
    def overlaps(self, item):
        """Comparison returning `True` if `item` has any overlap at all with the
        date range.

        This method overrides the `__contains__` method, so, e.g., 
        datetime.date('2019-09-18') in DateRange('2018-2019') will give
        `True`.
        """
        if isinstance(item, DateRange):
            return (self.start <= item.end) and (item.start <= self.end)
        else:
            return (self.start <= item) and (self.end >= item)

    def contains(self, item):
        """Comparison returning `True` if `item` is strictly contained within 
        the range.
        """
        if isinstance(item, DateRange):
            return (self.start <= item.start) and (self.end >= item.end)
        else:
            return (self.start <= item) and (self.end >= item)
    
    def intersection(self, item):
        if not self.overlaps(item):
            raise ValueError("{} and {} have empty intersection".format(self, item))
        return DateRange(max(self.start, item.start), min(self.end, item.end))

class DateFrequency(datetime.timedelta):
    """Class representing a date frequency or period.

    Note:
        Period lengths are *not* defined accurately, eg. a year is taken as
        365 days and a month is taken as 30 days. 
    """
    # define __new__, not __init__, because timedelta is immutable
    def __new__(cls, quantity, unit=None):
        if isinstance(quantity, str) and (unit is None):
            (quantity, unit, kwargs) = cls._parse_input_string(quantity)
        if (type(quantity) is not int) or not isinstance(unit, str):
            raise ValueError("Malformed input")
        else:
            (quantity, unit, kwargs) = cls._parse_quantity_unit(quantity, unit)
        obj = super(DateFrequency, cls).__new__(cls, **kwargs) 
        obj.quantity = quantity
        obj.unit = unit
        return obj

    @classmethod
    def _parse_quantity_unit(cls, quantity, s):
        if s in ['yearly', 'year', 'years', 'yr', 'y', 'annually', 'annual', 'ann']:
            unit = 'yr'
            kwargs = {'days': 365 * quantity}
        elif s in ['seasonally', 'seasonal', 'seasons', 'season', 'se']:      
            unit = 'season'
            kwargs = {'days': 91 * quantity}
        elif s in ['monthly', 'month', 'months', 'mon', 'mo']:      
            unit = 'mo'
            kwargs = {'days': 30 * quantity}
        elif s in ['weekly', 'weeks', 'week', 'wk', 'w']:
            unit = 'wk'
            kwargs = {'weeks': quantity}
        elif s in ['daily', 'day', 'days', 'dy', 'd', 'diurnal', 'diurnally']:
            unit = 'day'
            kwargs = {'days': quantity}
        elif s in ['hourly', 'hour', 'hours', 'hr', 'h']:
            unit = 'hr'
            kwargs = {'hours': quantity}
        elif s in ['minutes', 'minute', 'min']:
            unit = 'min'
            kwargs = {'minutes': quantity}
        else:
            raise ValueError("Malformed input {} {}".format(quantity, s))
        return (quantity, unit, kwargs)

    @classmethod    
    def _parse_input_string(cls, str_):
        match = re.match(
            r"(?P<quantity>\d+)[ _]*(?P<unit>[a-z]+)", 
            str_.lower()
        )
        try:
            if match:
                return cls._parse_quantity_unit(
                    int(match.group('quantity')),
                    match.group('unit')
                )
            else:
                return cls._parse_quantity_unit(1, str_.lower())
        except ValueError:
            raise ValueError("Malformed input {}".format(str_))

    def format(self):
        # conversion? only hr and yr used
        return "{}{}".format(self.quantity, self.unit)
    __str__ = format

    def format_local(self):
        if self.unit == 'hr':
            return self.format()
        else:
            assert self.quantity == 1
            _local_dict = {
                'mo': 'mon',
                'day': 'day',
            }
            return _local_dict[self.unit]

    def __repr__(self):
        return "{}('{}')".format(type(self).__name__, self)

    def __eq__(self, other):
        # Note: only want to match labels, don't want '24hr' == '1day'
        if isinstance(other, DateFrequency):
            return (self.quantity == other.quantity) and (self.unit == other.unit)
        else:
            return super(DateFrequency, self).__eq__(other)

    def __ne__(self, other):
        return (not self.__eq__(other)) # more foolproof
