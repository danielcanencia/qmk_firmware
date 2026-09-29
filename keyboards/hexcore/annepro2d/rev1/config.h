/*
 * Copyright 2025 danielcanencia
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#pragma once

#include "pin_defs.h"

/*
 * The stock firmware has permissive-hold-like handling enabled; matching it
 * keeps typing behaviour familiar when moving from the vendor build.
 */
#define PERMISSIVE_HOLD

/* Layers, used by the keymaps in keymaps/. */
#define _BASE 0
#define _SYM 1  // right thumb: shifted symbols and the punctuation Mod-DH displaces
#define _FN 2   // right thumb: F-row, media keys, Delete
#define _NAV 3  // left thumb: arrows, Home/End, Page Up/Down
