from datetime import datetime
from .compound import Compound
from rdkit import Chem


class Project:

    '''A class storing project information'''

    def __init__(self, owner:str, id:str, description:str, collaborators:dict = None, compounds:dict = None):
        self.owner = owner
        self.id = id
        self.description = description
        self.collaborators = collaborators if collaborators is not None else {}
        self.creation_date = datetime.now()
        self.status = 'active'
        self.compounds = compounds if compounds is not None else {}
        self.screens = {}

    def add_collaborator(self, user:str, role:str):
        roles = ['viewer', 'editor']
        if role not in roles:
            raise ValueError('Role must be either "viewer" or "editor".')
        else:
            self.collaborators[user] = role

    def remove_collaborator(self, user:str):
        if user not in self.collaborators:
            raise ValueError('User is not a collaborator.')
        else:
            del self.collaborators[user]

    def update_description(self, description:str):
        self.description = description

    def update_status(self, status:str):
        statuses = ['active', 'inactive', 'finished', 'archived']
        if status not in statuses:
            raise ValueError('Status must be either "active", "inactive", "finished", or "archived".')
        else:
            self.status = status

    def load_compounds_from_csv(self, csv_file: str):
        import pandas as pd
        df = pd.read_csv(csv_file)
        # Normalize column names for flexible schema support
        df.columns = [c.strip().lower() for c in df.columns]
        for _, row in df.iterrows():
            role = str(row.get('role', '')).strip()
            cid = row.get('id', None)
            cid = None if pd.isna(cid) else str(cid).strip()
            name = row.get('name', None)
            if name is None or (isinstance(name, float) and pd.isna(name)) or str(name).strip() == '':
                name = f"{role} {cid}" if cid else str(row.get('smiles', ''))[:20]
            else:
                name = str(name).strip()
            smiles = str(row.get('smiles', '')).strip()
            density = row.get('density', None)
            addition = row.get('addition', None)
            addition = None if (addition is None or (isinstance(addition, float) and pd.isna(addition))) else str(addition).strip()
            if not addition:
                addition = 'solution'
            compound = Compound(id=cid, name=name, smiles=smiles, role=role,
                                density=density, addition=addition)
            # Use id if available; else use name as key
            key = compound.id
            self.compounds[key] = compound

    def add_compound(self, compound: Compound):
        if Chem.CanonSmiles(compound.smiles) in self.compounds:
            raise ValueError(f'Compound {compound.name}: {compound.smiles} already exists in the project.')
        else:
            self.compounds[compound.name] = compound

    def remove_compound(self, compound_name: str):
        if compound_name not in self.compounds:
            raise ValueError(f'Compound {compound_name} does not exist in the project.')
        else:
            del self.compounds[compound_name]

    def add_screens(self, screen_id: str, reaction_array):
        if screen_id in self.screens:
            raise ValueError(f'Screen with ID {screen_id} already exists in the project.')
        else:
            self.screens[screen_id] = reaction_array