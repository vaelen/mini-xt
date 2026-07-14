# IRQ and I/O address map

Current as of the hardwired-IRQ rework (all on-board IRQs fixed; the only
remaining IRQ-related jumper anywhere is the PicoGUS DMA pair). Physical
IRQ lines are the 8 collected by the Bus MCU's single 74HCT165 (U12),
shifted out Q7-first: IRQ14, 8, 7, 6, 5, 4, 3, 2. Virtual IRQs exist only
inside the Bus MCU's AT-style soft PIC.

## IRQ map

| IRQ   | Type     | Mapped to                          | Notes                                                                          |
|-------|----------|------------------------------------|--------------------------------------------------------------------------------|
| IRQ0  | virtual  | PIT ch0 tick (emulated 8254)       | Bus MCU firmware                                                                 |
| IRQ1  | virtual  | Keyboard (emulated 8255/8042)      | Bus MCU firmware                                                                 |
| IRQ2  | physical | NE2000 NIC (0x340) — hardwired     | delivered as IRQ9 via AT redirect; fit addr_decode JP5 to tri-state it (sidecar) |
| IRQ3  | physical | COM2 (0x2F8) — hardwired           | free it by disabling COM2 (fit addr_decode JP2); sidecar can then drive it       |
| IRQ4  | physical | COM1 (0x3F8) — hardwired           | shared by the virtual COM3 mouse (use one or other); addr_decode JP1 frees it    |
| IRQ5  | physical | PicoGUS — hardwired                | sole driver; pgusinit sets the firmware to match                                 |
| IRQ6  | physical | Firmware floppy (virtual event)    | no physical FDC (design doc §10.1); the physical line stays free for the sidecar |
| IRQ7  | physical | LPT ~Ack (0x378) — hardwired       | tri-state, silent unless IRQ_EN set; fit addr_decode JP3 to free it              |
| IRQ8  | virtual  | RTC periodic/alarm — soft-PIC      | fired in Bus-MCU firmware; the physical ISA IRQ8 line is undriven/reserved       |
| IRQ12 | virtual  | PS/2 mouse option                  | Bus MCU firmware (default is the COM3 mouse on IRQ4)                             |
| IRQ14 | physical | XT-IDE INTRQ — hardwired           | motherboard-internal; poll vs interrupt = XTIDE UB config, wired either way      |

IRQ9–13 and IRQ15 do not exist on the board: nothing on the motherboard or
the 8-bit 60-pin header can drive them. A second cascaded '165 restores
them if a 16-bit source ever appears.

## I/O address map

| Address                   | Device                                       | Configuration                                                        |
|---------------------------|----------------------------------------------|------------------------------------------------------------------------|
| 0x00–0x0F + page regs     | 8237 DMA (functional)                        | Bus MCU emulated; PicoGUS jumpered to ch1 (the only serviced channel)   |
| 0x20/21, 0xA0/A1          | Dual 8259A PIC (AT-style)                    | Bus MCU emulated (soft PIC fed by the '165)                             |
| 0x40–0x43                 | 8254 PIT                                     | Bus MCU emulated; ch2 → speaker                                         |
| 0x60/0x61(/0x64)          | KBC — XT 8255 or AT 8042 mode                | Bus MCU emulated, software-selectable                                   |
| 0x70/0x71                 | RTC (Bus MCU-emulated) + NMI mask (bit 7)    | PCF8563 I2C RTC on the Supervisor backs the time; UART-synced at boot   |
| 0x80                      | POST display                                 | Bus MCU snoops → Supervisor's 2-digit hex                               |
| 0x220/0x240/0x330/0x388 … | PicoGUS personality (one at a time)          | SB/GUS/MPU-401/AdLib etc. via pgusinit; IRQ5, DMA1                      |
| 0x378                     | LPT                                          | base hardwired; addr_decode JP3 disable; IRQ7 hardwired                 |
| 0x2E8                     | (reserved) sidecar COM4                      | future; needs a freed COM/LPT IRQ (IRQ2 now taken by the NIC)           |
| 0x2F8                     | COM2 — 16C550                                | base hardwired; addr_decode JP2 disable; IRQ3 hardwired                 |
| 0x300                     | XT-IDE                                       | base hardwired; addr_decode JP4 disable; IRQ14 hardwired                |
| 0x340–0x35F               | NE2000 NIC (RTL8019AS)                       | hardwired; IRQ2→9; addr_decode JP5 disables (frees IRQ2, ignores I/O)   |
| 0x3F0–0x3F7               | (reserved) firmware floppy tier-2 registers  | Bus MCU emulated, only if register-level 765 emulation lands (§10.1)    |
| 0x3B4–3BF / 0x3D4–3DF     | Video MDA / CGA registers                    | VID_BASE strap picks; status 0x3BA/0x3DA scan-coherent                  |
| 0x3E8                     | COM3 — virtual serial mouse                  | Bus MCU emulated; IRQ4                                                  |
| 0x3F8                     | COM1 — 16C550                                | base hardwired; addr_decode JP1 disable; IRQ4 hardwired; console JP1    |

## Memory map

| Range           | Contents                                                       |
|-----------------|----------------------------------------------------------------|
| 0x00000–0x7FFFF | SRAM (IS62WV51216BLL, 1M×8 via byte-lane trick)                |
| 0x80000–0x9FFFF | SRAM (same chip; gated around the video hole)                  |
| 0xA0000–0xBFFFF | Video aperture (module PSRAM; CGA 0xB8000 / MDA 0xB0000 strap) |
| 0xC8000         | XTIDE Universal BIOS, shadow-loaded by the Bus MCU             |
