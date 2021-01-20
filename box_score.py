#!/usr/bin/env python

"""parse.py: Parse eggball ndjson records to produce player statistics."""

import ndjson
import os
import sys
import tabulate
import csv
from pathlib import Path

TEAMS = {
    "dinos": ['abe lincoln', 'arctic_tern', 'asap', 'titanblue', 'tc', 'airmigo', 'ballanka', 'anka.', 'balljack hor'],
    "ogres": ['jswan', 'anne frank', 'karlpilk', 'son hye joo', 'beast mode', 'el sacko', 'squeeb'],
    'raptors': ['werth', 'od god', 'jackals', 'ty', 'get_right', '#selfysyntax', 'gem#1'],
    'saucers': ['bmf', 'daballa', 'iha', 'mg', 'bump', 'vegan falc', 'canadian'],
    'quack': ['boldroller', 'relinquished', 'slide', 'gleg', 'acapuck', 'yiss', 'natex', 'king~zion'],
    'guacs': ['kevin', 'coltsrock', 'vigil', 'ray-ray', 'ant', 'unit-01', 'heart', 'blaster'],
    'goons': ['beast mode', 'unit-01', 'yiss', 'kooler', 'homer jay', 'vegan falc', 'sminitrious', 'bmf'],
    'ballphins': ['squeeb', 'king~zion', '#selfysyntax', 'jarvislandry', 'dakiller32', 'canadian', 'lbj']
}

HEADERS = ['MP', 'hold', 'caps', 'completions', 'ints_thrown', 'tagged', 'receptions', 'ints_caught', 
            'tags', 'raps_thrown', 'raps_caught', 'self_passes', 'start_egg']


class BoxScore:
    def __init__(self, input_dir, t1, t2):
        self.dir = input_dir
        self.team1 = TEAMS[t1]
        self.team2 = TEAMS[t2]
        self.produce_stats()


    def produce_stats(self):
        records = []
        for filename in os.listdir(self.dir):
            path = Path(self.dir + filename)
            with open(path) as f:
                try:
                    data = ndjson.load(f)
                    results = self.one_game(data)
                    eu = filename.split('.')[0]
                    self.generate_csv(results, eu)
                    for r in results:
                        records.append(r)
                except ValueError:
                    continue
        final = self.merge_results(records)
        self.merge_csvs()
        self.print_box_score(final)


    def one_game(self, data):
        ids = self.initialize_game(data)
        eggball = [x for x in data if x[1] == 'eggBall' or x[1] == 'boat']
        eggball = [x for x in eggball if x[1] == 'boat' or x[2]['state']]
        eggball = eggball[1:]
        #for i in eggball:
            #print(i)
        # huddle is printed twice every point, we want the holder in the 2nd line
        huddleSwitch = False
        prevHolder = {}
        prevPrevHolder = {}
        holder = {}
        caughtAt = 0
        thrownAt = 0
        in_air = True
        waiting_last = False
        for i in eggball:
            timestamp = i[0]
            #print(timestamp)
            dic = i[2]
            if i[1] == 'boat':
                if prevPrevHolder['team'] == prevHolder['team']:
                    prevPrevHolder['raps_thrown'] += 1
                    prevPrevHolder['caps'] += 1
                    prevHolder['raps_caught'] += 1
                # self rap/own rap
                else:
                    prevHolder['raps_caught'] += 1
                waiting_last = False
                continue
            if dic['state'] == 'waiting':
                if waiting_last:
                    continue
                try:
                    prevHolder['caps'] += 1
                    prevHolder['hold'] += ((timestamp - caughtAt) / 1000)
                except KeyError:
                    sys.stderr.write('No prevHolder ' + str(timestamp))
                waiting_last = True
                continue
                
            waiting_last = False
            holderid = dic['holder']
            if holderid:
                holder = ids[holderid]
            # in the huddle
            if dic['state'] == 'huddle':
                if huddleSwitch:
                    holder['start_egg'] += 1
                    prevHolder = ids[holderid]
                    caughtAt = timestamp + 5000
                huddleSwitch = not huddleSwitch

            # a tag (or rare handoff)
            elif not in_air:
                if holderid and holderid != prevHolder['id']:
                    # handoff
                    if holder['team'] == prevHolder['team']:
                        holder['receptions'] += 1
                        prevHolder['completions'] += 1
                    # tag
                    else:
                        holder['tags'] += 1
                        prevHolder['tagged'] += 1
                prevHolder['hold'] += ((timestamp - caughtAt) / 1000)
                caughtAt = timestamp
            
            # a catch
            elif holderid:
                if holder['team'] != prevHolder['team']:
                    prevHolder['ints_thrown'] += 1
                    holder['ints_caught'] += 1
                elif holder != prevHolder:
                    prevHolder['completions'] += 1
                    holder['receptions'] += 1
                else:
                    holder['self_passes'] += 1
                caughtAt = timestamp

            # a throw
            else:
                prevHolder['hold'] += ((timestamp - caughtAt) / 1000)
                thrownAt = timestamp

            if holderid:
                prevPrevHolder = prevHolder
                prevHolder = ids[holderid]
                in_air = False
            else:
                in_air = True
        return ids[1:]


    def initialize_game(self, data):
        ids = [None] * 50
        # ids aren't 0-indexed, fixing it here
        ids[0] = {'player': 'Brazzers', 'team': 0}
        count = 1
        start_time = 0
        end_time = -1
        for line in data:
            if line[1] == 'p' and type(line[2]) is list and 'name' in line[2][0]:
                for player in line[2]:
                    id = player['id']
                    ids[id] = {
                        'id': id,
                        'player': player['name'], 
                        'team': player['team'],
                        'MP': 0.0,
                        'hold': 0.0,
                        'caps': 0,
                        'completions': 0,
                        'ints_thrown': 0,
                        'tagged': 0,
                        'receptions': 0,
                        'ints_caught': 0,
                        'tags': 0,
                        'raps_thrown': 0,
                        'raps_caught': 0,     
                        'self_passes': 0,
                        'start_egg': 0,
                        'joined_at': line[0],
                        'left_at': -1
                    }
            elif line[1] == 'time' and line[2]['state'] == 1:
                start_time = line[0]
            
            elif line[1] == 'playerLeft':
                # player left before game ended
                if end_time == -1:
                    ids[line[2]]['left_at'] = line[0]

            elif line[1] == 'end':
                end_time = line[0]

        ids = [i for i in ids if i]
        for i in ids[1:]:
            i['joined_at'] = max(i['joined_at'], start_time)
            if i['left_at'] == -1:
                i['left_at'] = end_time
            i['MP'] = round((i['left_at'] - i['joined_at']) / 60000,2)
        return ids


    def merge_results(self, records):
        final = {}
        for r in records:
            player = r['player']
            if player in final:
                obj = final[player]
                for k in r.keys():
                    if k in HEADERS:
                        obj[k] += r[k]

            else:
                final[player] = {}
                for k in r.keys():
                    if k in HEADERS:
                        final[player][k] = r[k]
        return final


    def print_box_score(self, final):
        keys = []
        for ele in final:
            keys.append(ele)

        table = []
        for h in keys:
            table.append([h])

        count = 0
        for ele in final.keys():
            for j in final[ele].values():
                #print(j)
                table[count].append(j)
            count += 1

        table1 = [x for x in table if x[0].lower() in self.team1]
        table2 = [x for x in table if x[0].lower() in self.team2]
            
        totals1 = ['Total', 0.0,0,0,0,0,0,0,0,0,0,0,0,0]
        totals2 = ['Total', 0.0,0,0,0,0,0,0,0,0,0,0,0,0]
        count = 1
        for player in table1:
            for stat in player[1:]:
                totals1[count] += stat
                count += 1
            count = 1

        count = 1
        for player in table2:
            for stat in player[1:]:
                totals2[count] += stat
                count += 1
            count = 1
        table1.append(totals1)
        table2.append(totals2)
        path = Path(self.dir + 'box_score.txt')
        with open(path, 'w') as f:
            f.write(tabulate.tabulate(table1, HEADERS))
            f.write('\n\n')
            f.write(tabulate.tabulate(table2, HEADERS))


    def generate_csv(self, results, eu):
        path = Path(self.dir + eu + '.csv')
        headers = ['match_id', 'player']
        headers.extend(HEADERS[1:])
        with open(path, 'w') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for r in results:
                row = [eu]
                for h in headers[1:]:
                    row.append(r[h])
                writer.writerow(row)

    def merge_csvs(self):
        out = open(self.dir + 'stats.csv', 'w')
        writer = csv.writer(out)
        headers = False
        for filename in os.listdir(self.dir):
            if filename[-3:] == 'csv':
                path = Path(self.dir + filename)
                with open(path, 'r') as csvfile:
                    reader = csv.reader(csvfile)
                    if headers:
                        next(reader, None)
                    else:
                        headers = True
                    for row in reader:
                        writer.writerow(row)



if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Expected 3 arguements, got " + str(len(sys.argv) - 1))
        print("Usage: python3 box_score.py <input_directory> <team1> <team2>")
        print("Teams:", TEAMS.keys())
        print("ndjson files should be named according to corresponding eu link, e.g. 2760886.ndjson")
        sys.exit(1)
    dir = sys.argv[1]
    team1 = sys.argv[2]
    team2 = sys.argv[3]
    #eu = sys.argv[4]
    b = BoxScore(dir, team1, team2)
