from .utils import get_mw
from rdkit import Chem

class Compound:
    '''Class for compound object'''

    def __init__(self, id: str|None, name: str|None, smiles: str, role: str, density: None | float = None, addition = 'solution'):
        self.id = id
        self.name = name
        try:
            self.smiles = Chem.CanonSmiles(smiles)
        except:
            self.smiles = smiles
        self.mw = get_mw(smiles)
        self.role = role
        self.density = density
        assert addition in ['solution', 'slurry', 'solid', 'liquid', None], "Addition must be either 'solution', 'slurry' or 'solid'."
        self.addition = addition

    def __str__(self):
        return f'{self.name}: {self.smiles}'


class Reactant(Compound):
    '''Class for reactant object'''

    def __init__(self, compound: Compound, scale: float, equivalents: float, addition: str = None):
        super().__init__(compound.id, compound.name, compound.smiles, compound.role, compound.density)
        self.equivalents = equivalents
        if addition:
            assert addition in ['solution', 'slurry', 'solid', 'liquid'], "Addition must be either 'solution', 'slurry', 'liquid' or 'solid'."
            self.addition = addition
        if compound.role == 'solvent':
            self.amount = 0.0
            self.stoffmenge = 0.0
        else:
            self.amount = self.mw * scale * self.equivalents
            self.stoffmenge = scale * self.equivalents

    def __str__(self):
        return f'{self.name}: {self.smiles}'



class Product(Compound):
    '''Class for product object'''

    def __init__(self, smiles):
        super().__init__(None, None, smiles, 'product', None)

class Stock:
    '''Class for a stock solution object'''

    def __init__(self, reactant:Reactant, addition:str, solvent:Reactant, concentration: float):
        self.reactant = reactant
        self.addition = addition
        self.solvent = solvent
        self.concentration = concentration