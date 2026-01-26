from load import loader
from transform import transformer

# TODO:
#   make this run a full db update (ie just run load and 
#   transform) but this only really needs updating every 6 
#   weeks or so - cron job
#   more likely will need to run the code that updates the 
#   realtime stuff (need to add that to it's own table that 
#   let's us update stuff on the fly)

class update_db:
    def __init__(self) -> None:
        self.load = loader()
        self.transform = transformer()

    def update_tables(self) -> None:
        self.load.load_data()
        self.transform.transform()