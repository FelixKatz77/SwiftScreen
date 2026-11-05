
import json
from pathlib import Path

import pandas as pd

from .labware import LabwareDefinition


labware_path = Path(__file__).parent / 'labware'

labware = {
    "reservoirs": {file.stem: LabwareDefinition.from_json(file) for file in labware_path.joinpath('reservoirs').glob('*.json') if 'reservoir' in file.stem},
    "tuberacks": {file.stem: LabwareDefinition.from_json(file) for file in labware_path.joinpath('tuberacks').glob('*.json') if 'tuberack' in file.stem},
    "plates": {file.stem: LabwareDefinition.from_json(file) for file in labware_path.joinpath('plates').glob('*.json') if 'plate' in file.stem}
}

class ProtocolFactory:
    @staticmethod
    def create_protocol(reaction_array: 'ReactionArray', directory: str|Path, use_reservoirs: bool = True, robot_type: str = 'OT2'):
        """
        Creates a protocol for the given reaction array using the provided protocol context.
        """

        if robot_type not in ['OT2', 'Flex']:
            raise ValueError('Invalid robot type. Supported types are: OT2, Flex.')

        solutions = reaction_array.get_solutions()
        slurries = reaction_array.get_slurries()
        well_mapping = reaction_array.get_well_mapping()
        deck_positions_ot2 = [8, 11, 6, 2, 3, 9, 7, 10]
        deck_positions_flex = ['B1', 'B3', 'D1', 'D3', 'A2']
        if robot_type == 'OT2':
            deck_positions = deck_positions_ot2
        else:
            deck_positions = deck_positions_flex


        if use_reservoirs:
            reagents_full_rows_or_columns = ProtocolFactory.get_reagents_for_full_rows_or_columns(well_mapping)
            solutions_for_columns = list(set(reagents_full_rows_or_columns['columns']) & set(solutions))
            solutions_for_rows = list(set(reagents_full_rows_or_columns['rows']) & set(solutions))
        else:
            solutions_for_columns = []
            solutions_for_rows = []

        vial_racks = ProtocolFactory.get_vial_racks(reaction_array, solutions_for_columns, solutions_for_rows)

        reagents_mapping_df, reagents_mapping_str, labware_counts = ProtocolFactory.get_reagents_mapping(reaction_array, slurries, solutions_for_rows,
                                                                                                         solutions_for_columns, vial_racks, use_reservoirs,
                                                                                                         directory=directory)

        ProtocolFactory.create_compounds_table(reaction_array, reagents_mapping_df, directory=directory)

        metadata = {
            'protocolName': f'Plate Setup Protocol for {reaction_array.id}',
            'author': 'SwiftScreen Protocol Factory',
            'description': 'Transfers various reagent types into a 96-well plate with OT-2 using custom labware.',
            'apiLevel': '2.24'
        }

        with open(f'opentrons_protocol_factory/template_{robot_type}.txt', 'r') as file:
            protocol = file.read()

        protocol += f'\n\nmetadata = {json.dumps(metadata, indent=4)}\n\n'
        protocol += f'column_wise_reservoirs = {str(ProtocolFactory.get_column_wise_reservoirs())}\n\n'
        protocol += f'row_wise_reservoirs = {str(ProtocolFactory.get_row_wise_reservoirs())}\n\n'
        protocol += f'bottom_clearance = {json.dumps(ProtocolFactory.get_bottom_clearance_dict(), indent=4)}\n\n'
        protocol += 'def run(protocol: protocol_api.ProtocolContext):\n'

        if robot_type == 'OT2':
            protocol += (
                        '    # Load tip racks\n'
                        f'    single_tip_rack = protocol.load_labware(\'opentrons_96_tiprack_300ul\', \'{deck_positions.pop(0)}\')\n'
                        f'    multi_tip_rack = protocol.load_labware(\'opentrons_96_tiprack_300ul\', \'{deck_positions.pop(0)}\')\n'
            )
        else:
            protocol += (
                        '    # Load tip racks\n'
                        f'    single_tip_rack = protocol.load_labware(\'opentrons_flex_96_tiprack_200ul\', \'{deck_positions.pop(0)}\')\n'
                        f'    multi_tip_rack = protocol.load_labware(\'opentrons_flex_96_tiprack_200ul\', \'{deck_positions.pop(0)}\')\n'
            )
        protocol += '\n    # Load pipettes\n'
        if robot_type == 'OT2':
            protocol += (
                        '    p300_multi = protocol.load_instrument(\'p300_multi_gen2\', \'left\', tip_racks=[multi_tip_rack])\n'
                        '    p300_single = protocol.load_instrument(\'p300_single_gen2\', \'right\', tip_racks=[single_tip_rack])\n'
                        '    p300_multi.flow_rate.aspirate = 100\n'
                        '    p300_single.flow_rate.aspirate = 100\n'
            )
        if robot_type == 'Flex':
            protocol += (
                        '    p1000_multi = protocol.load_instrument(\'flex_8channel_1000\', \'left\', tip_racks=[multi_tip_rack])\n'
                        '    tips_by_row = sum(single_tip_rack.rows(), [])\n'
            )
        protocol += (
                    '\n    # Load custom labware\n'
                   f'    plate = protocol.load_labware(\'{reaction_array.conditions.get_plate_type()}\', \'5\')\n'
        )
        if slurries:
            protocol += '    slurry_rack = protocol.load_labware(\'ika_9_tuberack_2000ul\', \'4\')\n'
        if use_reservoirs:
            if solutions_for_columns:
                for i in range(1, labware_counts['solution_reservoir_column']+1):
                    protocol += f'    solution_reservoir_column_{i} = protocol.load_labware(\'starlab_12_reservoir_22000ul\', \'{deck_positions.pop(0)}\')\n'
            if solutions_for_rows:
                for i in range(1, labware_counts['solution_reservoir_row']+1):
                    protocol += f'    solution_reservoir_row_{i} = protocol.load_labware(\'starlab_8_reservoir_30000ul\', \'{deck_positions.pop(0)}\')\n'

        if vial_racks:
            if 'custom_24_tuberack_4000ul' in vial_racks:
                protocol += f'    tuberack_4ml = protocol.load_labware(\'custom_24_tuberack_4000ul\', \'{deck_positions.pop(0)}\')\n'
            if 'custom_24_tuberack_8000ul' in vial_racks:
                protocol += f'    tuberack_8ml = protocol.load_labware(\'custom_24_tuberack_8000ul\', \'{deck_positions.pop(0)}\')\n\n'

        if robot_type == 'Flex':
            protocol += (
                '    # Define trash\n'
                '    trash = protocol.load_trash_bin("A3")\n'
            )

        protocol += '\n    # Define addition volume\n'
        protocol += f'    addition_volume = {reaction_array.array.at["A", 1].transfer_volume}\n\n'


        protocol += '\n    # Define reagent mapping\n'
        protocol += reagents_mapping_str + '\n\n'

        protocol += '\n    # Define well mapping\n'
        protocol += '    well_mapping = ' + json.dumps(well_mapping, indent=4) + '\n\n'

        protocol += (
                    "    passed_ika_wells = []\n"
                    "    added_reagents = []\n"
                    "    for reagent, destinations in well_mapping.items():\n"
                    "        if reagent in added_reagents:\n"
                    "            continue\n"
                    "        columns = get_first_wells_of_complete_columns(destinations)\n"
                    "        rows = get_corresponding_wells_for_complete_rows(destinations)\n"
                    "        reservoir = reagents[reagent][0]\n"
                    "        if reservoir.load_name in row_wise_reservoirs:\n"
                    "            source_well = reservoir['A1']\n"
                    "        else:\n"
                    "            source_well = reservoir[reagents[reagent][1]]\n"
                    "        if reservoir.load_name == 'ika_9_tuberack_2000ul':\n"
                    "            if source_well in passed_ika_wells:\n"
                    "                protocol.pause('Please replace the vials on ika_9_tuberack_2000ul and click resume.')\n"
                    "                passed_ika_wells = []\n"
                    "            passed_ika_wells.append(source_well)\n"
                    "        volume = addition_volume\n"
        )
        if robot_type == 'OT2':
            protocol += (
                    "        if columns and reservoir.load_name in column_wise_reservoirs:\n"
                    "            pipette = p300_multi\n"
                    "            destinations = columns\n"
                    "        elif rows and reservoir.load_name in row_wise_reservoirs:\n"
                    "            pipette = p300_multi\n"
                    "            destinations = rows\n"
                    "            for reagent, mapping in reagents.items():\n"
                    "                if mapping[0].parent == reservoir.parent:\n"
                    "                    added_reagents.append(reagent)\n"
                    "        else:\n"
                    "            pipette = p300_single\n"
                    "        pipette.pick_up_tip()\n"
            )
        else:
            protocol += (
                    "        if columns and reservoir.load_name in column_wise_reservoirs:\n"
                    "            pipette = p1000_multi\n"
                    "            pipette.configure_nozzle_layout(style=ALL)\n"
                    "            destinations = columns\n"
                    "            pipette.pick_up_tip()\n"
                    "        else:\n"
                    "            pipette = p1000_multi\n"
                    "            pipette.configure_nozzle_layout(style=SINGLE, start=\'H1\')\n"
                    "            pipette.pick_up_tip(location=tips_by_row.pop(0))\n"
            )
        protocol += (
                    "        if reservoir.load_name in ['custom_24_tuberack_4000ul', 'custom_24_tuberack_8000ul']:\n"
                    "            for well in destinations:\n"
                    "                pipette.mix(2, 100, source_well.bottom(bottom_clearance[reservoir.load_name]), final_push_out=10)\n"  
                    "                pipette.aspirate(volume, source_well.bottom(bottom_clearance[reservoir.load_name]))\n"
                    "                pipette.air_gap(5)\n"
                    "                pipette.dispense(volume, plate[well].bottom(z=+20))\n"  
                    "                pipette.blow_out(plate[well].bottom(z=+20))\n"
                    "        else:\n"
                    "           for well in destinations:\n"
                )
        if robot_type == 'OT2':
            protocol += (
                    "               pipette.aspirate(volume, source_well.bottom(bottom_clearance[reservoir.load_name]))\n"
                )
        elif robot_type == 'Flex':
            protocol += (
                    "               asp_height = find_aspirate_height(pipette, source_well)\n"
                    "               pipette.aspirate(volume, source_well.bottom(z=asp_height))\n"
                )
        protocol += (
                    "               pipette.air_gap(5)\n"
                    "               pipette.dispense(volume, plate[well].bottom(z=+20))\n"
                    "               pipette.blow_out(plate[well].bottom(z=+20))\n"
                    "        pipette.drop_tip()\n"
                )

        # Write the protocol to a python file
        with open(f'{str(directory)}/{reaction_array.id}_protocol.py', 'w') as file:
            file.write(protocol)

    @staticmethod
    def get_column_wise_reservoirs() -> list:
        """Returns a list of reservoirs that are column-wise."""
        return [name for name, details in labware['reservoirs'].items() if details.column_wise]

    @staticmethod
    def get_row_wise_reservoirs() -> list:
        """Returns a list of reservoirs that are row-wise."""
        return [name for name, details in labware['reservoirs'].items() if details.row_wise]

    @staticmethod
    def get_bottom_clearance_dict() -> dict:
        """Returns a dictionary of bottom clearances for each labware item."""
        bottom_clearances = {}
        for type in labware.keys():
            clearances = {name: details.bottom_clearance for name, details in labware[type].items()}
            bottom_clearances.update(clearances)
        return bottom_clearances

    @staticmethod
    def get_first_wells_of_complete_columns(wells: list) -> list:
        from collections import defaultdict
        import re

        expected_rows = set("ABCDEFGH")
        column_to_rows = defaultdict(set)

        for well in wells:
            match = re.match(r"^([A-H])(\d{1,2})$", well)
            if match:
                row, col = match.groups()
                column_to_rows[int(col)].add(row)

        # Find columns that contain all rows A–H
        complete_columns = sorted(col for col, rows in column_to_rows.items() if rows == expected_rows)

        # Return the first well (row A) of each complete column
        return [f"A{col}" for col in complete_columns]

    @staticmethod
    def get_first_wells_of_complete_rows(wells: list) -> list:
        from collections import defaultdict
        import re

        expected_columns = set(range(1, 13))  # Assuming columns are numbered 1 to 12
        row_to_columns = defaultdict(set)

        for well in wells:
            match = re.match(r"^([A-H])(\d{1,2})$", well)
            if match:
                row, col = match.groups()
                row_to_columns[row].add(int(col))

        # Find rows that contain all columns 1–12
        complete_rows = sorted(row for row, cols in row_to_columns.items() if cols == expected_columns)

        # Return the first well (column 1) of each complete row
        return [f"{row}1" for row in complete_rows]

    @staticmethod
    def get_reagents_for_full_rows_or_columns(well_mapping: dict) -> dict:
        """
        Returns a dict with reagents that can be added to full rows or columns.
        """
        reagents_for_columns = []
        reagents_for_rows = []
        for reagent, wells in well_mapping.items():
            if ProtocolFactory.get_first_wells_of_complete_columns(wells):
                reagents_for_columns.append(reagent.split('_')[0])
            elif ProtocolFactory.get_first_wells_of_complete_rows(wells):
                reagents_for_rows.append(reagent.split('_')[0])
        return {
            "columns": list(set(reagents_for_columns)),
            "rows": list(set(reagents_for_rows))
        }

    @staticmethod
    def get_corresponding_row_for_stock(wells):
        rows = [x[0] for x in ProtocolFactory.get_first_wells_of_complete_rows(wells)]
        return rows

    @staticmethod
    def get_reagents_mapping(reaction_array: 'ReactionArray', slurries: list, solutions_for_rows: list, 
                            solutions_for_columns: list, vial_racks: dict, use_reservoirs: bool, directory: str|Path = None) -> \
    tuple[pd.DataFrame, str, dict]:
        """
        Returns a dict with all reagents and their corresponding source wells.
        """

        well_mapping = reaction_array.get_well_mapping()

        stock_names = list(well_mapping.keys())
        reagents_mapping = {}
        slurry_count = 0
        wells_solution_reservoir_row = labware["reservoirs"]['starlab_8_reservoir_30000ul'].wells
        wells_solution_reservoir_col = labware["reservoirs"]['starlab_12_reservoir_22000ul'].wells
        wells_slurry_rack = labware["tuberacks"]['ika_9_tuberack_2000ul'].wells
        if 'custom_24_tuberack_4000ul' in vial_racks:
            wells_tuberack_4ml = labware["tuberacks"]['custom_24_tuberack_4000ul'].wells
        if 'custom_24_tuberack_8000ul' in vial_racks:
            wells_tuberack_8ml = labware["tuberacks"]['custom_24_tuberack_8000ul'].wells
        labware_counts = {
            'solution_reservoir_row': 1,
            'solution_reservoir_column': 1
        }


        for stock_name in stock_names:
            compound = reaction_array.compounds[stock_name.split('_')[0]]
            if compound.addition in ['solution', 'liquid'] and (compound.id in solutions_for_rows or compound.id in solutions_for_columns):
                if compound.id in solutions_for_rows:
                    count = labware_counts['solution_reservoir_row']
                    rows = ProtocolFactory.get_first_wells_of_complete_rows(well_mapping[stock_name])
                    reagents_mapping[stock_name] = (f'solution_reservoir_row_{count}', rows)
                    wells_solution_reservoir_row = [row for row in wells_solution_reservoir_row if row not in rows]
                    if not wells_solution_reservoir_row:
                        labware_counts['solution_reservoir_row'] += 1
                        wells_solution_reservoir_row = labware["reservoirs"]['starlab_8_reservoir_30000ul'].wells
                    pass
                elif compound.id in solutions_for_columns:
                    count = labware_counts['solution_reservoir_column']
                    reagents_mapping[stock_name] = (f'solution_reservoir_column_{count}', wells_solution_reservoir_col.pop(0))
                    if not wells_solution_reservoir_col:
                        labware_counts['solution_reservoir_column'] += 1
                        wells_solution_reservoir_col = labware["reservoirs"]['starlab_12_reservoir_22000ul'].wells
            elif compound.addition in ['solution', 'liquid']:
                if compound.id in vial_racks.get('custom_24_tuberack_4000ul', []):
                    reagents_mapping[stock_name] = ('tuberack_4ml', wells_tuberack_4ml.pop(0))
                elif compound.id in vial_racks.get('custom_24_tuberack_8000ul', []):
                    reagents_mapping[stock_name] = ('tuberack_8ml', wells_tuberack_8ml.pop(0))
            elif compound.addition == 'slurry' and compound.id in slurries:
                reagents_mapping[stock_name] = ('slurry_rack', wells_slurry_rack[slurry_count])
                slurry_count += 1
                if slurry_count >= len(wells_slurry_rack):
                    slurry_count = 0
        reagents_mapping_df = pd.DataFrame.from_dict(reagents_mapping, orient='index', columns=['labware', 'well'])
        if directory:
            reagents_mapping_df.to_csv(f'{str(directory)}/{reaction_array.id}_reagents_mapping.csv')
        mapping_str = '    reagents = {\n'
        for reagent, (source, well) in reagents_mapping.items():
            if isinstance(well, list):
                well = f'{well}'
                mapping_str += f'        "{reagent}": ({source}, {well}),\n'
            else:
                mapping_str += f'        "{reagent}": ({source}, \'{well}\'),\n'
        mapping_str = mapping_str.rstrip(',\n')
        mapping_str += '\n    }'
        return reagents_mapping_df, mapping_str, labware_counts

    @staticmethod
    def get_vial_racks(reaction_array: 'ReactionArray', solutions_for_columns:list, solutions_for_rows:list) -> dict:
        racks = {}
        compound_table = reaction_array.create_compounds_table()
        solutions_and_liquids = compound_table[compound_table['addition'].isin(['solution', 'liquid'])]

        solutions_and_liquids = solutions_and_liquids[~solutions_and_liquids['id'].isin(solutions_for_columns + solutions_for_rows)]
        reagents_8ml = solutions_and_liquids[solutions_and_liquids['stock volume (uL)'] > 3600]['id'].tolist()
        reagents_4ml = solutions_and_liquids[solutions_and_liquids['stock volume (uL)'] <= 3600]['id'].tolist()
        if reagents_4ml:
            racks['custom_24_tuberack_4000ul'] = reagents_4ml
        if reagents_8ml:
            racks['custom_24_tuberack_8000ul'] = reagents_8ml
        return racks

    @staticmethod
    def create_compounds_table(reaction_array, reagents_mapping:pd.DataFrame, directory: str|Path = None, slurry_dead_volume: int = 850, reservoir_column_dead_volume: int = 1000, reservoir_row_dead_volume: int = 4000, vials_dead_volume: int = 400, use_vials=False):
        """Creates a table with all compounds in the reaction array."""
        compounds_table = []
        transfer_volume = reaction_array.conditions.get_transfer_volume()
        solid_additions = [compound for id, compound in reaction_array.compounds.items() if compound.addition == 'solid']

        for name, stock in reaction_array.stocks.items():
            reactant = stock.reactant
            labware = reagents_mapping.loc[name, 'labware']

            well_count = reaction_array.get_well_count_stock(stock_name=name)

            if 'slurry_rack' in labware:
                stock_volume = well_count * transfer_volume + slurry_dead_volume # Add dead volume for slurry
            elif 'solution_reservoir_column' in labware:
                stock_volume = well_count * transfer_volume + reservoir_column_dead_volume  # Add dead volume for reservoir
            elif 'solution_reservoir_row' in labware:
                stock_volume = well_count * transfer_volume + reservoir_row_dead_volume*len(reagents_mapping.loc[name, 'well'])
            elif 'tuberack' in labware:
                stock_volume = well_count * transfer_volume + vials_dead_volume
            else:
                raise ValueError(f'Unknown labware type: {labware}')
            mass = reactant.mw * stock.concentration * (stock_volume / 1000)
            compounds_table.append({
                'id': reactant.id,
                'name': reactant.name,
                'smiles': reactant.smiles,
                'solvent': stock.solvent.name,
                'mw (g/mol)': reactant.mw,
                'role': reactant.role,
                'well_count': well_count,
                'stock concentration (M)': stock.concentration,
                'stock volume (uL)': stock_volume,
                'mass (mg)': round(mass, 1),
                'density (g/cm3)': reactant.density,
                'addition': reactant.addition
            })
        for compound in solid_additions:
            well_count = reaction_array.get_well_count_solid(compound.id)
            conditions = reaction_array.conditions
            n = conditions.get_eq(compound.role)*conditions.get_concentration()*conditions.get_volume()/1000
            mass = compound.mw * n

            compounds_table.append({
                'id': compound.id,
                'name': compound.name,
                'smiles': compound.smiles,
                'solvent': '',
                'mw (g/mol)': compound.mw,
                'role': compound.role,
                'well_count': well_count,
                'stock concentration (M)': '',
                'stock volume (uL)': '',
                'mass (mg)': round(mass, 1),
                'density (g/cm3)': compound.density,
                'addition': compound.addition
            })
        for solvent in reaction_array.components['solvent']:
            solvent_additions = reaction_array.get_solvent_additions(solvent.name)
            if solvent_additions == 0:
                continue
            compounds_table.append({
                'id': solvent.id,
                'name': solvent.name,
                'smiles': solvent.smiles,
                'solvent': solvent.name,
                'mw (g/mol)': solvent.mw,
                'role': solvent.role,
                'well_count': solvent_additions,
                'stock concentration (M)': 0,
                'stock volume (uL)': solvent_additions * transfer_volume+1000,
                'mass (mg)': 0,
                'density (g/cm3)': solvent.density,
                'addition': solvent.addition
            })
        table = pd.DataFrame(compounds_table)
        table = table.sort_values(by=['role', 'id']).reset_index(drop=True)
        if directory is None:
            return table
        else:
            table.to_csv(Path(directory) / f'{reaction_array.id}_compounds_table.csv', index=False)

if __name__ == "__main__":
    # This block is for testing purposes only
    pass