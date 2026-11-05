from datetime import datetime
from .reaction_array import ReactionArray


class Screen:

    '''Class for a screen object'''

    def __init__(self, id:str, format:int, description:str = None, project_id: str = None):

        self.id = id
        self.format = format
        self.description = description
        self.project_id = project_id
        self.date = datetime.now()
        self.reaction_array = None
        #TODO Select compounds here. Add aditions number logic here. Different eq. in one plate?

    def add_array(self, reaction_array: ReactionArray):
        if self.reaction_array is not None:
            raise ValueError('Reaction array already exists for this screen.')
        if not isinstance(reaction_array, ReactionArray):
            raise TypeError('reaction_array must be an instance of Reaction_Array.')
        else:
            self.reaction_array = reaction_array

    def create_reaction_array(self, csv_layout: str, shape: tuple, conditions: str, compounds: list, no_replicates: int = 1):
        """Creates a reaction array for the screen."""
        if self.reaction_array is not None:
            raise ValueError('Reaction array already exists for this screen.')
        else:
            self.reaction_array = ReactionArray.create_reaction_array(
                array_id=self.id,
                csv_layout=csv_layout,  # Assuming no CSV layout is provided here
                shape=shape,
                conditions=conditions,
                compounds=compounds,
                no_replicates=no_replicates
            )



