########################################################################
# Imports
########################################################################

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import pandas as pd
from os import path
from glob import glob


########################################################################
# Config
########################################################################

# Set root directory (should only need to do once)
r = r'C:\Users\Jackals\PycharmProjects\eggball'

# Don't change unless Google changes the location
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# ID of Google Sheet (between 'spreadsheets/d/' and '/edit')
sheet_loc = '1j_NRzYxIWEgit3ONiFtDXj40hmHJM6YUvqAmejqcE5M'

# Name of Tab in Google Sheets
tab_name = 'input_matches'

# The rest is setup, leave it alone
df = None


########################################################################
# Functions
########################################################################

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

    # Calculate game hold, ha, prevent, grabs, drops, returns, tags, pups
    # _half_df['game_hold'] = _half_df.merge(_game_gb.hold.sum(), on='game_id',
    #                                        how='left').hold_y
    # _half_df['game_ha'] = _half_df.merge(_game_gb.ha.sum(), on='game_id',
    #                                      how='left').hold_y

    del _ot, _game_gb
    return _half_df


def get_map(sheet_data):
    d = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
    d.loc[:, 'match_id'] = d.match_id.astype('int64')
    return d


########################################################################
# Main
########################################################################

if __name__ == '__main__':
    # Load data
    print('Loading data...')
    print('\tinput_matches...')
    df_h = create_half_df(get_sheets_data(sheet_loc, 'input_matches'))
    print('\tCSVs...')
    df_s = pd.concat([pd.read_csv(f) for f in glob(r + '\\csvs\\*.csv')])
    print('\tmap_teams...')
    df_teams = get_map(get_sheets_data(sheet_loc, 'map_teams'))
    print('\tmap_players...')
    df_players = get_map(get_sheets_data(sheet_loc, 'map_players'))

    # Check for incorrect scores in main sheet
    print('Checking for incorrect scores...')
    df = df_s.merge(df_h, how='left', left_on='match_id', right_on='eu')
    print(f'Size: {df.shape} (should match size below)')
    cc = df.loc[df.caps_for.ne(df.score_1) & df.caps_for.ne(df.score_2)]
    err = list(cc.match_id.unique())
    verified = [2579325]
    [err.remove(v) for v in verified]
    if len(err) > 0:
        print(f'Check these match_ids for erroneous scores!\n{err}')
        print('You will need to reload match CSVs for these if erroneous!')

    # Force verified games to be a certain score
    df.loc[df.match_id.eq(2579325), 'caps_for'] = 8
    df.loc[df.match_id.eq(2579325), 'caps_against'] = 8
    df.loc[df.match_id.eq(2579325), 'team_captures'] = 8
    df.loc[df.match_id.eq(2579325), 'opp_captures'] = 8

    # For matches without correct abbreviations in the team name, assign
    # team names to players based on scores. If game was a tie, it must
    # be done manually -- use map_teams tab to configure
    print('Updating team names in tied games...')
    tie = df.loc[df.caps_for.eq(df.caps_against)].reset_index(drop=True)
    tie['to'] = tie.merge(df_teams, how='left', on=('match_id', 'team'))[['to']]
    tie.team.update(tie.to)
    tie.drop('to', axis=1, inplace=True)

    # If game was not a tie, use scores from sheet to attribute teams
    print('Updating team name in non-ties...')
    no_tie = df.loc[df.caps_for.ne(df.caps_against)]
    no_tie.loc[no_tie.caps_for.eq(no_tie.score_1), 'team'] = no_tie.loc[
        no_tie.caps_for.eq(no_tie.score_1), 'team_1']
    no_tie.loc[no_tie.caps_for.eq(no_tie.score_2), 'team'] = no_tie.loc[
        no_tie.caps_for.eq(no_tie.score_2), 'team_2']

    # Merge results together
    print('Merging...')
    df = pd.concat([no_tie, tie])

    # Since a lot of players like to use stupid names, they need to be
    # mapped one game at a time... so use map_players tab to configure
    print('Updating player names...')
    df.reset_index(inplace=True, drop=True)
    df['to'] = df.merge(df_players, how='left',
                        on=('match_id', 'player'))[['to']]
    df.player.update(df.to)
    df.drop('to', axis=1, inplace=True)

    # Export results
    print(f'Size: {df.shape} (should match size above)')
    print('Exporting to CSV...')
    df.to_csv(r + '\\match_export.csv', index=False)

    print('Done!')


########################################################################
# Run these tests once everything comes back fine up to this point
########################################################################

# View all team combinations within each season. Use the count of teams
# first, then look at each team name if the count is off. Red and Blue
# are common offenders.

# Expected number of teams per season; update every season
ls_dict = {'egga1': 10,
           'egga2': 8,
           'egga3': 6,
           'eggb3': 6,
           'egga4': 6,
           'eggb4': 4
           }

for ls in df.league_season.unique():
    val = df.loc[df.league_season.eq(ls)].team.unique()
    print(f'{ls}: {len(val)} {val}')
    if ls_dict[ls] != len(val):
        print(f'^ too many, expected {ls_dict[ls]}!')

# If you find one that's off, set errant team name below. For
# each unique match_id, add a row to sheet "map_teams"

print(df.loc[df.team.eq('Red')])

# Re-run the main loop, then run the above again and double-check
# corrections. Once all is good, move to players...

########################################################################

# Now, check player names. It's best to attack season by season, looking
# for names that are close. The more people use reserved names, the less
# of a problem this is.

for ls in df.league_season.unique():
    print(ls + '\n')
    b = df.loc[df.league_season.eq(ls)].player.unique()
    a = []
    for k in b:
        a += [k.lower()]
    a = sorted(a)
    zug = ''
    for i in range(len(a)):
        zug += a[i] + ', '
        if i > 0 and a[i] == a[i - 1]:
            print(f'{a[i]} DUPE')
        if i % 10 == 9:
            zug = zug[:-1]
            print(zug)
            zug = ''
    print(zug)
    print('')
    zug = ''
    s = sorted(b)
    for i in range(len(b)):
        zug += s[i] + ', '
        if i % 10 == 9:
            zug = zug[:-1]
            print(zug)
            zug = ''
    print(zug + '\n\n')


# All players in one list
b = df.player.unique()
a = []
for k in b:
    a += [k.lower()]
a = sorted(a)
zug = ''
for i in range(len(a)):
    zug += a[i] + ', '
    if i > 0 and a[i] == a[i-1]:
        print(f'{a[i]} DUPE')
    if i % 10 == 9:
        zug = zug[:-1]
        print(zug)
        zug = ''
print(zug)
print('')
zug = ''
s = sorted(b)
for i in range(len(b)):
    zug += s[i] + ', '
    if i % 10 == 9:
        zug = zug[:-1]
        print(zug)
        zug = ''
print(zug + '\n\n')


# Modify as needed to identify corrections.
# Post corrections to sheet "map_players".
print(df.loc[df.league_season.eq('egga4') & df.player.eq('KINK/BRAZ')])
print(df.loc[df.league_season.eq('egga4') & df.player.eq('KINK/Braz')])
print(df.loc[df.player.eq('ahooger')])
print(df.loc[df.player.eq('gEm#1')])
print(df.loc[df.player.eq('Scary terry')])
print(df.loc[df.player.eq('Scary Terry')])
print(df.loc[df.player.eq('TC')])
