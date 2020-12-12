
class STRIP:
    TRAILING = 't'
    LEADING = 'l'
    BOTH = 'lt'
    NONE = ''

class PREFIX:
    UMK = {'u':'µ', 'm': 'm', 'k': 'k'}
    MK = {'m': 'm', 'k': 'k'}
    M = {'m': 'm'}
    K = {'k': 'k'}

class FormatFloat(object):

    # digits        digits to display
    # precision     precision of value
    # prefix        prefix for format conversion (u=*1000000, m=*1000, #=*1, k=*0.001)
    def __init__(self, precision=3, digits=4, prefix=PREFIX.MK, strip=STRIP.TRAILING, spacer=''):
        self.set_display(digits, precision)
        self.prefix = prefix
        self.extra = {}
        self.strip = strip
        self.spacer = spacer

    def set_prefix(self, prefix):
        self.prefix = prefix

    def set_display(self, precision, digits):
        self.digits = digits
        self.prec = {'u': max(0, precision - 6), 'm': max(0, precision - 3), '#': precision, 'k': precision + 3}

    def set_digits(self, idx, val):
        self.extra[idx] = val

    def set_precision(self, idx, val):
        self.prec[idx] = val

    def __format(self, value, unit):
        idx = '#'
        if 'k' in self.prefix:
            if value>=1000.0:
                value *= 0.001
                idx = 'k'
        if 'u' in self.prefix:
            if value<.001:
                value *= 1000000
                idx = 'u'
        if 'm' in self.prefix:
            if value<1.0:
                value *= 1000
                idx = 'm'
        if idx in self.prefix:
            unit = '%s%s' % (self.prefix[idx], unit)

        val_len = len('%u' % value)
        if idx in self.extra:
            digits = self.extra[idx]
        else:
            digits = self.digits
        n = min(self.prec[idx], max(0, digits - val_len))
        return (('%%.%uf' % n) % (value), unit)

    def format(self, value, unit):
        value, unit = self.__format(value, unit)
        if STRIP.TRAILING in self.strip and value.find('.')!=-1:
            value = value.rstrip('0')
            if value.endswith('.'):
                value += '0'
        if STRIP.LEADING in self.strip and value.startswith('0.'):
            value = value[1:]
        return '%s%s%s' % (value, self.spacer, unit)

# f = FormatFloat()

# v = 1.23456789 / 1000000
# for i in range(0, 16):
#     print(f.format(v, 'W'))
#     v *= 10.0

# f.set_display(5, 4)
# f.set_prefix(FormatFloat.PREFIX_UMK)

# v = 1.23456789 / 1000000
# for i in range(0, 16):
#     print(f.format(v, 'W'))
#     v *= 10.0


# f = FormatFloat(4, 5, FormatFloat.PREFIX_MK)
# f.set_precision('m', 1)
# #f.set_digits('k', 5)

# print(f.prec)

# v = 1.23456789 / 100000
# for i in range(0, 16):
#     print(f.format(v, 'W'))
#     v *= 10.0


