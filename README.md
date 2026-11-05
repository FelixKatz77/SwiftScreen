<p align="center">
  <img src="docs/logo.png" alt="SwiftScreen logo: a swallow perched on a 96-well plate" width="200">
</p>

<h1 align="center">SwiftScreen</h1>

SwiftScreen converts the design of a high-throughput reaction screen into the files needed to run it. From a compound list, a plate layout and a set of reaction conditions, it computes the stock solutions and per-well transfer volumes and writes:

- an Opentrons protocol (OT-2 or Flex) that dispenses all reagents into a 96-well plate;
- a compounds table listing the amount of each reagent to prepare, including dead volumes;
- optionally, a GC sequence table for analysis of the finished plate.

## Installation

SwiftScreen requires Python ≥ 3.11 and is managed with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

## Inputs

| File | Content |
| --- | --- |
| Compounds (`.csv`) | One row per compound with columns `id`, `name`, `smiles`, `role` (e.g. `catalyst`, `base`, `solvent`) and optionally `density` and `addition` (`solution` by default, or `slurry`). |
| Plate layout (`.csv`) | One row per well, indexed by well position (`A1` … `H12`), with a `reagents` column of comma-separated compound IDs and an optional `products` column of SMILES. |
| Conditions (`.json`) | Plate type, reaction volume (µL), concentration (M), number of additions, equivalents per role and addition order. |

## Usage

```python
from swiftscreen.backend.project import Project
from swiftscreen.backend.screen import Screen
from swiftscreen.backend.gc_tools import GC

round = 6
lab_book_id = "FKB-FA-167"

project = Project(owner="FKB", id="PlateOpt", description="PlateOpt project")
project.load_compounds_from_csv("PlateOpt/Plates/cu_coupling_chemicals.csv")

screen = Screen(id=lab_book_id, format=96, description=f"PlateOpt_round{round}", project_id=project.id)
screen.create_reaction_array(
    csv_layout=f"PlateOpt/Plates/round{round}/plate_design_round{round}.csv",
    shape=(8, 12),
    conditions=f"PlateOpt/Plates/round{round}/conditions.json",
    compounds=project.compounds,
    no_replicates=1,
)

out_dir = f"PlateOpt/Plates/round{round}"
GC.create_sequence_table(screen.reaction_array, "50_20_165_50_300_1.amx", "PlateOpt", path=out_dir)
screen.reaction_array.create_opentrons_protocol(out_dir, use_reservoirs=True, robot_type="OT2")
```

The protocol and the GC sequence table are written to the round's directory. To also write the compounds table, call `screen.reaction_array.create_compounds_table(out_dir)`.

This example is [`scripts/plateopt_round1.py`](scripts/plateopt_round1.py). Its paths are relative to the working directory, so run it from the folder that contains `PlateOpt/`:

```bash
uv run --project <path/to/SwiftScreen> python <path/to/SwiftScreen>/scripts/plateopt_round1.py
```

## License

MIT; see [LICENSE.md](LICENSE.md).
