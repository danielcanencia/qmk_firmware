# colemak_dh_dev

Colemak-DH with a symbol layer, an F-row layer, and a navigation layer, built
around how a programmer actually uses a 60% — no dedicated F-row, no arrow
keys, and a layer key on every thumb.

## Base layer

Unmodified ANSI Colemak-DH (SteveP's Mod-DH, Z-relocated ANSI variant):

```
 ESC  1   2   3   4   5   6   7   8   9   0   -   =   Bksp
 Tab  Q   W   F   P   B   J   L   U   Y   ;   [   ]   \
 Caps A   R   S   T   G   M   N   E   I   O   '   Ent
 LSh  X   C   D   V   Z   K   H   ,   .   /   RSh
 Ctl Alt  Gui           Space           Gui  Alt  Menu  Ctl
       └─────── _SYM ───────┘└──── Space ────┘└ _NAV _FN ┘
```

Two properties of Colemak are doing the work here. It leaves the whole QWERTY
bracket block `[ ] \`, the punctuation `, . /`, and `'` exactly where QWERTY
puts them, so the characters a programmer types constantly are never
displaced. And it pushes the alphabetic load onto the home row, which is where
a programmer's shortcuts already live, so a layer is never a stretch from
where the letters are.

The cost is that every letter moves and `;` leaves the home row for the top
row. Both are recoverable on the layers.

**The one deliberate deviation from stock Colemak-DH is the top-left key:**
`Esc` instead of `` ` ``. Esc is a modal key that gets pressed constantly in an
editor or a REPL, and the backtick is available on _SYM. Swap them back by
editing `KC_ESC` / `KC_GRV` in `keymap.c`.

## Layers

Every thumb key is a **tap-hold** (`LT`), so no modifier is permanently
consumed and no key is given up to a layer outright. Tap is the modifier, hold
is the layer. The board's `PERMISSIVE_HOLD` is on, so a layer resolves as soon
as you type a key on it.

| Layer | Key | Contents |
|---|---|---|
| _SYM | <kbd>Ctrl</kbd> (left thumb) | Both shifted number rows: every symbol reachable without Shift |
| _FN | <kbd>Alt</kbd> (right thumb) | F1–F12, media keys |
| _NAV | <kbd>Gui</kbd> (right thumb) | Arrows, Home/End, word motion, clipboard |

### _SYM

Rows 0 and 1 become the two shifted number rows. The punctuation on row 1 is
mirrored one-for-one underneath row 0, so the two are easy to learn as a pair
rather than as 24 arbitrary keys.

```
 `   !   @   #   $   %   ^   &   *   (   )   _   +   Bksp
 Tab {   }   [   ]   <   >   \   |   ;   :   "   ?   =
 Caps A   R   S   T   G   M   N   E   I   O   '   Ent
 LSh  ,   .   /   ~   .   .   .   .   .   .   .   RSh
```

`,` `.` `/` are repeated under the left hand. They sit on the right hand in
Colemak, and this way a right-hand Ctrl/Alt/Shift can be held while the left
hand types them.

Rows 2 and 3 keep their letters, so the layer survives being held mid-word: hit
a symbol and carry on typing without releasing.

### _FN

F1–F12 on the number row, which is where the muscle memory already reaches for
them, and the media keys on the home row. Rows 2 and 3 pass through, so you can
type while the layer is held. <kbd>Del</kbd> sits where Backspace does.

### _NAV

The inverted T a 60% user expects — <kbd>PgUp</kbd> <kbd>Up</kbd>
<kbd>PgDn</kbd> over <kbd>Left</kbd> <kbd>Down</kbd> <kbd>Right</kbd> — placed
on the right-hand keys of the home and top rows, where those fingers already
rest. <kbd>Home</kbd> and <kbd>End</kbd> go under the left hand, since nothing
next to the arrows needs them.

The bottom row pairs each key with its Ctrl variant, because those are the
chords a programmer reaches for and they are otherwise awkward on a 60%:
Ctrl+Left/Right is word motion on Windows and Linux, and Ctrl+Home/End is
document start/end. The clipboard cluster (cut, copy, paste, undo, redo) is
under the left hand on the same row.

## Tuning

The default 200 ms tapping term is used. If the tap-hold thumbs feel slow to
switch or fire modifiers early, `TAPPING_TERM` in
[`../../rev1/config.h`](../../rev1/config.h) is the knob — 180 is the usual
starting point for a layout this tap-hold-heavy. Raise `PERMISSIVE_HOLD` to
`#define PERMISSIVE_HOLD_PER_KEY` if a specific key misbehaves.

## Layer order

`_BASE`, `_SYM`, `_FN`, `_NAV` are 0, 1, 2, 3 in that order, defined once in
[`../../rev1/config.h`](../../rev1/config.h) rather than in this keymap, so
that future keymaps on this board share the numbering.
