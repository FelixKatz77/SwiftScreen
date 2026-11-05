from rdkit import Chem
from rdkit. Chem import Descriptors

def get_mw(smiles: str) -> float:
    """Calculate the molecular weight of a compound given its SMILES representation."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES string: {smiles}")
    return Descriptors.MolWt(mol)