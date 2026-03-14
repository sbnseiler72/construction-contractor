/** @odoo-module **/

/**
 * Jalali Date Picker Field Widget for Odoo 19
 *
 * v5 — Fix: replaced the incorrect Borkowski algorithm with the correct
 * conversion algorithm (same one used inside jalalidatepicker internally).
 * Previous algorithm mapped 1404/12/21 -> 2025-11-20 instead of 2026-03-12.
 *
 * Architecture:
 *   - record holds:  Luxon DateTime (Gregorian, UTC midnight)
 *   - input shows:   Jalali string — pure getter from record, never stored in state
 *   - on pick/blur:  Jalali string -> Luxon DateTime -> record.update()
 */

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

// ---------------------------------------------------------------------------
// Luxon — accessed via window.luxon injected by Odoo's web bundle.
// Never import "luxon" directly; it is not an exposed module name in Odoo.
// ---------------------------------------------------------------------------
function getLuxonDT() {
    if (window.luxon && window.luxon.DateTime) return window.luxon.DateTime;
    throw new Error("[JalaliDateField] window.luxon.DateTime not found.");
}

// ---------------------------------------------------------------------------
// Gregorian <-> Jalali conversion
// This is the standard algorithm used by jalalidatepicker internally,
// verified correct: 1404/12/21 <-> 2026-03-12.
// ---------------------------------------------------------------------------

function pad2(n) { return String(n).padStart(2, "0"); }

/**
 * Gregorian (gy, gm, gd) -> Jalali {year, month, day}
 */
function gregorianToJalali(gy, gm, gd) {
    var g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    var j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];
    gy -= 1600; gm -= 1; gd -= 1;
    var g_d_no = 365 * gy
        + Math.floor((gy + 3) / 4)
        - Math.floor((gy + 99) / 100)
        + Math.floor((gy + 399) / 400);
    for (var i = 0; i < gm; ++i) g_d_no += g_days_in_month[i];
    if (gm > 1 && ((gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0)) g_d_no++;
    g_d_no += gd;
    var j_d_no = g_d_no - 79;
    var j_y = 979 + 33 * Math.floor(j_d_no / 12053);
    j_d_no %= 12053;
    j_y += 4 * Math.floor(j_d_no / 1461);
    j_d_no %= 1461;
    if (j_d_no >= 366) {
        j_y += Math.floor((j_d_no - 1) / 365);
        j_d_no = (j_d_no - 1) % 365;
    }
    var j_m, j_d;
    for (i = 0; i < 11 && j_d_no >= j_days_in_month[i]; ++i)
        j_d_no -= j_days_in_month[i];
    j_m = i + 1; j_d = j_d_no + 1;
    return { year: j_y, month: j_m, day: j_d };
}

/**
 * Jalali (jy, jm, jd) -> Gregorian {year, month, day}
 */
function jalaliToGregorian(jy, jm, jd) {
    jy -= 979; jm -= 1; jd -= 1;
    var j_d_no = 365 * jy
        + Math.floor(jy / 33) * 8
        + Math.floor((jy % 33 + 3) / 4);
    for (var i = 0; i < jm; ++i) j_d_no += (i < 6) ? 31 : 30;
    j_d_no += jd;
    var g_d_no = j_d_no + 79;
    var gy = 1600 + 400 * Math.floor(g_d_no / 146097);
    g_d_no %= 146097;
    var leap = true;
    if (g_d_no >= 36525) {
        g_d_no--;
        gy += 100 * Math.floor(g_d_no / 36524);
        g_d_no %= 36524;
        if (g_d_no >= 365) g_d_no++;
        else leap = false;
    }
    gy += 4 * Math.floor(g_d_no / 1461);
    g_d_no %= 1461;
    if (g_d_no >= 366) {
        leap = false;
        g_d_no--;
        gy += Math.floor(g_d_no / 365);
        g_d_no %= 365;
    }
    var g_days_in_month = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    var gm, gd;
    for (i = 0; g_d_no >= g_days_in_month[i]; i++) g_d_no -= g_days_in_month[i];
    gm = i + 1; gd = g_d_no + 1;
    return { year: gy, month: gm, day: gd };
}

// ---------------------------------------------------------------------------
// Value bridge between Odoo record and Jalali strings
// ---------------------------------------------------------------------------

function isLuxon(val) {
    return val !== null && typeof val === "object" && typeof val.toISODate === "function";
}

/**
 * Converts an Odoo record date value (Luxon DateTime | false) to
 * a Jalali display string "YYYY/MM/DD".
 *
 * Called as a PURE GETTER on every render — not stored in state.
 * This guarantees the displayed value is always in sync with the record,
 * even after save/refresh.
 *
 * @param {object|false|null} val  Luxon DateTime from record.data
 * @returns {string}  e.g. "1404/12/21"
 */
function luxonToJalali(val) {
    if (!val || !isLuxon(val)) return "";
    try {
        const iso = val.toISODate(); // always "YYYY-MM-DD" Gregorian
        const [y, m, d] = iso.split("-").map(Number);
        const j = gregorianToJalali(y, m, d);
        return `${j.year}/${pad2(j.month)}/${pad2(j.day)}`;
    } catch (e) {
        console.error("[JalaliDateField] luxonToJalali error:", e);
        return "";
    }
}

/**
 * Converts a Jalali display string "YYYY/MM/DD" to a Luxon DateTime (UTC midnight).
 *
 * Odoo's serializeDate() calls .toFormat() on the value passed to record.update(),
 * so it MUST be a Luxon DateTime object — passing a plain string crashes Odoo.
 *
 * @param {string} jalaliStr  e.g. "1404/12/21"
 * @returns {object|null}  Luxon DateTime or null on invalid input
 */
function jalaliStrToLuxon(jalaliStr) {
    if (!jalaliStr) return null;
    try {
        const parts = jalaliStr.replace(/-/g, "/").trim().split("/").map(Number);
        if (parts.length !== 3 || parts.some(isNaN)) return null;
        const [jy, jm, jd] = parts;
        if (jy < 1300 || jy > 1600 || jm < 1 || jm > 12 || jd < 1 || jd > 31) return null;
        const g = jalaliToGregorian(jy, jm, jd);
        return getLuxonDT().utc(g.year, g.month, g.day);
    } catch (e) {
        console.error("[JalaliDateField] jalaliStrToLuxon error:", e);
        return null;
    }
}

function gregorianISOToJalali(iso) {
    if (!iso) return "";
    try {
        const [y, m, d] = iso.split("-").map(Number);
        const j = gregorianToJalali(y, m, d);
        return `${j.year}/${pad2(j.month)}/${pad2(j.day)}`;
    } catch (e) { return ""; }
}

function isLibraryReady() {
    return window.jalaliDatepicker && typeof window.jalaliDatepicker.startWatch === "function";
}

// ---------------------------------------------------------------------------
// OWL Component
// ---------------------------------------------------------------------------

export class JalaliDateField extends Component {
    static template = "jalali_datepicker.JalaliDateField";

    static props = {
        ...standardFieldProps,
        placeholder: { type: String,  optional: true },
        minDate:     { type: String,  optional: true },
        maxDate:     { type: String,  optional: true },
        zIndex:     { type: String,  optional: true },
        highlightHolidays: { type: Boolean, optional: true },
    };

    static defaultProps = {
        placeholder: "YYYY/MM/DD",
        minDate: "",
        maxDate: "",
        zIndex: "1000",
        highlightHolidays: true,
    };

    static supportedTypes = ["date"];

    setup() {
        this.inputRef = useRef("jalali-input");

        // Only transient UI state — the displayed date is a pure getter, not state.
        this.state = useState({ isInvalid: false });

        onMounted(() => {
            if (!isLibraryReady()) {
                console.error(
                    "[JalaliDateField] jalalidatepicker.min.js not loaded. " +
                    "Ensure vendor files are in static/src/vendor/."
                );
                return;
            }
            this._initPicker();
        });

        onWillUnmount(() => this._destroyPicker());
    }

    // -------------------------------------------------------------------------
    // Pure computed getter — always derived from the record on every OWL render.
    // Never stored in state; eliminates all sync/refresh bugs.
    // -------------------------------------------------------------------------

    get jalaliDisplayValue() {
        return luxonToJalali(this.props.record.data[this.props.name]);
    }

    // -------------------------------------------------------------------------
    // Picker lifecycle
    // -------------------------------------------------------------------------

    _initPicker() {
        const el = this.inputRef.el;
        if (!el) return;

        el.setAttribute("data-jdp", "");
        el.setAttribute("data-jdp-only-date", "");

        if (this.props.minDate) {
            el.setAttribute("data-jdp-min-date", gregorianISOToJalali(this.props.minDate));
        }
        if (this.props.maxDate) {
            el.setAttribute("data-jdp-max-date", gregorianISOToJalali(this.props.maxDate));
        }

        window.jalaliDatepicker.startWatch({
            dayRendering: this.props.highlightHolidays
                ? (o) => ({ isHollyDay: o.month === 1 && o.day <= 4 })
                : undefined,
            zIndex: this.props.zIndex
        });

        el.addEventListener("change", this._onPickerChange);
    }

    _destroyPicker() {
        const el = this.inputRef.el;
        if (!el) return;
        el.removeEventListener("change", this._onPickerChange);
        el.removeAttribute("data-jdp");
        el.removeAttribute("data-jdp-only-date");
        el.removeAttribute("data-jdp-min-date");
        el.removeAttribute("data-jdp-max-date");
    }

    // -------------------------------------------------------------------------
    // Commit: Jalali string -> Luxon DateTime -> record.update()
    // -------------------------------------------------------------------------

    _commitValue(jalaliStr) {
        const luxonDate = jalaliStrToLuxon(jalaliStr);
        if (luxonDate) {
            this.state.isInvalid = false;
            this.props.record.update({ [this.props.name]: luxonDate });
        } else {
            this.state.isInvalid = true;
        }
    }

    // -------------------------------------------------------------------------
    // Event handlers
    // -------------------------------------------------------------------------

    _onPickerChange = (event) => {
        this._commitValue(event.target.value);
    };

    onInputBlur(event) {
        const jalaliStr = event.target.value.trim();
        if (!jalaliStr) {
            this.state.isInvalid = false;
            this.props.record.update({ [this.props.name]: false });
            return;
        }
        this._commitValue(jalaliStr);
        if (this.state.isInvalid) {
            // Restore the input DOM to the last valid record value
            if (this.inputRef.el) {
                this.inputRef.el.value = this.jalaliDisplayValue;
            }
            this.state.isInvalid = false;
        }
    }

    onClear() {
        this.state.isInvalid = false;
        this.props.record.update({ [this.props.name]: false });
    }

    // -------------------------------------------------------------------------
    // Template getters
    // -------------------------------------------------------------------------

    get isReadonly() { return this.props.readonly; }
    get hasValue()   { return !!this.props.record.data[this.props.name]; }

    get inputClasses() {
        return [
            "o_input",
            "o_field_jalali_date_input",
            this.state.isInvalid ? "o_field_invalid" : "",
        ].filter(Boolean).join(" ");
    }
}

// ---------------------------------------------------------------------------
// Field descriptor
// ---------------------------------------------------------------------------

export const jalaliDateField = {
    component: JalaliDateField,
    displayName: _t("Jalali Date"),
    supportedTypes: ["date"],
    extractProps: ({ attrs, options }) => ({
        placeholder: attrs.placeholder || "YYYY/MM/DD",
        zIndex: options.zIndex || "1000",
        minDate: (options && options.min_date) || "",
        maxDate: (options && options.max_date) || "",
        highlightHolidays: options && options.highlight_holidays !== undefined
            ? !!options.highlight_holidays
            : true,
    }),
};

registry.category("fields").add("jalali_date", jalaliDateField);
