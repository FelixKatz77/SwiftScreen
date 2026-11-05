import json
from copy import copy
from functools import reduce
from pathlib import Path

import pandas as pd
from .compound import Compound, Product, Reactant, Stock
from .opentrons_protocol_factory.factory import ProtocolFactory

class Conditions(dict):
    '''A class for storing information about the conditions of a reaction array.'''

    def __init__(self, conditions: dict = None):
        super().__init__()
        if conditions:
            self.update(conditions)

    @classmethod
    def from_file(cls, file: str|Path):
        with open(file, 'r') as f:
            conditions = json.load(f)
        return cls(conditions)

    @classmethod
    def initialize(cls, **kwargs):
        return cls(kwargs)

    def get_unit(self, key: str):
        """Returns the unit of a condition."""
        try:
            return super().__getitem__(key)['unit']
        except KeyError:
            raise ValueError(f'Condition {key} not found in the conditions.')

    def get_scale(self):
        """Returns the scale of the reaction based on concentration and volume."""
        scale = self['concentration']['value'] * self['volume']['value'] / 1000  # Umrechnung in mmol
        return scale

    def get_eq(self, component: str):
        """Returns the equivalents of a component in the reaction."""
        if 'equivalents' in self and component in self['equivalents']:
            return self['equivalents'][component]
        else:
            raise ValueError(f'Component {component} not found in the equivalents of the conditions.')

    def get_addition_order(self):
        """Returns the addition order of the components in the reaction."""
        if 'addition_order' in self:
            return self['addition_order']
        else:
            raise ValueError('Addition order not found in the conditions.')

    def get_plate_type(self):
        """Returns the type of plate used in the reaction."""
        if 'plate_type' in self:
            return self['plate_type']
        else:
            raise ValueError('Plate type not found in the conditions.')

    def get_volume(self):
        """Returns the total volume of the reaction in microliters."""
        if 'volume' in self:
            return self['volume']['value']
        else:
            raise ValueError('Volume not found in the conditions.')

    def get_concentration(self):
        """Gets the concentration of the reaction in mM."""
        if 'concentration' in self:
            return self['concentration']['value']
        else:
            raise ValueError('Concentration not found in the conditions.')

    def get_transfer_volume(self):
        """Gets the transfer volume per pipetting operation in uL."""
        if 'volume' in self and 'additions' in self:
            return self['volume']['value'] / self['additions']
        else:
            raise ValueError('Transfer volume not defined by the the conditions.')


class Well:
    '''A class for storing information about a well in a reaction array.'''

    def __init__(self, reactants: list, solvent: Reactant, stocks: dict, products: list, conditions: Conditions, components: dict, reaction: None=None):
        self.reactants = reactants
        self.solvent = solvent
        self.stocks = stocks
        self.products = products
        self.conditions = conditions
        self.reaction = reaction
        self.solvent_additions = self.__check_for_solvent_additions(components)
        self.transfer_volume = self.__get_transfer_volume()

    def __get_transfer_volume(self) -> object:
        """Returns the transfer volume for the reaction array."""

        transfer_reactants = len([reactant for reactant in self.reactants if reactant.addition in ['solution', 'slurry']])
        transfers = transfer_reactants + self.solvent_additions
        return self.conditions.get_volume() / transfers

    def __check_for_solvent_additions(self, components: dict):
        """Checks if a well requires blank solvent addition."""
        #TODO: Ignore reactants if the addition is all solid.

        solvent_additions = 0
        for reactant in self.reactants:
            if reactant.addition not in ['solution', 'slurry']:
                other_entries = components[reactant.role]
                component_additions = list(set([compound.addition for compound in other_entries]))
                if not (len(component_additions) == 1 and component_additions[0] == 'solid'):
                    solvent_additions += 1
        added_reactants = [reactant for reactant in self.reactants]
        added_components = set([reactant.role for reactant in added_reactants])
        no_missing_components = len(self.conditions['components']) - len(added_components)
        solvent_additions += no_missing_components
        return solvent_additions


class ReactionArray:
    '''A class for storing information about the combinatorial layout of a reaction array.'''

    def __init__(self, array_id:str, shape: tuple, components: dict, stocks: dict, no_replicates: int, conditions: Conditions|None, array: pd.DataFrame|None = None):
        self.id = array_id
        self.shape = shape
        self.components = components
        self.stocks = stocks
        self.compounds = {compound.id: compound for role, compounds in components.items() for compound in compounds}
        self.replicates = no_replicates
        if not no_replicates * reduce(lambda x, y: x * y, [len(value) for value in components.values()])== shape[0] * shape[1]:
            print('Number of replicates and components do not match the shape of the array.')
        if not conditions:
            conditions = Conditions.initialize()
        self.conditions = conditions
        if isinstance(array, pd.DataFrame):
            self. array = array
        else:
            self.array = pd.DataFrame(index=list(map(chr, range(65, 65 + shape[0]))),
                                  columns=range(1, shape[1] + 1))

    def __getitem__(self, pos: str):
        """Returns the well at the given position."""
        if pos[0] not in self.array.index and int(pos[1:]) not in self.array.columns:
            raise ValueError(f'Position {pos} is not valid in the reaction array.')
        return self.array.at[pos[0], int(pos[1:])]


    @classmethod
    def create_reaction_array(cls, array_id:str, csv_layout: str, shape:tuple, conditions: Conditions|Path|str, compounds: dict, no_replicates:int=1):
        #TODO collect info about all components first to enable calculation of solvent additions.
        layout = cls.__read_csv_layout(csv_layout)
        stocks = {}
        if shape[0]* shape[1] != len(layout):
            raise ValueError('Shape does not match the number of wells in the layout.')
        #if not no_replicates * reduce(lambda x, y: x * y, components.values()) == shape[0] * shape[1]:
            #raise ValueError('Number of replicates and components do not match the shape of the array.')
        if isinstance(conditions, str) or isinstance(conditions, Path):
            conditions = Conditions.from_file(conditions)
        array = pd.DataFrame(index=list(map(chr, range(65, 65 + shape[0]))),
                             columns=range(1, shape[1] + 1))
        components = {}

        for pos, row in layout.iterrows():
            entries = row['reagents']
            if isinstance(entries, str):
                entries = [entries]
            for entry in entries:
                if entry not in compounds:
                    raise ValueError(f'Compound {entry} not found in the project compounds.')
                else:
                    compound = compounds[entry]
                    if compound.role not in components:
                        components[compound.role] = [compound]
                    else:
                        if compound not in components[compound.role]:
                            components[compound.role].append(compound)

        for pos, row in layout.iterrows():
            reactants = []
            entries = row['reagents']
            if isinstance(entries, str):
                entries = [entries]
            for entry in entries:
                if entry not in compounds:
                    raise ValueError(f'Compound {entry} not found in the project compounds.')
                else:
                    compound = compounds[entry]
                    reactant = Reactant(compound=compound, scale=conditions.get_scale(), equivalents=conditions.get_eq(compound.role), addition=compound.addition)

                    if compound.role == 'solvent':
                        solvent = reactant
                    else:
                        reactants.append(reactant)

            stocks_well = cls.__create_stocks_well(reactants, solvent, conditions)
            stocks.update(stocks_well)
            well = Well(reactants=reactants, solvent=solvent, stocks=stocks_well, products=row.get('products', []), conditions=conditions, components=components)
            array.at[pos[0], int(pos[1:])] = well
        return cls(array_id = array_id, shape=shape, components=components, stocks=stocks, no_replicates=no_replicates, conditions=conditions, array=array)

    @staticmethod
    def __read_csv_layout(csv_layout):

        def smiles_to_product(smiles: list) -> list:
            products = [Product(smiles) for smiles in smiles]
            return products

        csv_layout = pd.read_csv(csv_layout, index_col=0)
        csv_layout['reagents'] = csv_layout['reagents'].str.split(', ')
        if 'products' in csv_layout.columns:
            csv_layout['products'] = csv_layout['products'].str.split(', ')
            csv_layout['products'] = csv_layout['products'].apply(smiles_to_product)
        return csv_layout

    def get_slurries(self):
        """Returns a list of unique slurry compound names in the reaction array."""
        slurries = []
        for component in self.components.values():
            for compound in component:
                if compound.addition == "slurry" and compound.id not in slurries:
                    slurries.append(compound.id)
        return slurries

    def get_solutions(self):
        """Returns a list of unique solution/liquid compound names in the reaction array."""
        solutions = []
        for component in self.components.values():
            for compound in component:
                if compound.addition in ["solution", "liquid"] and compound.id not in solutions:
                    solutions.append(compound.id)
        return solutions

    @staticmethod
    def __create_stocks_well(reactants:list, solvent: Reactant, conditions: Conditions):

        total_volume = conditions.get_volume()
        stocks = {}

        for reactant in reactants:
            addition = reactant.addition
            match addition:
                case 'solution' | 'slurry':
                    dilution_factor = conditions.get_volume() / conditions.get_transfer_volume()
                    concentration = conditions.get_concentration() * conditions.get_eq(reactant.role)
                    concentration = dilution_factor * concentration
                    stock = Stock(reactant=reactant, addition=addition, solvent= solvent, concentration=concentration)
                    stocks[f'{reactant.id}_{solvent.name}'] = stock
                case _:
                    pass
        return stocks


    def get_well_mapping(self):
        """Returns a dict with all reactants and their corresponding well positions."""


        well_mapping = {}
        for index, row in self.array.iterrows():
            for col in self.array.columns:
                well = row[col]
                for name, stock in well.stocks.items():
                    if name not in well_mapping:
                        well_mapping[name] = []
                    well_mapping[name].append(f'{index}{col}')
                if well.solvent_additions > 0:
                    solvent = well.solvent.name
                    if solvent not in well_mapping:
                        well_mapping[solvent] = []
                    well_mapping[solvent].append(f'{index}{col}')
        well_mapping = dict(sorted(well_mapping.items(), key=self.__get_addition_order))
        return well_mapping


    def create_opentrons_protocol(self, directory: str|Path, use_reservoirs: bool = True, robot_type: str = 'OT2'):
        protcol = ProtocolFactory.create_protocol(self, directory, use_reservoirs=use_reservoirs, robot_type=robot_type)

    def create_compounds_table(self, directory: str|Path = None, slurry_dead_volume: int = 800, reservoir_dead_volume: int = 1000, vials_dead_volume: int = 400, use_vials=False):
        """Creates a table with all compounds in the reaction array."""
        compounds_table = []
        transfer_volume = self.conditions.get_transfer_volume()

        for name, stock in self.stocks.items():
            reactant = stock.reactant

            well_count = self.get_well_count_stock(stock_name=name)

            if stock.addition == 'slurry':
                stock_volume = well_count * transfer_volume + slurry_dead_volume # Add dead volume for slurry
            elif stock.addition in ['solution', 'liquid'] and not use_vials:
                stock_volume = well_count * transfer_volume + reservoir_dead_volume  # Add dead volume for reservoir
            else:
                stock_volume = well_count * transfer_volume + vials_dead_volume
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
        for solvent in self.components['solvent']:
            solvent_additions = self.get_solvent_additions(solvent.name)
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
        return table


    def get_well_count_stock(self, stock_name: str) -> int:
        count = 0
        for index, row in self.array.iterrows():
            for col in self.array.columns:
                well = row[col]
                if stock_name in well.stocks:
                    count += 1
        return count

    def get_well_count_solid(self, id: str):
        count = 0
        for index, row in self.array.iterrows():
            for col in self.array.columns:
                well = row[col]
                if id in [reactant.id for reactant in well.reactants]:
                    count += 1
        return count

    def get_solvent_additions(self, solvent_name):
        solvent_additions = 0
        for index, row in self.array.iterrows():
            for col in self.array.columns:
                well = row[col]
                if well.solvent.name == solvent_name:
                    solvent_additions += well.solvent_additions
        return solvent_additions



    def __get_addition_order(self, reactant_mapping: tuple) -> int:
        """Returns the addition order of a reactant."""
        reactant = reactant_mapping[0].split('_')[0]  # Extract the reactant name from the key
        for component, reactants in self.components.items():
            if reactant in [r.id for r in reactants]:
                addition_order = self.conditions.get_addition_order()
                return self.conditions.get_addition_order()[component]
        raise ValueError(f'Reactant {reactant} not found in addition order.')




