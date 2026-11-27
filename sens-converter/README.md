# Sens Converter

Works out the sensitivity that keeps your horizontal mouse speed (cm/360) when you change DPI or `m_yaw`, and sets it and `m_yaw` in [Momentum Mod](https://momentum-mod.org/).

Example: 800 DPI at sensitivity 0.8 and `m_yaw 0.022` turns as far per inch as 1600 DPI at sensitivity 1.466667 and `m_yaw 0.006`.

- **Reference sens:** a DPI, `m_yaw` and sensitivity to keep the horizontal speed of (0.022 is the game's default `m_yaw`). It opens on the sens you play with now: Momentum's `sensitivity` and `m_yaw` from `config.cfg`, turned into the sensitivity at this row's DPI and `m_yaw`, with your mouse at the DPI in the bottom row. **Use the game's sens** fills it in that way again.
- **Your setup in Momentum:** your mouse's DPI, and the `m_yaw` and sensitivity Apply sets in the game. The sensitivity is worked out from the reference. Change this sensitivity and the one above follows. Both rows go DPI, `m_yaw`, sensitivity.
- The page shows the cm/360 as you type. **Apply** sets the bottom row's sensitivity and `m_yaw` in the game.
- Each box has a slider too. The two DPIs and the old `m_yaw` are kept for the next time the page opens; the new `m_yaw` opens on the game's `m_yaw`.

The formula is `new sens = old sens × old DPI × old m_yaw / (new DPI × new m_yaw)`.

Only the horizontal speed is kept. `m_pitch` stays as it is, so vertical aim gets faster or slower with the new DPI and sens.

## What Apply does

- **Game closed:** it rewrites the `sensitivity` and `m_yaw` lines of `momentum/cfg/config.cfg`. The game uses them from its next start. The first change keeps a copy as `config.cfg.bak-sens-converter`.
- **Game open, started through the kit with [Source Yaw](../sourceyaw/) installed:** it sends the values through the game's net console (Source Yaw's launch adds it), so they apply at once.
- **Game open any other way:** it changes nothing, because the game writes `config.cfg` back when it quits. The page gives the console line to type instead (click it to copy).

The hub can't set your mouse's DPI. Set it in your mouse's own software, and in Momentum's mouse settings so the game's cm/360 (and Strafe Review's) reads right.

## Install

Install [Soulmanyes's Movement Kit](../README.md#install) (Windows or Linux) and click **Install** on the Sens Converter card of its Modules page. It shows up as the Sens Converter section.

### Licence

CC0 1.0 (see `LICENSE`).
