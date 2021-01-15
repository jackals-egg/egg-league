########################################################################
# Imports
########################################################################

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import tagpro_eu
import json
import numpy as np
import pandas as pd
from os import path


########################################################################
# Config
########################################################################

# Set to True to force all matches to update
force_update = False

# Set root directory (should only need to do once)
r = r'C:\Users\Jackals\PycharmProjects\eggball'

# ID of Google Sheet (between 'spreadsheets/d/' and '/edit')
sheet_loc = '1j_NRzYxIWEgit3ONiFtDXj40hmHJM6YUvqAmejqcE5M'

# Name of Tab in Google Sheets
tab_name = 'input_matches'

# Don't change unless Google changes the location
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# Force a player onto a team for a match if the script can't figure it out
team_force = {2507835: {'T-Swift!': 'RCR'}}


########################################################################
# Class
########################################################################

class EggMatch:

    drops = list()
    raps = list()
    df_rename = {'name': 'player',
                 }

    def __init__(self, match_id, root):
        global a
        self.match_id = match_id
        self.root = root
        a = self.match = self.get_match(match_id)
        self.assign_players()
        self.parse_caps()
        self.parse_drops()
        self.parse_raps()

    def get_match(self, match_id):
        _json_path = self.root + f'\\jsons\\match{match_id}.json'
        try:
            with open(_json_path, 'r') as _json_handle:
                return tagpro_eu.match.Match(json.load(_json_handle))
        except FileNotFoundError:
            return tagpro_eu.download_match(match_id)

    def assign_players(self):
        """
        Search for players unassigned to a team and assign a team,
        unless the player is already on a team
        (i.e., disconnected and rejoined)
        """
        for i in range(len(self.match.players)):
            if not self.match.players[i].team:
                break_flag = False
                for j in range(len(self.match.players)):
                    if self.match.players[i].name ==\
                            self.match.players[j].name and i != j:
                        break_flag = True
                        del self.match.players[i]
                        break
                if break_flag:
                    break
                self.match.players[i].__team__ = self.assign_player(
                    self.match.players[i])
        else:
            return None
        self.assign_players()

    def assign_player(self, p):
        """
        If a player substituted in after the game started, player.team
        will be None. This method uses the team he had the most splat
        with to attribute player to a team.
        """
        print(f'Auto-assigning {p.name}...')
        t = [s.team.name for s in self.match.splats if s.player == p]
        d = {None: 0}
        for s in t:
            try:
                d[s] += 1
            except KeyError:
                d[s] = 1
        t = max([d[k] for k in d])
        for k, v in d.items():
            if v == t:
                try:
                    return [t for t in self.match.teams if t.name == k][0]
                except IndexError:
                    print(team_force[self.match_id][p.name])
                    return [t for t in self.match.teams if t.name ==
                            team_force[self.match_id][p.name]][0]
                except KeyError:
                    raise KeyError(f'Lookup match {self.match_id} and add'
                                   f'team name to {p.name} in team_force'
                                   f'in config.')

    def parse_caps(self):
        self.match.team_red.stats.caps_for = self.match.team_red.score
        self.match.team_blue.stats.caps_for = self.match.team_blue.score
        self.match.team_red.stats.caps_against = self.match.team_blue.score
        self.match.team_blue.stats.caps_against = self.match.team_red.score
        for i in range(len(self.match.players)):
            if self.match.players[i].team.name == self.match.team_blue.name:
                self.match.players[i].stats.caps_against =\
                    self.match.team_red.score
                self.match.players[i].stats.caps_for =\
                    self.match.team_blue.score
            elif self.match.players[i].team.name == self.match.team_red.name:
                self.match.players[i].stats.caps_against =\
                    self.match.team_blue.score
                self.match.players[i].stats.caps_for =\
                    self.match.team_red.score
            else:
                print(f'WARNING! Match {self.match_id} - '
                      f'{self.match.players[i].name} unattributed to team!')

    def parse_raps(self):
        cap_events = [k for k in self.match.create_timeline()
                      if k[1] == 'Capture marsball']
        d = {}
        for s in cap_events:
            c = s[0]
            try:
                d[c] += 1
            except KeyError:
                d[c] = 1
        k = [i for i in d if d[i] > 1]
        self.raps = [s for s in cap_events if s[0] in k]

        # iterate through players and create mapping
        p_raps = {}
        i = 0
        for p in self.match.players:
            p_raps[p.name] = [i, 0]
            i += 1
        for d in self.raps:
            p_raps[d[2].name][1] += 1

        # init raps in stats collections, then fill
        for i in range(len(self.match.players)):
            self.match.players[0].stats.raps = 0
        self.match.team_red.stats.raps = 0
        self.match.team_blue.stats.raps = 0
        for p in p_raps:
            self.match.players[p_raps[p][0]].stats.raps = p_raps[p][1]
        for i in range(len(self.match.players)):
            if self.match.players[i].team.name == self.match.team_blue.name:
                self.match.team_blue.stats.raps +=\
                    self.match.players[i].stats.raps
            elif self.match.players[i].team.name == self.match.team_red.name:
                self.match.team_red.stats.raps +=\
                    self.match.players[i].stats.raps
            else:
                print(f'WARNING! Match {self.match_id} - '
                      f'{self.match.players[i].name} unattributed to team!')

    def parse_drops(self):
        d = {}
        for s in self.match.splats:
            c = int(s.time)
            try:
                d[c] += 1
            except KeyError:
                d[c] = 1
        k = [i for i in d if d[i] < 3]
        self.drops = [s for s in self.match.splats if int(s.time) in k]
        p_drops = {}
        i = 0
        for p in self.match.players:
            p_drops[p.name] = [i, 0]
            i += 1
        for d in self.drops:
            p_drops[d.player.name][1] += 1
        for p in p_drops:
            self.match.players[p_drops[p][0]].stats.drops = p_drops[p][1]
        for i in range(len(self.match.players)):
            if self.match.players[i].team.name == self.match.team_blue.name:
                self.match.team_blue.stats.drops +=\
                    self.match.players[i].stats.drops
            elif self.match.players[i].team.name == self.match.team_red.name:
                self.match.team_red.stats.drops +=\
                    self.match.players[i].stats.drops
            else:
                print(f'WARNING! Match {self.match_id} - '
                      f'{self.match.players[i].name} unattributed to team!')

    def to_csv(self, force=False):
        p = self.root + f'\\csvs\\match{self.match_id}.csv'
        if force or not path.exists(p):
            p_cols = ['name', 'team', 'cap_diff', 'caps_for', 'caps_against',
                      'captures', 'drops', 'prevent', 'time', 'raps']
            t_cols = ['team_captures', 'team_drops', 'team_prevent',
                      'team_raps']
            o_cols = ['opp_captures', 'opp_drops', 'opp_prevent', 'opp_raps']
            df = pd.DataFrame(columns=['match_id']+p_cols+t_cols+o_cols)
            for i in range(len(self.match.players)):
                df.loc[i, 'match_id'] = self.match_id
                for c in p_cols:
                    if c in ['name', 'team']:
                        df.loc[i, c] = getattr(self.match.players[i], c, np.nan)
                    else:
                        df.loc[i, c] = getattr(self.match.players[i].stats, c, np.nan)
                    if c in ['time', 'prevent']:
                        df.loc[i, c] = int(df.loc[i, c])
                    elif c in ['team']:
                        df.loc[i, c] = df.loc[i, c].name
                for c in t_cols:
                    s = c[5:]
                    df.loc[i, c] = getattr(self.match.players[i].team.stats, s, np.nan)
                    if s in ['time', 'prevent']:
                        df.loc[i, c] = int(df.loc[i, c])
                if self.match.players[i].team == self.match.team_blue:
                    for c in o_cols:
                        s = c[4:]
                        df.loc[i, c] = getattr(self.match.team_red.stats, s, np.nan)
                        if s in ['time', 'prevent']:
                            df.loc[i, c] = int(df.loc[i, c])
                else:
                    for c in o_cols:
                        s = c[4:]
                        df.loc[i, c] = getattr(self.match.team_blue.stats, s, np.nan)
                        if s in ['time', 'prevent']:
                            df.loc[i, c] = int(df.loc[i, c])
            df.rename(columns=self.df_rename, inplace=True)
            df.to_csv(p, index=False)
            print(f'{self.match_id} exported.')
        else:
            print(f'{self.match_id} already exists, no action taken.')


########################################################################
# Functions
########################################################################

def process_matches(matches, root):
    if type(matches) == list:
        match_list = matches
    elif isinstance(matches, pd.Series):
        match_list = matches.to_list()
    else:
        err = f'process_matches received ' \
            f'unknown type for matches: {type(matches)}'
        raise(TypeError, err)
    for m in match_list:
        try:
            m = int(m)
        except ValueError:
            continue
        if force_update or not path.exists(root + f'\\csvs\\match{m}.csv'):
            print(f'Loading {m}...')
            EggMatch(m, root).to_csv(force_update)


def get_sheets_data(sheet_id, tab):
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens,
    # and is created automatically when the authorization flow completes
    # for the first time.
    if path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=sheet_id,
                                range=tab).execute()
    values = result.get('values', [])

    if not values:
        print('No data found.')
    else:
        return values


def create_half_df(half_data):
    _half_df = pd.DataFrame(half_data[1:], columns=half_data[0])

    # Turn everything numeric than can be
    _half_df = _half_df.apply(pd.to_numeric, errors='ignore')

    # Warn for duplicates
    _dupe_cols = ['league', 'season', 'week', 'match', 'game', 'half']
    _dupes = _half_df.loc[_half_df.duplicated(_dupe_cols, keep=False)]
    if not _dupes.empty:
        print('WARNING: Duplicate rows detected!')
        print(_dupes[_dupe_cols])

    # Classify league and season
    _half_df['league_season'] = _half_df.league + _half_df.season.astype(str)

    # Create unique game_id for each game
    _half_df['game_id'] = _half_df.league.astype(str) + '_' + \
        _half_df.season.astype(str) + '_' + \
        _half_df.week.astype(str) + '_' + \
        _half_df.match.astype(str) + '_' + \
        _half_df.game.astype(str)

    # Populate data with cap differential
    _half_df['cd'] = _half_df.score_1 - _half_df.score_2

    # Grab EU data
    # hold, ha, prevent, pa, grabs, drops, returns, tags, pups

    # Group by
    _game_gb = _half_df.groupby('game_id')

    # Calculate game scores
    _half_df['game_s1'] = _half_df.merge(_game_gb.score_1.sum(), on='game_id',
                                         how='left').score_1_y
    _half_df['game_s2'] = _half_df.merge(_game_gb.score_2.sum(), on='game_id',
                                         how='left').score_2_y
    _half_df['game_cd'] = _half_df.game_s1 - _half_df.game_s2

    # Flag games with an OT half
    _ot = _half_df.loc[_half_df.half.eq(3)][['game_id']]
    _ot['game_ot'] = True
    _half_df['game_ot'] = _half_df.merge(_ot, on='game_id', how='left').game_ot
    _half_df.game_ot.fillna(False, inplace=True)

    del _ot, _game_gb
    return _half_df


########################################################################
# Main
########################################################################

if __name__ == '__main__':
    a = None  # For debugging Match object
    match_df = create_half_df(get_sheets_data(sheet_loc, tab_name))
    process_matches(match_df.eu, r)
    print('Done!')
