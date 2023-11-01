from PointMapping.mapping import PointMapping
import pandas as pd
import sys
import yaml



def _get_class(kls):
    parts = kls.split(".")
    module =".".join(parts[:-1])
    main_mod = __import__(module)
    for comp in parts[1:]:
        main_mod = getattr(main_mod, comp)
    return main_mod


class Main:
    def __init__(self, config_path):
        '''Load Configuration File'''
        with open(config_path, 'r') as config_file:
            self.config = yaml.safe_load(config_file)
        
        pointMap = self.config.get("pointmapping")
        pointApp = pointMap['path']
        pointConfig = pointMap['config']

        kla = _get_class(pointApp)
        self.mapping = kla(config_path=pointConfig)

        profile = self.config.get('profile')
        
        self.df = pd.read_csv(profile['database'], index_col=0)
        cols = self.df.columns
        tagging = []        
        for col in cols:
            tagging.append({"before": col, "after": self.mapping.resolve({'query': col}).get("name", "None")})
            self.df = self.df.rename(columns={col: self.mapping.resolve({'query': col}).get("name", "None")})
        self.create_report(tagging)

        app = '.'.join(['FDD', profile['component'], profile['model'], 'Application'])
        kla = _get_class(app)
        app_instance = kla(self.config['application'][profile['component']][profile['model']][profile['device']]['config'])

        max_len = len(self.df)
        for num in range(max_len):
            message = self.df.loc[(self.df.index) == num].to_dict('records')
            app_instance.handled_message(message=message)


    def create_report(self, message):
        file_path = './tag_report.txt'

        with open(file_path, 'w') as output_file:
            for msg in message:
                print(msg, file=output_file)




def main(argv=sys.argv):
    Main(config_path=r'C:\Users\ikim2\OneDrive - NREL\Icksung\Demo-scripts\config.yaml')


if __name__=="__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass