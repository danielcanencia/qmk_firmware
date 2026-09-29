/*
    Copyright (C) 2020 Yaotian Feng, Codetector<codetector@codetector.cn>

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
*/

#pragma once

/*
 * Hexcore ANNE PRO 2D board definition.
 *
 * The MCU is a Holtek HT32F52352 (Cortex-M0+, 128 KiB flash, 16 KiB SRAM), the
 * same part family used by the Obins Anne Pro 2. The stock firmware links the
 * application at 0x4000, so the vendor bootloader owns the first 16 KiB.
 */

#define BOARD_NAME "Hexcore ANNE PRO 2D"

#define HT32F52352

/* 128 KiB flash minus the 16 KiB vendor bootloader. */
#define FLASH_SIZE (0x20000 - 0x4000)

#if !defined(_FROM_ASM_)
#ifdef __cplusplus
extern "C" {
#endif
void boardInit(void);
#ifdef __cplusplus
}
#endif
#endif /* _FROM_ASM_ */
