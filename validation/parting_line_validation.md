# Parting Plane Comparison (Flange Split vs. Others)

This document shows how the exploded mold split and parting line look when the parting plane is placed at different heights: the middle flange shelf ($Z = 10.0\text{ mm}$), right after the logo ($Z = 14.0\text{ mm}$), the top end of the part ($Z = 15.0\text{ mm}$), and above the part ($Z = 28.3\text{ mm}$).

---

## Technical Details

### 1. Case A: $Z = 10.0\text{ mm}$ (Flange Split)
*   **Parting Sheet (Cyan):** Sits exactly at the interface where the top cap meets the legs.
*   **Cavity Block (Red):** Forms the entire upper head/boss of the part (recreating the logo).
*   **Core Block (Blue):** Forms the lower body and legs/ribs.
*   **Parting Line Loops:** **2 clean loops** (Loop 1: 4 edges for the inner circular boss, Loop 2: 16 edges for the outer flange boundary).
*   *Mold Feasibility*: **Excellent**. This is the standard, most cost-effective split point because it cleanly separates the cap from the legs, minimizing slides and complex tooling.

### 2. Case B: $Z = 14.0\text{ mm}$ (Right After Logo)
*   **Parting Sheet (Cyan):** Sits just below the top face, right after the logo recess.
*   **Cavity Block (Red):** A thin flat plate ($\approx 1\text{ mm}$ thick) that only forms the top flat face and the logo details.
*   **Core Block (Blue):** A very deep block that contains the entire height of the side walls and the legs.
*   **Parting Line Loops:** **Multiple closed loops** (including the outer perimeter rectangle, the central hole, and the 4 corner screw bosses).
*   *Mold Feasibility*: **Feasible, but less common**. Placing the parting line here creates a very thin cavity plate and forces the core block to have extremely deep, thin pockets to form the side walls of the cap, which increases mold wear.

### 3. Case C: $Z = 15.0\text{ mm}$ (Physical Top End)
*   **Parting Sheet (Cyan):** Sits exactly on the top flat surface of the part.
*   **Cavity/Core Blocks:** Cavity block has no part features except a shallow recess for the top boss.
*   **Parting Line Loops:** 2 small concentric closed loops (8 edges each).

### 4. Case D: $Z = 28.3\text{ mm}$ (Above Part)
*   **Parting Sheet (Cyan):** Positioned far above the part.
*   **Parting Line Loops:** **0 loops** (completely empty parting line).
