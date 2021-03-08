# egg-league
Miscellaneous Egg League Scripts

## The Process
After matches occur, the scores and EU match_id's are added to the input_matches tab on the EBL Results sheet, currently located here: https://docs.google.com/spreadsheets/d/1j_NRzYxIWEgit3ONiFtDXj40hmHJM6YUvqAmejqcE5M/

The match.py script is then run in its entirety: https://github.com/jackals-egg/egg-league/blob/main/match.py. The EggMatch object creates and tabulates the stats we're able to extract from EU data and stores it in the ./csvs/ folder on a match-by-match basis. The merge_season function should be run after a season ends (including playoffs) and EUs are finalized -- this is to lower processing times on the next script, as the next script often requires multiple runs before all necessary corrections are made. Any EUs that did not get properly uploaded to the tagpro.eu site but were locally captured should be named match1###.json and put in the ./jsons/ folder, where the EggMatch object will look first for match data. 

Next, the compile_matches.py script is run (up through the main section): https://github.com/jackals-egg/egg-league/blob/main/compile_matches.py. A short series of tests should be run next to ensure homogeneity of team and player names -- the output will be in the console. The team names portion is pretty well automated, and it should flag any seasons with improper team naming (assuming ls_dict is updated every season). The player naming is a bit trickier. While capitalization differences will get automatically flagged, variations in characters will have to be manually found. In both tema and player cases, the map_teams and map_player tabs of the above spreadsheet should be updated with any changes.

Finally, once all changes have been made and the main section of compile_matches.py having been run one last time after all changes were made to team/player maps, upload the match_export.csv file to the player_stats tab of the spreadsheet, replacing that tab with the uploaded data. A connection refresh must be requested in the Tableau workbook. This refresh can take anywhere from 5 minutes to a couple hours, depending on the size of the queue in Tableau Public.

## To Do
The box_scores.py script will be pretty heavily modified to output a table into the vcr_stats tab of the spreadsheet, similarly structured to the player_stats tab. Once that is complete, the table will be linked by match_id and player name to the main data source (again, player_stats), which will allow visualizations of other stats to be built.
