# GivEnergy single-phase Gen 3 hybrid • simulator register note

The simulator serves a 60-word snapshot starting at zero using standard Modbus TCP, input-register function 04, unit 17 (0x11). Each word is big-endian. Addresses below are zero-based offsets. Read-only demo port 1502.

| JSON field | Input register | Raw to engineering units |
|---|---|---|
| pv_power_w | 18 and 20 | Add two unsigned string powers, 1 W per count |
| load_power_w | 42 | Unsigned, 1 W per count |
| grid_power_w | 30 | Negate signed int16, 1 W per count, positive import |
| battery_power_w | 52 | Negate signed int16, 1 W per count, positive charge |
| battery_soc_pct | 59 | Unsigned, 1 percent per count |

Address reference: https://jak.github.io/givenergy-modbus/register-map.html . GivEnergy uses proprietary framing on physical LAN adapters. This implementation reproduces the register meanings over standard Modbus TCP for simulator-first testing. A real adapter requires a compatible transport and model/firmware verification.
