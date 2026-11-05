from swiftscreen.backend.project import Project
from swiftscreen.backend.screen import Screen
from swiftscreen.backend.gc_tools import GC

round = 6
lab_book_id = "FKB-FA-167"

my_project = Project(owner='FKB', id='PlateOpt', description='PlateOpt project')
my_project.load_compounds_from_csv("PlateOpt/Plates/cu_coupling_chemicals.csv")
my_screen = Screen(id=f'{lab_book_id}', format=96, description=f'PlateOpt_round{round}', project_id=my_project.id)
my_screen.create_reaction_array(csv_layout=f"PlateOpt/Plates/round{round}/plate_design_round{round}.csv", shape=(8, 12), conditions=f'PlateOpt/Plates/round{round}/conditions.json', compounds=my_project.compounds, no_replicates=1)
sequence_table = GC.create_sequence_table(my_screen.reaction_array, '50_20_165_50_300_1.amx', 'PlateOpt', path=f"PlateOpt/Plates/round{round}")
my_screen.reaction_array.create_opentrons_protocol(f"PlateOpt/Plates/round{round}", use_reservoirs=True, robot_type='OT2')
