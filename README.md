# Sprocket Generator — Fusion 360 Add-in

A Fusion 360 add-in that generates accurate roller-chain sprockets based on the **ANSI B29.1 / JIS B1801** three-arc tooth profile standard.

## Features

- Correct three-arc tooth form: seating arc → profile arc → tip arc
- 17 chain series supported (motorcycle and industrial)
- Generates a fully parametric, solid body in its own component
- Writes key dimensions to Fusion user parameters (`Spr_*`)
- Persistent toolbar button under **Solid → Create**, next to Spur Gear

## Supported Chain Series

| Code | Pitch (mm) | Roller (mm) | Notes |
|------|-----------|-------------|-------|
| 415  | 12.700 | 7.770 | JIS light-duty motorcycle |
| 420  | 12.700 | 7.750 | Motorcycle / mini-bike / ATV |
| 420H | 12.700 | 7.750 | Heavy-duty variant |
| 428  | 12.700 | 8.510 | Motorcycle 125–250 cc |
| 428H | 12.700 | 8.510 | Heavy-duty variant |
| 520  | 15.875 | 10.160 | Motorcycle 250–400 cc |
| 520H | 15.875 | 10.160 | Heavy-duty variant |
| 525  | 15.875 | 10.160 | Motorcycle 400–750 cc |
| 525H | 15.875 | 10.160 | Heavy-duty variant |
| 530  | 15.875 | 10.160 | Motorcycle 600 cc+ |
| 530H | 15.875 | 10.160 | Heavy-duty variant |
| 25   | 6.350  | 3.300  | ANSI #25 industrial |
| 35   | 9.525  | 5.080  | ANSI #35 industrial |
| 40   | 12.700 | 7.920  | ANSI #40 industrial |
| 41   | 12.700 | 7.770  | ANSI #41 lightweight |
| 50   | 15.875 | 10.160 | ANSI #50 industrial |
| 60   | 19.050 | 11.910 | ANSI #60 industrial |

## Installation

1. Clone or copy this folder into your Fusion 360 add-ins directory:
   - **Windows:** `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`
   - **macOS:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
2. In Fusion 360, open **Tools → Scripts and Add-Ins** (or press `Shift+S`)
3. Switch to the **Add-Ins** tab, find **SprocketGenerator**, and click **Run**
4. To load automatically on startup, enable **Run on Startup**

## Usage

1. Open (or create) a Fusion 360 Design
2. Click **Sprocket Generator** in the **Solid → Create** panel
3. Set **Tooth Count** (6–99) and select a **Chain Series**
4. Click **OK** — the sprocket is generated in its own component

## User Parameters Written

After generation, these parameters appear in the design's user parameters:

| Parameter | Description |
|-----------|-------------|
| `Spr_Pitch` | Chain pitch (mm) |
| `Spr_RollerD` | Roller diameter (mm) |
| `Spr_SeatR` | Seating arc radius (mm) |
| `Spr_ProfileR` | Profile arc radius (mm) |
| `Spr_PitchD` | Pitch circle diameter (mm) |
| `Spr_RootD` | Root circle diameter (mm) |
| `Spr_TipD` | Tip (outside) circle diameter (mm) |
| `Spr_InnerR` | Inner closing arc radius (mm) |
| `Spr_Width` | Face width (mm) |
| `Spr_BoreD` | Bore placeholder diameter (mm) |

## Tooth Form Reference

The profile follows the ANSI B29.1 / JIS B1801 formulas:

$$r_i = 0.505 \cdot d_r + 0.0345 \cdot d_r^{1/3}$$

$$r_f = 0.12 \cdot d_r \cdot (N + 2)$$

$$D_a = 2R_p + \left(1 - \frac{1.6}{N}\right)p - d_r$$

where $d_r$ = roller diameter, $N$ = tooth count, $p$ = pitch, $R_p$ = pitch radius.

## License

MIT
