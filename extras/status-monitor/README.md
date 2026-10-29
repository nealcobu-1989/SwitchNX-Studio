# SkyNX mode for Status Monitor Deux

A one-line strip at the top right for testing modpacks: game RAM now (and the pool's
total), the highest game RAM since the mode opened (with the time), the three game cores,
GPU, FPS, MB/s read from the SD, and optionally the SoC temperature (Y to choose). RAM turns yellow from 2700 MB
and red from 2780 MB (change both with Y in the overlay menu).

Install: copy `04.SkyNX.smd` to `sdmc:/config/status-monitor-deux/modes/`.
Open it from Status Monitor Deux like the other modes. FPS and SD reads need SaltyNX.
Peak resets when the mode is reopened, or by holding ZL + ZR + D-pad down.

Status Monitor Deux is by masagrator (GPL-2.0): https://github.com/masagrator/Status-Monitor-Deux
