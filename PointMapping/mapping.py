import brickschema
import re
import time
import yaml
import sys


class PointMapping():
    def __init__(self, config_path):
        with open(config_path, 'r') as config_file:
            self.tagmap = yaml.safe_load(config_file)

        self.inf = brickschema.inference.TagInferenceSession(approximate=True)
        print("Initial Setting Finished")

    def flatten(self, lol):
        """flatten a list of lists"""
        return [x for sl in lol for x in sl]

    def resolve(self, q):
        # break query up into potential tags
        limit = int(q.get('limit', 20))
        print(q)
        tags = map(str.lower, re.split(r'[.:\-_ ]', q.get('query', '')))
        tags = list(tags)
        search = ''
        for tag in tags:
            if search == tag:
                tags.remove(tag)

        brick_tags = self.flatten([self.tagmap.get(tag.lower(), [tag]) for tag in tags])
        print(brick_tags)
        # Load sub-class(type)
        if q.get('type') == 'PointClass':
            brick_tags += ['Point']
        elif q.get('type') == 'EquipmentClass':
            brick_tags += ['Equipment']
        else:
            q['type'] = 'BrickClass'
            q['id'] = 'BrickClass'

        res = []
        most_likely, leftover = self.inf.most_likely_tagsets(brick_tags, limit)
        print(most_likely)
        for ml in most_likely:
            res.append({
                'id': q['query'],
                'name': ml,
                'score': (len(brick_tags) - len(leftover)) / len(brick_tags),
                'match': len(leftover) == 0,
                'type': [{"id": q.get("type"), "name": q.get("type")}],
            })

        return res[0]