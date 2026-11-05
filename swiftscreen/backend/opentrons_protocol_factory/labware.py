from dataclasses import dataclass
from pathlib import Path
import json

@dataclass
class LabwareDefinition:
    name: str
    columns: int
    rows: int
    volume: int
    bottom_clearance: float
    column_wise: bool
    row_wise: bool
    wells: list

    @classmethod
    def from_json(cls, json_data):
        if isinstance(json_data, str) or isinstance(json_data, Path):
            with open(json_data, 'r') as f:
                data = json.load(f)
        else:
            data = json_data

        ordering = data['ordering']
        wells = []
        for column in ordering:
            wells.extend(column)
        columns = len(ordering)
        rows = len(ordering[0]) if columns > 0 else 0

        first_well = next(iter(data['wells'].values()))
        volume = first_well['totalLiquidVolume']
        name = data['parameters']['loadName']
        if name == 'asparadox_96_wellplate_1000ul':
            bottom_clearance = 3
        elif name == 'ika_9_tuberack_2000ul':
            bottom_clearance = 2.5
        elif name in ["custom_24_tuberack_8000ul", "custom_24_tuberack_4000ul"]:
            bottom_clearance = 0.75
        else:
            bottom_clearance = 1.0

        column_wise = rows == 1 and first_well['yDimension'] >= 66
        row_wise = columns == 1 and rows == 8

        return cls(
            name=name,
            columns=columns,
            rows=rows,
            volume=volume,
            bottom_clearance=bottom_clearance,
            column_wise=column_wise,
            row_wise=row_wise,
            wells=wells
        )