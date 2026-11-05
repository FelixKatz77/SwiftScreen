import pandas as pd

from .reaction_array import ReactionArray



class GC:

    '''A class for creating GC sequence tables.'''

    @staticmethod
    def create_sequence_table(reaction_array: ReactionArray, acq_method:str, proc_method:str, path:str=None):

        '''Creates a sequence table in csv format for the given reaction array.'''

        columns = ['Sample type', 'Vial', 'Acq. method', 'Proc. method', 'Sample name', 'Data file']

        entries = []
        vial = 1
        for row in reaction_array.array.index:
            for col in reaction_array.array.columns:
                entries.append(['Sample', vial, acq_method, proc_method, f'{reaction_array.id}-{row}{col}', '<S>'])
                vial += 1
        sequence_table = pd.DataFrame(columns=columns, data=entries)
        plate_format = reaction_array.shape[0]*reaction_array.shape[1]
        indices = range(0, plate_format, 24)
        for i in indices:
            sequence_table.loc[i-0.5] = ['Blank', 150, acq_method, proc_method, f'cleaning_run_{i}', '<S>']
        sequence_table = sequence_table.sort_index().reset_index(drop=True)
        if path:
            sequence_table.to_csv(f'{path}/{reaction_array.id}_sequence.csv', index=False)
        return sequence_table


