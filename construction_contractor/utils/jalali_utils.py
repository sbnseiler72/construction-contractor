# -*- coding: utf-8 -*-


class JalaliUtils:
    """Jalali (Shamsi/Persian) ↔ Gregorian calendar conversions.

    These are pure-math, stateless utilities — no Odoo dependencies.
    The algorithms mirror those in jalali_datepicker/static/src/js/jalali_date_field.js
    so both layers always agree on conversion results.

    Usage::

        gy, gm, gd = JalaliUtils.jalali_to_gregorian(1404, 2, 25)
        jy, jm, jd = JalaliUtils.gregorian_to_jalali(2025, 5, 15)
    """

    # Year ranges used to detect calendar type from a filename-encoded date.
    # Jalali years are currently in the ~1300-1500 range (1404 ≈ 2025/2026 CE).
    JALALI_YEAR_MIN = 1300
    JALALI_YEAR_MAX = 1500
    GREGORIAN_YEAR_MIN = 1900
    GREGORIAN_YEAR_MAX = 2100

    @staticmethod
    def jalali_to_gregorian(jy, jm, jd):
        """Convert a Jalali date to a Gregorian ``(year, month, day)`` tuple.

        Raises ``ValueError`` for inputs that produce an invalid calendar date.
        """
        jy -= 979
        jm -= 1
        jd -= 1
        j_d_no = 365 * jy + (jy // 33) * 8 + (jy % 33 + 3) // 4
        for i in range(jm):
            j_d_no += 31 if i < 6 else 30
        j_d_no += jd
        g_d_no = j_d_no + 79
        gy = 1600 + 400 * (g_d_no // 146097)
        g_d_no %= 146097
        leap = True
        if g_d_no >= 36525:
            g_d_no -= 1
            gy += 100 * (g_d_no // 36524)
            g_d_no %= 36524
            if g_d_no >= 365:
                g_d_no += 1
            else:
                leap = False
        gy += 4 * (g_d_no // 1461)
        g_d_no %= 1461
        if g_d_no >= 366:
            leap = False
            g_d_no -= 1
            gy += g_d_no // 365
            g_d_no %= 365
        g_days_in_month = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        i = 0
        while i < 12 and g_d_no >= g_days_in_month[i]:
            g_d_no -= g_days_in_month[i]
            i += 1
        return gy, i + 1, g_d_no + 1

    @staticmethod
    def gregorian_to_jalali(gy, gm, gd):
        """Convert a Gregorian date to a Jalali ``(year, month, day)`` tuple."""
        g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
        gy -= 1600
        gm -= 1
        gd -= 1
        g_d_no = (
            365 * gy
            + (gy + 3) // 4
            - (gy + 99) // 100
            + (gy + 399) // 400
        )
        for i in range(gm):
            g_d_no += g_days_in_month[i]
        if gm > 1 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
            g_d_no += 1
        g_d_no += gd
        j_d_no = g_d_no - 79
        j_y = 979 + 33 * (j_d_no // 12053)
        j_d_no %= 12053
        j_y += 4 * (j_d_no // 1461)
        j_d_no %= 1461
        if j_d_no >= 366:
            j_y += (j_d_no - 1) // 365
            j_d_no = (j_d_no - 1) % 365
        i = 0
        while i < 11 and j_d_no >= j_days_in_month[i]:
            j_d_no -= j_days_in_month[i]
            i += 1
        return j_y, i + 1, j_d_no + 1
