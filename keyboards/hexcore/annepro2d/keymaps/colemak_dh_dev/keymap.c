// Copyright 2025 danielcanencia
// SPDX-License-Identifier: GPL-2.0-or-later

#include QMK_KEYBOARD_H

/*
 * Colemak-DH, tuned for programming.
 *
 * The base layer is unmodified ANSI Colemak-DH (SteveP's Mod-DH, Z-relocated
 * ANSI variant):
 *
 *     q w f p b | j l u y ;
 *     a r s t g | m n e i o
 *         x c d v z | k h , . /
 *
 * Two properties of Colemak matter here, and the layers below lean on both.
 * It leaves the entire QWERTY bracket block `[ ] \`, the punctuation `, . /`,
 * and `'` on their original keys, so nothing a programmer types constantly is
 * displaced. And it loads the alphabetic weight onto the home row, which is
 * where a programmer's shortcuts already live.
 *
 * What it costs: every letter moves, and `;` leaves the home row for the top
 * row. Both are handled below. The one deliberate deviation from stock
 * Colemak-DH is the top-left key, `Esc` instead of `` ` ``; the backtick is on
 * _SYM, and a programmer reaches for Esc far more often.
 *
 * Every thumb key is a tap-hold, so no modifier is permanently consumed and
 * no layer key is given up outright:
 *
 *     [4][0]  Ctrl / _SYM    [4][6]  Space
 *     [4][2]  Alt             [4][9]  Gui  / _NAV
 *     [4][3]  Gui             [4][10] Alt  / _FN
 *                            [4][11] Menu
 *                            [4][12] Ctrl
 *
 * _SYM  Rows 0 and 1 become the two shifted number rows: every symbol reached
 *       without Shift, and the punctuation mirrored one-to-one underneath them.
 *       `, . /` are repeated under the left hand, so a right-hand Ctrl/Alt/Shift
 *       can be held while the left hand types them. Rows 2 and 3 keep their
 *       letters, so the layer survives being held mid-word.
 * _FN   F1-F12 on the number row, where the muscle memory already goes, plus
 *       the media keys on the home row. Rows 2 and 3 pass through.
 * _NAV  The inverted T a 60% user expects (PgUp/Up/PgDn over Left/Down/Right),
 *       Home/End, word-wise motion, and the clipboard and undo cluster.
 */

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
    [_BASE] = LAYOUT_60_ansi(
        KC_ESC, KC_1, KC_2, KC_3, KC_4, KC_5, KC_6, KC_7, KC_8, KC_9, KC_0, KC_MINS, KC_EQL, KC_BSPC,
        KC_TAB, KC_Q, KC_W, KC_F, KC_P, KC_B, KC_J, KC_L, KC_U, KC_Y, KC_SCLN, KC_LBRC, KC_RBRC, KC_BSLS,
        KC_CAPS, KC_A, KC_R, KC_S, KC_T, KC_G, KC_M, KC_N, KC_E, KC_I, KC_O, KC_QUOT, KC_ENT,
        KC_LSFT, KC_X, KC_C, KC_D, KC_V, KC_Z, KC_K, KC_H, KC_COMM, KC_DOT, KC_SLSH, KC_RSFT,
        LT(_SYM, KC_LCTL), KC_LALT, KC_LGUI, KC_SPC, LT(_NAV, KC_RGUI), LT(_FN, KC_RALT), KC_APP, KC_RCTL
    ),

    [_SYM] = LAYOUT_60_ansi(
        KC_GRV, KC_EXLM, KC_AT, KC_HASH, KC_DLR, KC_PERC, KC_CIRC, KC_AMPR, KC_ASTR, KC_LPRN, KC_RPRN, KC_UNDS, KC_PLUS, KC_BSPC,
        KC_TAB, KC_LCBR, KC_RCBR, KC_LBRC, KC_RBRC, KC_LABK, KC_RABK, KC_BSLS, KC_PIPE, KC_SCLN, KC_COLN, KC_QUOT, KC_QUES, KC_EQL,
        KC_CAPS, KC_A, KC_R, KC_S, KC_T, KC_G, KC_M, KC_N, KC_E, KC_I, KC_O, KC_TRNS, KC_ENT,
        KC_LSFT, KC_COMM, KC_DOT, KC_SLSH, KC_TILD, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_RSFT,
        KC_TRNS, KC_TRNS, KC_TRNS, KC_SPC, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS
    ),

    [_FN] = LAYOUT_60_ansi(
        KC_ESC, KC_F1, KC_F2, KC_F3, KC_F4, KC_F5, KC_F6, KC_F7, KC_F8, KC_F9, KC_F10, KC_F11, KC_F12, KC_DEL,
        KC_TAB, KC_MUTE, KC_VOLU, KC_VOLD, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS,
        KC_CAPS, KC_A, KC_R, KC_S, KC_T, KC_G, KC_M, KC_N, KC_E, KC_I, KC_O, KC_QUOT, KC_ENT,
        KC_LSFT, KC_X, KC_C, KC_D, KC_V, KC_Z, KC_K, KC_H, KC_COMM, KC_DOT, KC_SLSH, KC_RSFT,
        KC_TRNS, KC_TRNS, KC_TRNS, KC_SPC, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS
    ),

    // Home/End sit under the left hand at the B/J positions; the inverted T is
    // right-hand only, so it stays on the Colemak home row where those fingers
    // already rest. Ctrl+Left/Right is word motion on Windows and Linux, and
    // Ctrl+Home/End is document start/end, which is why those four pair with
    // the plain keys above them.
    [_NAV] = LAYOUT_60_ansi(
        KC_ESC, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_DEL, KC_BSPC,
        KC_TAB, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_HOME, KC_END, KC_TRNS, KC_TRNS, KC_UP, KC_PGUP, KC_PGDN, KC_TRNS, KC_TRNS,
        KC_CAPS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS, KC_LEFT, KC_DOWN, KC_RIGHT, KC_TRNS, KC_ENT,
        KC_LSFT, KC_CUT, KC_COPY, KC_PASTE, KC_UNDO, C(KC_Y), KC_TRNS, C(KC_LEFT), C(KC_RIGHT), C(KC_HOME), C(KC_END), KC_RSFT,
        KC_TRNS, KC_TRNS, KC_TRNS, KC_SPC, KC_TRNS, KC_TRNS, KC_TRNS, KC_TRNS
    ),
};
